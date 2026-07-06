"""Tests for provider routing: heavy always first, fast model as last fallback."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMResponse
from nanobot.providers.fallback_provider import FallbackEntry, FallbackProvider


def _make_provider(name: str) -> MagicMock:
    p = MagicMock(name=name)
    p.get_default_model.return_value = f"{name}-model"
    p.active_model = f"{name}-model"
    p.generation = MagicMock(temperature=0.7, max_tokens=512, reasoning_effort=None)
    p.chat_with_retry = AsyncMock(return_value=LLMResponse(content=f"reply from {name}", tool_calls=[]))
    return p


def _make_loop(tmp_path) -> tuple[AgentLoop, MagicMock]:
    heavy = _make_provider("heavy")

    loop = AgentLoop(
        bus=MessageBus(),
        provider=heavy,
        workspace=tmp_path,
        model="heavy-model",
        context_window_tokens=65_536,
    )
    loop.tools.get_definitions = MagicMock(return_value=[])
    return loop, heavy


# ---------------------------------------------------------------------------
# Heavy always first
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_simple_message_routed_to_heavy(tmp_path) -> None:
    """All messages — including short simple ones — go to the heavy provider."""
    loop, heavy = _make_loop(tmp_path)

    await loop.process_direct("hello", session_key="cli:test")

    heavy.chat_with_retry.assert_awaited_once()


@pytest.mark.asyncio
async def test_long_message_routed_to_heavy(tmp_path) -> None:
    """Long messages also go to the heavy provider."""
    loop, heavy = _make_loop(tmp_path)

    await loop.process_direct("x" * 300, session_key="cli:test")

    heavy.chat_with_retry.assert_awaited_once()


@pytest.mark.asyncio
async def test_keyword_message_routed_to_heavy(tmp_path) -> None:
    """Messages with task keywords go to the heavy provider."""
    loop, heavy = _make_loop(tmp_path)

    await loop.process_direct("debug this crash", session_key="cli:test")

    heavy.chat_with_retry.assert_awaited_once()


# ---------------------------------------------------------------------------
# Fast model as last fallback via FallbackProvider
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fast_model_used_after_all_fallbacks_fail(tmp_path) -> None:
    """Fast model is reached only after all other providers in the chain fail."""
    heavy_inner = _make_provider("heavy")
    fallback_inner = _make_provider("fallback")
    fast_inner = _make_provider("fast")

    error_response = LLMResponse(content="error", tool_calls=[], finish_reason="error")
    heavy_inner.chat_with_retry = AsyncMock(return_value=error_response)
    fallback_inner.chat_with_retry = AsyncMock(return_value=error_response)
    fast_inner.chat_with_retry = AsyncMock(
        return_value=LLMResponse(content="fast reply", tool_calls=[])
    )

    chain = [
        FallbackEntry(provider=heavy_inner, model="heavy-model"),
        FallbackEntry(provider=fallback_inner, model="fallback-model"),
        FallbackEntry(provider=fast_inner, model="fast-model"),
    ]
    provider = FallbackProvider(chain)
    provider.generation = heavy_inner.generation

    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="heavy-model",
        context_window_tokens=65_536,
    )
    loop.tools.get_definitions = MagicMock(return_value=[])

    await loop.process_direct("hello", session_key="cli:test")

    heavy_inner.chat_with_retry.assert_awaited_once()
    fallback_inner.chat_with_retry.assert_awaited_once()
    fast_inner.chat_with_retry.assert_awaited_once()


@pytest.mark.asyncio
async def test_fast_model_not_used_when_heavy_succeeds(tmp_path) -> None:
    """Fast model is never called when the heavy provider succeeds."""
    heavy_inner = _make_provider("heavy")
    fast_inner = _make_provider("fast")

    heavy_inner.chat_with_retry = AsyncMock(
        return_value=LLMResponse(content="heavy reply", tool_calls=[])
    )
    fast_inner.chat_with_retry = AsyncMock(
        return_value=LLMResponse(content="fast reply", tool_calls=[])
    )

    chain = [
        FallbackEntry(provider=heavy_inner, model="heavy-model"),
        FallbackEntry(provider=fast_inner, model="fast-model"),
    ]
    provider = FallbackProvider(chain)
    provider.generation = heavy_inner.generation

    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="heavy-model",
        context_window_tokens=65_536,
    )
    loop.tools.get_definitions = MagicMock(return_value=[])

    await loop.process_direct("hello", session_key="cli:test")

    heavy_inner.chat_with_retry.assert_awaited_once()
    fast_inner.chat_with_retry.assert_not_awaited()


# ---------------------------------------------------------------------------
# History — always full context (no per-provider trimming)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_heavy_provider_receives_full_history(tmp_path, monkeypatch) -> None:
    """History is passed in full to the heavy provider regardless of message content."""
    import nanobot.utils.helpers as helpers_mod

    loop, heavy = _make_loop(tmp_path)

    session = loop.sessions.get_or_create("cli:test")
    session.messages = [
        {"role": "user",      "content": "old message 1"},
        {"role": "assistant", "content": "old reply 1"},
        {"role": "user",      "content": "old message 2"},
        {"role": "assistant", "content": "old reply 2"},
        {"role": "user",      "content": "recent message"},
        {"role": "assistant", "content": "recent reply"},
    ]
    loop.sessions.save(session)

    monkeypatch.setattr(helpers_mod, "estimate_message_tokens", lambda _m: 20)

    captured_messages: list = []

    async def capture_chat(*args, messages, **kwargs):
        captured_messages.extend(messages)
        return LLMResponse(content="ok", tool_calls=[])

    heavy.chat_with_retry = capture_chat

    await loop.process_direct("hello", session_key="cli:test")

    history_in_call = [m for m in captured_messages if m["role"] != "system"]
    history_only = history_in_call[:-1]  # exclude the appended user message
    assert len(history_only) == 6, (
        f"Expected all 6 history messages, got {len(history_only)}"
    )
