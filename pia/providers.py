"""Pluggable LLM providers.

Two adapters cover most models: the Anthropic SDK, and any OpenAI-compatible
chat completions API (OpenAI, Gemini, Ollama, LM Studio, vLLM, OpenRouter, ...).
"""

import os
from dataclasses import dataclass
from typing import Protocol

MAX_OUTPUT_TOKENS = 4096


class LLMError(RuntimeError):
    pass


class Provider(Protocol):
    name: str
    model: str

    def complete(self, system: str, user: str) -> str: ...


@dataclass(frozen=True)
class ProviderSpec:
    kind: str  # "anthropic" or "openai"
    default_model: str | None
    key_env: str | None
    base_url: str | None = None


PROVIDERS: dict[str, ProviderSpec] = {
    "anthropic": ProviderSpec("anthropic", "claude-sonnet-5-5", "ANTHROPIC_API_KEY"),
    "openai": ProviderSpec("openai", "gpt-4.1-mini", "OPENAI_API_KEY"),
    "gemini": ProviderSpec(
        "openai", "gemini-2.5-flash", "GEMINI_API_KEY",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
    ),
    "ollama": ProviderSpec("openai", "llama3.1", None, "http://localhost:11434/v1"),
    # Any other OpenAI-compatible endpoint; needs --base-url and --model.
    "openai-compatible": ProviderSpec("openai", None, "OPENAI_API_KEY"),
}


def detect_provider() -> str | None:
    """Pick a provider from whichever API key is present in the environment."""
    for name in ("anthropic", "openai", "gemini"):
        if os.environ.get(PROVIDERS[name].key_env):
            return name
    return None


class AnthropicProvider:
    def __init__(self, model: str, api_key: str, base_url: str | None = None):
        try:
            import anthropic
        except ImportError:
            raise LLMError("The 'anthropic' package is required: pip install anthropic") from None
        self.name, self.model = "anthropic", model
        self._client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
        self._errors = anthropic.APIError

    def complete(self, system: str, user: str) -> str:
        try:
            msg = self._client.messages.create(
                model=self.model,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except self._errors as e:
            raise LLMError(f"Anthropic API error: {e}") from e
        if msg.stop_reason == "max_tokens":
            raise LLMError("Model response was cut off (max_tokens reached)")
        return "".join(block.text for block in msg.content if block.type == "text")


class OpenAICompatibleProvider:
    def __init__(self, name: str, model: str, api_key: str | None, base_url: str | None):
        try:
            import openai
        except ImportError:
            raise LLMError("The 'openai' package is required: pip install openai") from None
        self.name, self.model = name, model
        # Local servers such as Ollama ignore the key, but the SDK requires one.
        self._client = openai.OpenAI(api_key=api_key or "not-needed", base_url=base_url)
        self._errors = openai.OpenAIError

    def complete(self, system: str, user: str) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                # No max_tokens: newer OpenAI models reject it in favour of max_completion_tokens.
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except self._errors as e:
            raise LLMError(f"{self.name} API error: {e}") from e
        choice = resp.choices[0]
        if choice.finish_reason == "length":
            raise LLMError("Model response was cut off (output token limit reached)")
        return choice.message.content or ""


def get_provider(name: str, model: str | None = None, base_url: str | None = None) -> Provider:
    spec = PROVIDERS.get(name)
    if spec is None:
        raise LLMError(f"Unknown provider '{name}'. Choose from: {', '.join(PROVIDERS)}")

    model = model or spec.default_model
    base_url = base_url or spec.base_url
    if not model:
        raise LLMError(f"Provider '{name}' needs --model")
    if name == "openai-compatible" and not base_url:
        raise LLMError("Provider 'openai-compatible' needs --base-url")

    api_key = os.environ.get(spec.key_env) if spec.key_env else None
    # A custom base URL may point at a server that needs no key.
    if spec.key_env and not api_key and name != "openai-compatible":
        raise LLMError(f"Set the {spec.key_env} environment variable to use provider '{name}'")

    if spec.kind == "anthropic":
        return AnthropicProvider(model, api_key, base_url)
    return OpenAICompatibleProvider(name, model, api_key, base_url)
