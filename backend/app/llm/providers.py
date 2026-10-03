"""Pluggable LLM providers.

Groq, OpenAI, Gemini and Ollama all expose OpenAI-compatible /chat/completions endpoints,
so a single client class covers them; only base_url, key and default model differ.
`mock` streams an extractive answer from the context and needs no network: used in tests
and as a safe fallback so the app works before any key is configured.
"""
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass

from ..config import get_settings


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    base_url: str | None
    api_key: str
    default_model: str
    needs_key: bool = True

    @property
    def configured(self) -> bool:
        return bool(self.api_key) or not self.needs_key


def provider_specs() -> dict[str, ProviderSpec]:
    s = get_settings()
    return {
        "groq": ProviderSpec("groq", "https://api.groq.com/openai/v1", s.groq_api_key, s.groq_model),
        "openai": ProviderSpec("openai", None, s.openai_api_key, s.openai_model),
        "gemini": ProviderSpec("gemini", "https://generativelanguage.googleapis.com/v1beta/openai/",
                               s.gemini_api_key, s.gemini_model),
        "ollama": ProviderSpec("ollama", s.ollama_base_url, "ollama", s.ollama_model, needs_key=False),
        "mock": ProviderSpec("mock", None, "", "mock-extractive", needs_key=False),
    }


class ProviderError(RuntimeError):
    pass


# gpt-oss cites as 【1】 or 【1†L1-L3】; normalise to the [1] style the UI and widget expect.
_CITATION = re.compile(r"【([^】]*)】|\[(\d+)†[^\]]*\]")


def _fix_citation(m: re.Match) -> str:
    inner = m.group(1) if m.group(1) is not None else m.group(2)
    n = re.match(r"\s*(\d+)", inner)
    return f"[{n.group(1)}]" if n else f"[{inner}]"


def clean_citations(deltas: Iterator[str]) -> Iterator[str]:
    """Rewrite citations even when one is split across streamed deltas: text from an unclosed
    bracket is held back (at most ~40 chars) until it closes."""
    pending = ""
    for d in deltas:
        pending += d
        cut = max(pending.rfind("【"), pending.rfind("["))
        held = cut != -1 and "】" not in pending[cut:] and "]" not in pending[cut:] and len(pending) - cut < 40
        ready, pending = (pending[:cut], pending[cut:]) if held else (pending, "")
        if ready:
            yield _CITATION.sub(_fix_citation, ready)
    if pending:
        yield _CITATION.sub(_fix_citation, pending)


def resolve(provider: str | None, model: str | None) -> tuple[ProviderSpec, str]:
    specs = provider_specs()
    name = provider or get_settings().default_llm_provider
    spec = specs.get(name)
    if spec is None:
        raise ProviderError(f"unknown provider '{name}'")
    if not spec.configured:
        raise ProviderError(f"provider '{name}' has no API key: set {name.upper()}_API_KEY in .env")
    return spec, (model or spec.default_model)


def stream_chat(spec: ProviderSpec, model: str, messages: list[dict]) -> Iterator[str]:
    """Yield text deltas."""
    if spec.name == "mock":
        yield from _mock_stream(messages)
        return
    from openai import OpenAI, OpenAIError

    client = OpenAI(api_key=spec.api_key, base_url=spec.base_url, timeout=60, max_retries=1)
    # gpt-oss models reason before answering; "low" keeps that (and first-token latency) short on Groq.
    extra = {"reasoning_effort": "low"} if spec.name == "groq" and "gpt-oss" in model else None
    try:
        stream = client.chat.completions.create(
            model=model, messages=messages, stream=True, temperature=0.2, max_tokens=800,
            extra_body=extra)
        yield from clean_citations(
            e.choices[0].delta.content for e in stream
            if e.choices and e.choices[0].delta and e.choices[0].delta.content)
    except OpenAIError as e:
        raise ProviderError(f"{spec.name}: {getattr(e, 'message', None) or e}") from e


def complete(spec: ProviderSpec, model: str, messages: list[dict], max_tokens: int = 300) -> str:
    """One short non-streamed completion (used for query rewriting)."""
    if spec.name == "mock":  # offline: echo the latest user message
        return messages[-1]["content"].rsplit("Latest message:", 1)[-1].strip()
    from openai import OpenAI, OpenAIError

    client = OpenAI(api_key=spec.api_key, base_url=spec.base_url, timeout=20, max_retries=0)
    extra = {"reasoning_effort": "low"} if spec.name == "groq" and "gpt-oss" in model else None
    try:
        r = client.chat.completions.create(model=model, messages=messages, temperature=0, max_tokens=max_tokens,
                                           extra_body=extra)
        return (r.choices[0].message.content or "").strip()
    except OpenAIError as e:
        raise ProviderError(f"{spec.name}: {getattr(e, 'message', None) or e}") from e


def _mock_stream(messages: list[dict]) -> Iterator[str]:
    """Answer with the context sentences that best overlap the question."""
    system = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
    question = messages[-1]["content"]
    ctx = system.rsplit("<context>", 1)[-1].split("</context>", 1)[0] if "<context>" in system else ""  # the prompt itself mentions <context>
    qwords = {w for w in re.findall(r"\w+", question.lower()) if len(w) > 3}
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", ctx)
             if s.strip() and not s.startswith("[")]
    ranked = sorted(sents, key=lambda s: -len(qwords & set(re.findall(r"\w+", s.lower()))))
    best = [s for s in ranked[:2] if qwords & set(re.findall(r"\w+", s.lower()))]
    answer = ("(mock) " + " ".join(best)) if best else "(mock) I couldn't find that in the documents."
    for tok in re.findall(r"\S+\s*", answer):
        time.sleep(0.005)
        yield tok
