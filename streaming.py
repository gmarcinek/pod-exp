from __future__ import annotations

import os

import anthropic
import openai

from client import OLLAMA_DEFAULT_BASE_URL
from config import PROVIDER_MAX_TOKENS


def _stream_openai(
    system_prompt: str,
    messages: list[dict],
    model: str,
    thinking_effort: str | None = None,
    max_tokens: int | None = None,
    response_format: dict | None = None,
):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("Brak OPENAI_API_KEY.")
    params: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "stream": True,
    }
    if thinking_effort:
        params["reasoning_effort"] = thinking_effort
    if max_tokens:
        params["max_completion_tokens"] = max_tokens
    if response_format:
        params["response_format"] = response_format
    full = ""
    for chunk in openai.OpenAI(api_key=api_key).chat.completions.create(**params):
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if rc := getattr(delta, "reasoning_content", None):
            yield {"type": "thinking", "delta": rc}
        if delta.content:
            full += delta.content
            yield {"type": "text", "delta": delta.content}
    yield {"type": "done", "content": full}


def _stream_anthropic(
    system_prompt: str,
    messages: list[dict],
    model: str,
    thinking_effort: str | None = None,
    max_tokens: int | None = 4096,
    prefill: str | None = None,
):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("Brak ANTHROPIC_API_KEY.")
    clean = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m["role"] in ("user", "assistant")
    ]
    if prefill:
        clean.append({"role": "assistant", "content": prefill})
    if max_tokens is None:
        max_tokens = PROVIDER_MAX_TOKENS["anthropic"]
    params: dict = {"model": model, "max_tokens": max_tokens, "system": system_prompt, "messages": clean}
    if thinking_effort:
        budget = {"auto": 8000, "medium": 5000, "high": 10000, "low": 2000}.get(thinking_effort, 5000)
        params["thinking"] = {"type": "enabled", "budget_tokens": budget}
        params["max_tokens"] = max(params["max_tokens"], budget + 1000)
    full = prefill or ""
    if prefill:
        yield {"type": "text", "delta": prefill}
    with anthropic.Anthropic(api_key=api_key).messages.stream(**params) as stream:
        for event in stream:
            if getattr(event, "type", None) == "content_block_delta":
                d = event.delta
                if getattr(d, "type", None) == "thinking_delta":
                    yield {"type": "thinking", "delta": d.thinking}
                elif getattr(d, "type", None) == "text_delta":
                    full += d.text
                    yield {"type": "text", "delta": d.text}
    yield {"type": "done", "content": full}


def _stream_ollama(
    system_prompt: str,
    messages: list[dict],
    model: str,
    thinking_effort: str | None = None,
    max_tokens: int | None = None,
    response_format: dict | None = None,
):
    base_url = os.environ.get("OLLAMA_BASE_URL", OLLAMA_DEFAULT_BASE_URL)
    params: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "stream": True,
    }
    if max_tokens:
        params["max_tokens"] = max_tokens
    if response_format:
        params["response_format"] = response_format
    full = ""
    for chunk in openai.OpenAI(api_key="ollama", base_url=base_url).chat.completions.create(**params):
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta.content:
            full += delta.content
            yield {"type": "text", "delta": delta.content}
    yield {"type": "done", "content": full}


def _streamer(provider: str):
    if provider == "anthropic":
        return _stream_anthropic
    if provider == "ollama":
        return _stream_ollama
    return _stream_openai
