"""FallbackProvider — tries multiple (provider, model) pairs in order on error."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger

from nanobot.providers.base import LLMProvider, LLMResponse


@dataclass
class FallbackEntry:
    provider: LLMProvider
    model: str


class FallbackProvider(LLMProvider):
    """Wraps an ordered list of providers and falls back to the next one on error.

    The primary provider is chain[0].  On any error response, chain[1] is
    tried, then chain[2], and so on.  The last error response is returned if
    all entries fail.

    Generation settings (temperature, max_tokens, reasoning_effort) are
    propagated to each sub-provider before every call so that changing
    self.generation is enough to affect the whole chain.
    """

    def __init__(self, chain: list[FallbackEntry]) -> None:
        if not chain:
            raise ValueError("FallbackProvider requires at least one entry")
        self._chain = chain
        self._active_index = 0
        super().__init__(chain[0].provider.api_key, chain[0].provider.api_base)

    @property
    def active_model(self) -> str:
        """Return the model of the currently active chain entry."""
        return self._chain[self._active_index].model

    def get_default_model(self) -> str:
        return self._chain[0].model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        # Direct chat() delegates to primary only (retries happen in chat_with_retry).
        entry = self._chain[0]
        return await entry.provider.chat(
            messages=messages, tools=tools,
            model=model or entry.model, **kwargs,
        )

    async def chat_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        # Propagate generation settings to every sub-provider.
        for entry in self._chain:
            entry.provider.generation = self.generation

        last_response: LLMResponse | None = None

        for i, entry in enumerate(self._chain):
            if i > 0:
                logger.warning(
                    "Provider '{}' failed, trying fallback #{}: '{}'",
                    self._chain[i - 1].model, i, entry.model,
                )
            response = await entry.provider.chat_with_retry(
                messages=messages, tools=tools, model=entry.model, **kwargs
            )
            if response.finish_reason != "error":
                self._active_index = i
                return response

            last_response = response
            logger.warning(
                "Provider '{}' error: {}",
                entry.model, (response.content or "")[:120],
            )

        return last_response  # type: ignore[return-value]
