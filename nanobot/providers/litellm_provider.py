"""LLM provider — openai SDK primary path, lazy LiteLLM fallback for Anthropic."""

import hashlib
import os
import secrets
import string
from typing import Any

import json_repair
import openai
from loguru import logger

from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from nanobot.providers.registry import find_by_model, find_by_name, find_gateway

_ALLOWED_MSG_KEYS = frozenset({"role", "content", "tool_calls", "tool_call_id", "name", "reasoning_content"})
_ANTHROPIC_EXTRA_KEYS = frozenset({"thinking_blocks"})
_ALNUM = string.ascii_letters + string.digits

# Providers that need LiteLLM's translation layer (non-OpenAI-compatible wire format).
# Everything else talks standard /v1/chat/completions via the openai SDK.
_NEEDS_LITELLM = frozenset({"anthropic"})

# OpenAI-compatible base URLs for known providers.
# None = use openai SDK default ("openai") or requires explicit api_base in config ("vllm").
_OPENAI_BASES: dict[str, str | None] = {
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "moonshot": "https://api.moonshot.ai/v1",
    "minimax": "https://api.minimax.io/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "aihubmix": "https://aihubmix.com/v1",
    "volcengine": "https://ark.cn-beijing.volces.com/api/v3",
    "volcengine_coding_plan": "https://ark.cn-beijing.volces.com/api/coding/v3",
    "byteplus": "https://ark.ap-southeast.bytepluses.com/api/v3",
    "byteplus_coding_plan": "https://ark.ap-southeast.bytepluses.com/api/coding/v3",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "dashscope": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    "ollama": "http://localhost:11434/v1",
    "vllm": None,
    "openai": None,
}


def _short_tool_id() -> str:
    """Generate a 9-char alphanumeric ID compatible with all providers (incl. Mistral)."""
    return "".join(secrets.choice(_ALNUM) for _ in range(9))


class LiteLLMProvider(LLMProvider):
    """
    LLM provider using the openai SDK for OpenAI-compatible endpoints.
    LiteLLM is lazy-imported only for providers that need its translation layer (Anthropic).
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "anthropic/claude-opus-4-5",
        extra_headers: dict[str, str] | None = None,
        provider_name: str | None = None,
        request_timeout: float | None = None,
        context_window_tokens: int | None = None,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.extra_headers = extra_headers or {}
        self.request_timeout = request_timeout
        self.context_window_tokens = context_window_tokens
        self._provider_name = provider_name
        self._gateway = find_gateway(provider_name, api_key, api_base)

        effective_name = self._gateway.name if self._gateway else provider_name
        # Detect Anthropic by API key prefix when provider_name is not explicitly set
        if effective_name is None and api_key and api_key.startswith("sk-ant-"):
            effective_name = "anthropic"
        self._use_litellm: bool = effective_name in _NEEDS_LITELLM

        if not self._use_litellm:
            # Resolve base URL: explicit config > known-provider table > None (OpenAI native)
            base_url = api_base or _OPENAI_BASES.get(effective_name or "")
            timeout = request_timeout if request_timeout is not None else openai.NOT_GIVEN
            self._openai_client = openai.AsyncOpenAI(
                api_key=api_key or "dummy",
                base_url=base_url,
                timeout=timeout,
                default_headers=self.extra_headers,
            )
            # Detect Ollama backend: needs num_ctx + think=False in the request body
            self._is_ollama = (
                (self._gateway is not None and self._gateway.name == "ollama")
                or bool(api_base and "11434" in api_base)
            )
        else:
            # Anthropic path: configure env vars for LiteLLM
            if api_key:
                self._setup_env(api_key, api_base, default_model)
            self._langsmith_enabled = bool(os.getenv("LANGSMITH_API_KEY"))

    # ------------------------------------------------------------------
    # LiteLLM env-var setup (Anthropic path only)
    # ------------------------------------------------------------------

    def _setup_env(self, api_key: str, api_base: str | None, model: str) -> None:
        spec = (
            self._gateway
            or find_by_model(model)
            or (find_by_name(self._provider_name) if self._provider_name else None)
        )
        if not spec or not spec.env_key:
            return
        if self._gateway:
            os.environ[spec.env_key] = api_key
        else:
            os.environ.setdefault(spec.env_key, api_key)
        effective_base = api_base or spec.default_api_base
        for env_name, env_val in spec.env_extras:
            resolved = env_val.replace("{api_key}", api_key).replace("{api_base}", effective_base)
            os.environ.setdefault(env_name, resolved)

    # ------------------------------------------------------------------
    # Model resolution (LiteLLM path only — openai SDK uses bare names)
    # ------------------------------------------------------------------

    def _resolve_model(self, model: str) -> str:
        """Apply provider/gateway prefixes required by LiteLLM routing."""
        if self._gateway:
            prefix = self._gateway.litellm_prefix
            if self._gateway.strip_model_prefix:
                model = model.split("/")[-1]
            if prefix:
                model = f"{prefix}/{model}"
            return model
        spec = find_by_model(model) or (find_by_name(self._provider_name) if self._provider_name else None)
        if spec and spec.litellm_prefix:
            model = self._canonicalize_explicit_prefix(model, spec.name, spec.litellm_prefix)
            if not any(model.startswith(s) for s in spec.skip_prefixes):
                model = f"{spec.litellm_prefix}/{model}"
        return model

    @staticmethod
    def _canonicalize_explicit_prefix(model: str, spec_name: str, canonical_prefix: str) -> str:
        """Normalize explicit provider prefixes like `github-copilot/...`."""
        if "/" not in model:
            return model
        prefix, remainder = model.split("/", 1)
        if prefix.lower().replace("-", "_") != spec_name:
            return model
        return f"{canonical_prefix}/{remainder}"

    # ------------------------------------------------------------------
    # Cache control
    # ------------------------------------------------------------------

    def _supports_cache_control(self, model: str) -> bool:
        if self._gateway is not None:
            return self._gateway.supports_prompt_caching
        spec = find_by_model(model)
        return spec is not None and spec.supports_prompt_caching

    def _apply_cache_control(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None]:
        new_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                content = msg["content"]
                if isinstance(content, str):
                    new_content = [{"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}]
                else:
                    new_content = list(content)
                    new_content[-1] = {**new_content[-1], "cache_control": {"type": "ephemeral"}}
                new_messages.append({**msg, "content": new_content})
            else:
                new_messages.append(msg)
        new_tools = tools
        if tools:
            new_tools = list(tools)
            new_tools[-1] = {**new_tools[-1], "cache_control": {"type": "ephemeral"}}
        return new_messages, new_tools

    # ------------------------------------------------------------------
    # Model overrides and message sanitization
    # ------------------------------------------------------------------

    def _apply_model_overrides(self, model: str, kwargs: dict[str, Any]) -> None:
        model_lower = model.lower()
        spec = find_by_model(model)
        if spec:
            for pattern, overrides in spec.model_overrides:
                if pattern in model_lower:
                    kwargs.update(overrides)
                    return

    @staticmethod
    def _extra_msg_keys(original_model: str, resolved_model: str) -> frozenset[str]:
        spec = find_by_model(original_model) or find_by_model(resolved_model)
        if (
            (spec and spec.name == "anthropic")
            or "claude" in original_model.lower()
            or resolved_model.startswith("anthropic/")
        ):
            return _ANTHROPIC_EXTRA_KEYS
        return frozenset()

    @staticmethod
    def _normalize_tool_call_id(tool_call_id: Any) -> Any:
        """Normalize tool_call_id to a provider-safe 9-char alphanumeric form."""
        if not isinstance(tool_call_id, str):
            return tool_call_id
        if len(tool_call_id) == 9 and tool_call_id.isalnum():
            return tool_call_id
        return hashlib.sha1(tool_call_id.encode()).hexdigest()[:9]

    @staticmethod
    def _sanitize_messages(
        messages: list[dict[str, Any]], extra_keys: frozenset[str] = frozenset()
    ) -> list[dict[str, Any]]:
        """Strip non-standard keys and ensure assistant messages have a content key."""
        allowed = _ALLOWED_MSG_KEYS | extra_keys
        sanitized = LLMProvider._sanitize_request_messages(messages, allowed)
        id_map: dict[str, str] = {}

        def map_id(value: Any) -> Any:
            if not isinstance(value, str):
                return value
            return id_map.setdefault(value, LiteLLMProvider._normalize_tool_call_id(value))

        for clean in sanitized:
            # Keep assistant tool_calls[].id and tool tool_call_id in sync after
            # shortening, otherwise strict providers reject the broken linkage.
            if isinstance(clean.get("tool_calls"), list):
                normalized_tool_calls = []
                for tc in clean["tool_calls"]:
                    if not isinstance(tc, dict):
                        normalized_tool_calls.append(tc)
                        continue
                    tc_clean = dict(tc)
                    tc_clean["id"] = map_id(tc_clean.get("id"))
                    normalized_tool_calls.append(tc_clean)
                clean["tool_calls"] = normalized_tool_calls
            if "tool_call_id" in clean and clean["tool_call_id"]:
                clean["tool_call_id"] = map_id(clean["tool_call_id"])
        return sanitized

    # ------------------------------------------------------------------
    # Chat dispatch
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        if self._use_litellm:
            return await self._chat_litellm(
                messages, tools, model, max_tokens, temperature, reasoning_effort, tool_choice
            )
        return await self._chat_openai(
            messages, tools, model, max_tokens, temperature, reasoning_effort, tool_choice
        )

    async def _chat_openai(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str | None,
        max_tokens: int,
        temperature: float,
        reasoning_effort: str | None,
        tool_choice: str | dict[str, Any] | None,
    ) -> LLMResponse:
        original_model = model or self.default_model
        extra_msg_keys = self._extra_msg_keys(original_model, original_model)

        if self._supports_cache_control(original_model):
            messages, tools = self._apply_cache_control(messages, tools)

        kwargs: dict[str, Any] = {
            "model": original_model,
            "messages": self._sanitize_messages(
                self._sanitize_empty_content(messages), extra_keys=extra_msg_keys
            ),
            "max_tokens": max(1, max_tokens),
            "temperature": temperature,
        }

        self._apply_model_overrides(original_model, kwargs)

        # Ollama requires num_ctx to pre-allocate the KV cache; without it the
        # server defaults to 2048 and silently truncates or returns an empty body.
        extra_body: dict[str, Any] = {}
        if self._is_ollama and self.context_window_tokens:
            extra_body["num_ctx"] = self.context_window_tokens
            extra_body["think"] = False  # disable built-in thinking mode (Qwen3 etc.)
        if extra_body:
            kwargs["extra_body"] = extra_body

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"

        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort

        try:
            response = await self._openai_client.chat.completions.create(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            return LLMResponse(content=f"Error calling LLM: {str(e)}", finish_reason="error")

    async def _chat_litellm(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str | None,
        max_tokens: int,
        temperature: float,
        reasoning_effort: str | None,
        tool_choice: str | dict[str, Any] | None,
    ) -> LLMResponse:
        import litellm  # noqa: PLC0415
        from litellm import acompletion  # noqa: PLC0415

        litellm.suppress_debug_info = True
        litellm.drop_params = True

        original_model = model or self.default_model
        resolved = self._resolve_model(original_model)
        extra_msg_keys = self._extra_msg_keys(original_model, resolved)

        if self._supports_cache_control(original_model):
            messages, tools = self._apply_cache_control(messages, tools)

        kwargs: dict[str, Any] = {
            "model": resolved,
            "messages": self._sanitize_messages(
                self._sanitize_empty_content(messages), extra_keys=extra_msg_keys
            ),
            "max_tokens": max(1, max_tokens),
            "temperature": temperature,
        }

        spec = self._gateway or (find_by_name(self._provider_name) if self._provider_name else None)
        if spec and spec.litellm_kwargs:
            kwargs.update(spec.litellm_kwargs)
        if spec and spec.name == "ollama" and self.context_window_tokens:
            kwargs["num_ctx"] = self.context_window_tokens

        self._apply_model_overrides(resolved, kwargs)

        if getattr(self, "_langsmith_enabled", False):
            kwargs.setdefault("callbacks", []).append("langsmith")

        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.extra_headers:
            kwargs["extra_headers"] = self.extra_headers
        if self.request_timeout is not None:
            kwargs["timeout"] = self.request_timeout
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
            kwargs["drop_params"] = True
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"

        try:
            response = await acompletion(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            return LLMResponse(content=f"Error calling LLM: {str(e)}", finish_reason="error")

    # ------------------------------------------------------------------
    # Response parsing (identical for both SDK paths — same attribute names)
    # ------------------------------------------------------------------

    def _parse_response(self, response: Any) -> LLMResponse:
        choice = response.choices[0]
        message = choice.message
        content = message.content
        finish_reason = choice.finish_reason

        # Some providers (e.g. GitHub Copilot) split content and tool_calls
        # across multiple choices. Merge them so tool_calls are not lost.
        raw_tool_calls = []
        for ch in response.choices:
            msg = ch.message
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                raw_tool_calls.extend(msg.tool_calls)
                if ch.finish_reason in ("tool_calls", "stop"):
                    finish_reason = ch.finish_reason
            if not content and msg.content:
                content = msg.content

        if len(response.choices) > 1:
            logger.debug(
                "response has {} choices, merged {} tool_calls",
                len(response.choices),
                len(raw_tool_calls),
            )

        tool_calls = []
        for tc in raw_tool_calls:
            args = tc.function.arguments
            if isinstance(args, str):
                args = json_repair.loads(args)

            provider_specific_fields = getattr(tc, "provider_specific_fields", None) or None
            function_provider_specific_fields = (
                getattr(tc.function, "provider_specific_fields", None) or None
            )

            tool_calls.append(
                ToolCallRequest(
                    id=_short_tool_id(),
                    name=tc.function.name,
                    arguments=args,
                    provider_specific_fields=provider_specific_fields,
                    function_provider_specific_fields=function_provider_specific_fields,
                )
            )

        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        reasoning_content = getattr(message, "reasoning_content", None) or None
        thinking_blocks = getattr(message, "thinking_blocks", None) or None

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason or "stop",
            usage=usage,
            reasoning_content=reasoning_content,
            thinking_blocks=thinking_blocks,
        )

    def get_default_model(self) -> str:
        return self.default_model
