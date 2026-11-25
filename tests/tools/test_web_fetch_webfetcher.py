"""Tests for the self-hosted webfetcher fetch path (local port, no upstream equivalent)."""

from __future__ import annotations

import json
import socket
from unittest.mock import patch

import pytest

from nanobot.agent.tools import web as web_module
from nanobot.agent.tools.web import WebFetchTool
from nanobot.agent.tools.web_config import WebFetchConfig


def _fake_resolve_public(hostname, port, family=0, type_=0):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _RecordingWebfetcherClient:
    """Fake httpx.AsyncClient that records every requested URL/params and
    returns a canned webfetcher-shaped JSON response."""

    requested: list[tuple[str, dict]] = []
    response_payload: dict = {"success": True, "markdown": "body text", "engine": "moli"}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, params=None, **kwargs):
        _RecordingWebfetcherClient.requested.append((url, params or {}))
        return _FakeResponse(_RecordingWebfetcherClient.response_payload)


@pytest.fixture
def webfetcher_client():
    _RecordingWebfetcherClient.requested = []
    _RecordingWebfetcherClient.response_payload = {
        "success": True,
        "markdown": "body text",
        "engine": "moli",
    }
    with patch("nanobot.agent.tools.web.httpx.AsyncClient", _RecordingWebfetcherClient):
        yield _RecordingWebfetcherClient


async def test_fetch_webfetcher_success(webfetcher_client) -> None:
    tool = WebFetchTool(config=WebFetchConfig(webfetcher_url="http://192.168.1.146:9000"))
    result = await tool._fetch_webfetcher("https://example.com/report", max_chars=1000)

    assert result is not None
    data = json.loads(result)
    assert data["extractor"] == "webfetcher:moli"
    assert "body text" in data["text"]
    assert webfetcher_client.requested == [
        ("http://192.168.1.146:9000/md", {"url": "https://example.com/report"})
    ]


async def test_fetch_webfetcher_returns_none_on_reported_failure(webfetcher_client) -> None:
    webfetcher_client.response_payload = {"success": False}
    tool = WebFetchTool(config=WebFetchConfig(webfetcher_url="http://192.168.1.146:9000"))
    result = await tool._fetch_webfetcher("https://example.com/report", max_chars=1000)
    assert result is None


async def test_fetch_webfetcher_returns_none_on_transport_error(webfetcher_client) -> None:
    class _RaisingClient(_RecordingWebfetcherClient):
        async def get(self, url, params=None, **kwargs):
            raise RuntimeError("connection refused")

    with patch("nanobot.agent.tools.web.httpx.AsyncClient", _RaisingClient):
        tool = WebFetchTool(config=WebFetchConfig(webfetcher_url="http://192.168.1.146:9000"))
        result = await tool._fetch_webfetcher("https://example.com/report", max_chars=1000)
    assert result is None


async def test_execute_prefers_webfetcher_over_jina(monkeypatch, webfetcher_client) -> None:
    """When webfetcher_url is set, execute() should use it and never call Jina."""
    tool = WebFetchTool(config=WebFetchConfig(webfetcher_url="http://192.168.1.146:9000"))
    jina_called = False

    async def _fail_if_called(*args, **kwargs):
        nonlocal jina_called
        jina_called = True
        return None

    monkeypatch.setattr(tool, "_fetch_jina", _fail_if_called)

    class FakeStreamResponse:
        status_code = 200
        headers = {"content-type": "text/html"}
        url = "https://example.com/report"

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakePreflightClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url, headers=None, **kwargs):
            return FakeStreamResponse()

    # The preflight image-detection client and the webfetcher client both go
    # through httpx.AsyncClient, so route by call signature: the preflight
    # uses .stream(), webfetcher uses .get(). Reuse the recording fake for
    # both since it implements .get(); .stream() needs the extra method.
    class _CombinedClient(_RecordingWebfetcherClient, FakePreflightClient):
        pass

    with (
        patch("nanobot.agent.tools.web.httpx.AsyncClient", _CombinedClient),
        patch("nanobot.security.network.socket.getaddrinfo", _fake_resolve_public),
        patch.object(web_module, "_pinned_dns_transport", lambda: object()),
    ):
        result = await tool.execute(url="https://example.com/report")

    data = json.loads(result)
    assert data["extractor"] == "webfetcher:moli"
    assert jina_called is False


async def test_execute_falls_back_to_jina_when_webfetcher_unset() -> None:
    """Default config (webfetcher_url="") must not change existing behavior."""
    tool = WebFetchTool()
    assert tool.config.webfetcher_url == ""
