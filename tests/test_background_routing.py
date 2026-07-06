"""Tests for background task routing: fast model for simple tasks, heavy for complex."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMResponse
from nanobot.utils.evaluator import evaluate_response
from nanobot.providers.base import LLMProvider, ToolCallRequest
from nanobot.heartbeat.service import HeartbeatService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(name: str) -> MagicMock:
    p = MagicMock(name=name)
    p.get_default_model.return_value = f"{name}-model"
    p.active_model = f"{name}-model"
    p.generation = MagicMock(temperature=0.7, max_tokens=512, reasoning_effort=None)
    p.chat_with_retry = AsyncMock(return_value=LLMResponse(content=f"reply from {name}", tool_calls=[]))
    return p


def _make_loop(tmp_path) -> tuple[AgentLoop, MagicMock, MagicMock]:
    heavy = _make_provider("heavy")
    fast = _make_provider("fast")
    loop = AgentLoop(
        bus=MessageBus(),
        provider=heavy,
        workspace=tmp_path,
        model="heavy-model",
        context_window_tokens=65_536,
        fast_provider=fast,
        fast_model="fast-model",
    )
    loop.tools.get_definitions = MagicMock(return_value=[])
    return loop, heavy, fast


# ---------------------------------------------------------------------------
# _is_heavy_background_task classifier
# ---------------------------------------------------------------------------

def test_classifier_simple_tasks_are_not_heavy():
    assert not AgentLoop._is_heavy_background_task("check if today's fetch is done")
    assert not AgentLoop._is_heavy_background_task("review open tasks")
    assert not AgentLoop._is_heavy_background_task("status report")
    assert not AgentLoop._is_heavy_background_task("verify archive date")
    assert not AgentLoop._is_heavy_background_task("nothing to do")

def test_classifier_action_tasks_are_heavy():
    # "fetch" alone is excluded (noun/verb ambiguity); DSPM tasks have other keywords too
    assert AgentLoop._is_heavy_background_task("update the archive")
    assert AgentLoop._is_heavy_background_task("send weekly email digest")
    assert AgentLoop._is_heavy_background_task("run daily DSPM news sync")
    assert AgentLoop._is_heavy_background_task("generate monthly report")
    assert AgentLoop._is_heavy_background_task("analyze recent articles")
    assert AgentLoop._is_heavy_background_task("sync archive with new data")
    assert AgentLoop._is_heavy_background_task("write summary of findings")


# ---------------------------------------------------------------------------
# process_direct background routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_simple_background_task_uses_fast_provider(tmp_path) -> None:
    loop, heavy, fast = _make_loop(tmp_path)

    await loop.process_direct(
        "check if today's date matches the last fetch date",
        is_background=True,
    )

    fast.chat_with_retry.assert_awaited_once()
    heavy.chat_with_retry.assert_not_awaited()


@pytest.mark.asyncio
async def test_heavy_background_task_uses_heavy_provider(tmp_path) -> None:
    loop, heavy, fast = _make_loop(tmp_path)

    await loop.process_direct(
        "fetch new DSPM articles and update the archive",
        is_background=True,
    )

    heavy.chat_with_retry.assert_awaited_once()
    fast.chat_with_retry.assert_not_awaited()


@pytest.mark.asyncio
async def test_user_message_always_uses_heavy_provider(tmp_path) -> None:
    """is_background=False (default) always routes to heavy regardless of content."""
    loop, heavy, fast = _make_loop(tmp_path)

    await loop.process_direct("check the status", is_background=False)

    heavy.chat_with_retry.assert_awaited_once()
    fast.chat_with_retry.assert_not_awaited()


@pytest.mark.asyncio
async def test_background_without_fast_provider_uses_heavy(tmp_path) -> None:
    """When no fast_provider is configured, background tasks fall through to heavy."""
    heavy = _make_provider("heavy")
    loop = AgentLoop(
        bus=MessageBus(),
        provider=heavy,
        workspace=tmp_path,
        model="heavy-model",
        context_window_tokens=65_536,
    )
    loop.tools.get_definitions = MagicMock(return_value=[])

    await loop.process_direct("check status", is_background=True)

    heavy.chat_with_retry.assert_awaited_once()


# ---------------------------------------------------------------------------
# HeartbeatService uses fast provider for _decide
# ---------------------------------------------------------------------------

class _DummyProvider(LLMProvider):
    def __init__(self, response: LLMResponse):
        super().__init__()
        self._response = response
        self.calls = 0

    async def chat(self, *args, **kwargs) -> LLMResponse:
        self.calls += 1
        return self._response

    def get_default_model(self) -> str:
        return "dummy-model"


@pytest.mark.asyncio
async def test_heartbeat_decide_uses_fast_provider(tmp_path) -> None:
    heavy = _DummyProvider(LLMResponse(content="", tool_calls=[]))
    fast = _DummyProvider(LLMResponse(
        content="",
        tool_calls=[ToolCallRequest(id="1", name="heartbeat", arguments={"action": "skip"})],
    ))

    service = HeartbeatService(
        workspace=tmp_path,
        provider=heavy,
        model="heavy-model",
        fast_provider=fast,
        fast_model="fast-model",
    )

    action, _ = await service._decide("heartbeat content")

    assert action == "skip"
    assert fast.calls == 1
    assert heavy.calls == 0


@pytest.mark.asyncio
async def test_heartbeat_decide_falls_back_to_heavy_when_no_fast(tmp_path) -> None:
    heavy = _DummyProvider(LLMResponse(
        content="",
        tool_calls=[ToolCallRequest(id="1", name="heartbeat", arguments={"action": "skip"})],
    ))

    service = HeartbeatService(
        workspace=tmp_path,
        provider=heavy,
        model="heavy-model",
    )

    action, _ = await service._decide("heartbeat content")

    assert action == "skip"
    assert heavy.calls == 1


# ---------------------------------------------------------------------------
# evaluate_response uses fast provider
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evaluator_uses_fast_provider_when_provided() -> None:
    heavy = _DummyProvider(LLMResponse(content="heavy reply", tool_calls=[]))
    fast = _DummyProvider(LLMResponse(
        content="",
        tool_calls=[ToolCallRequest(
            id="1", name="evaluate_notification",
            arguments={"should_notify": False, "reason": "routine"},
        )],
    ))

    result = await evaluate_response(
        "All clear", "check status",
        provider=heavy, model="heavy-model",
        fast_provider=fast, fast_model="fast-model",
    )

    assert result is False
    assert fast.calls == 1
    assert heavy.calls == 0


@pytest.mark.asyncio
async def test_evaluator_falls_back_to_heavy_when_no_fast() -> None:
    heavy = _DummyProvider(LLMResponse(
        content="",
        tool_calls=[ToolCallRequest(
            id="1", name="evaluate_notification",
            arguments={"should_notify": True, "reason": "important"},
        )],
    ))

    result = await evaluate_response("result", "task", provider=heavy, model="heavy-model")

    assert result is True
    assert heavy.calls == 1
