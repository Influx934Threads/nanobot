"""Regression tests for LiteLLM provider routing behavior.

Validates that:
- OpenRouter and other OpenAI-compatible gateways use the openai SDK directly.
- Model names are sent as-is to provider APIs (no LiteLLM routing prefix needed).
- Anthropic (non-OpenAI wire format) is detected and routed through LiteLLM.
- custom_llm_provider is never injected into requests.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.providers.litellm_provider import LiteLLMProvider
from nanobot.providers.registry import find_by_name


def _fake_response(content: str = "ok") -> SimpleNamespace:
    """Build a minimal chat-completion-shaped response object."""
    message = SimpleNamespace(
        content=content,
        tool_calls=None,
        reasoning_content=None,
        thinking_blocks=None,
    )
    choice = SimpleNamespace(message=message, finish_reason="stop")
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    return SimpleNamespace(choices=[choice], usage=usage)


def _mock_create(provider: LiteLLMProvider) -> AsyncMock:
    """Attach an AsyncMock to the provider's openai client and return it."""
    fake = AsyncMock(return_value=_fake_response())
    provider._openai_client.chat = MagicMock()
    provider._openai_client.chat.completions = MagicMock()
    provider._openai_client.chat.completions.create = fake
    return fake


def test_openrouter_spec_uses_prefix_not_custom_llm_provider() -> None:
    """OpenRouter registry spec must use litellm_prefix, not custom_llm_provider kwarg.

    LiteLLM internally adds a provider/ prefix when custom_llm_provider is set,
    which double-prefixes models (openrouter/anthropic/model) and breaks the API.
    """
    spec = find_by_name("openrouter")
    assert spec is not None
    assert spec.litellm_prefix == "openrouter"
    assert "custom_llm_provider" not in spec.litellm_kwargs, (
        "custom_llm_provider causes LiteLLM to double-prefix the model name"
    )


@pytest.mark.asyncio
async def test_openrouter_prefixes_model_correctly() -> None:
    """OpenRouter via openai SDK: model name is sent as-is to the provider's API."""
    provider = LiteLLMProvider(
        api_key="sk-or-test-key",
        api_base="https://openrouter.ai/api/v1",
        default_model="anthropic/claude-sonnet-4-5",
        provider_name="openrouter",
    )
    assert not provider._use_litellm, "OpenRouter should use openai SDK, not LiteLLM"
    assert "openrouter.ai" in str(provider._openai_client.base_url)

    fake_create = _mock_create(provider)
    await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="anthropic/claude-sonnet-4-5",
    )

    call_kwargs = fake_create.call_args.kwargs
    # OpenRouter's API receives the model name without any routing prefix
    assert call_kwargs["model"] == "anthropic/claude-sonnet-4-5"
    assert "custom_llm_provider" not in call_kwargs


@pytest.mark.asyncio
async def test_non_gateway_provider_no_extra_kwargs() -> None:
    """sk-ant- API keys without explicit provider_name must route through LiteLLM."""
    provider = LiteLLMProvider(
        api_key="sk-ant-test-key",
        default_model="claude-sonnet-4-5",
    )
    assert provider._use_litellm, (
        "sk-ant- key must trigger LiteLLM path (Anthropic uses a non-OpenAI wire format)"
    )


@pytest.mark.asyncio
async def test_gateway_without_litellm_kwargs_injects_nothing_extra() -> None:
    """AiHubMix (OpenAI-compatible gateway) should use openai SDK with no extra kwargs."""
    provider = LiteLLMProvider(
        api_key="sk-aihub-test-key",
        api_base="https://aihubmix.com/v1",
        default_model="claude-sonnet-4-5",
        provider_name="aihubmix",
    )
    assert not provider._use_litellm, "AiHubMix should use openai SDK, not LiteLLM"
    assert "aihubmix.com" in str(provider._openai_client.base_url)

    fake_create = _mock_create(provider)
    await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="claude-sonnet-4-5",
    )

    call_kwargs = fake_create.call_args.kwargs
    assert "custom_llm_provider" not in call_kwargs


@pytest.mark.asyncio
async def test_openrouter_autodetect_by_key_prefix() -> None:
    """sk-or- key should auto-detect OpenRouter without explicit provider_name."""
    provider = LiteLLMProvider(
        api_key="sk-or-auto-detect-key",
        default_model="anthropic/claude-sonnet-4-5",
    )
    assert not provider._use_litellm
    assert "openrouter.ai" in str(provider._openai_client.base_url)

    fake_create = _mock_create(provider)
    await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="anthropic/claude-sonnet-4-5",
    )

    call_kwargs = fake_create.call_args.kwargs
    # Model is sent as-is to OpenRouter — no openrouter/ prefix needed
    assert call_kwargs["model"] == "anthropic/claude-sonnet-4-5"


@pytest.mark.asyncio
async def test_openrouter_native_model_id_gets_double_prefixed() -> None:
    """openrouter/free is an OpenRouter model ID and is sent as-is via the openai SDK.

    Previously, LiteLLM required double-prefixing (openrouter/openrouter/free) so it
    would strip one layer before the API call. The openai SDK sends model names as-is,
    so openrouter/free reaches the API unchanged — which is exactly what OpenRouter expects.
    """
    provider = LiteLLMProvider(
        api_key="sk-or-test-key",
        api_base="https://openrouter.ai/api/v1",
        default_model="openrouter/free",
        provider_name="openrouter",
    )
    fake_create = _mock_create(provider)
    await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
        model="openrouter/free",
    )

    call_kwargs = fake_create.call_args.kwargs
    assert call_kwargs["model"] == "openrouter/free", (
        "openai SDK sends model name as-is; OpenRouter's API receives openrouter/free directly"
    )
