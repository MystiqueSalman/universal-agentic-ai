"""Model Intelligence Router (Master Prompt v3.0 section 32, Doc 09 precursor).

Provider-independent gateway. Today it speaks to any OpenAI-compatible API
configured purely by environment (OPENAI_API_KEY / OPENAI_BASE_URL /
UAA_MODEL) and falls back cleanly to local behaviour when no provider is
configured or a call fails — the platform never hard-depends on one provider.
Set UAA_DISABLE_LLM=1 to force local mode (used by the test suite).
Usage is metered in-memory for the Server Room / cost tracking.
"""
from __future__ import annotations

import os
import threading

import httpx

_lock = threading.Lock()
_stats = {"calls": 0, "failures": 0, "prompt_chars": 0, "completion_chars": 0, "provider": "local"}


def available() -> bool:
    if os.environ.get("UAA_DISABLE_LLM") == "1":
        return False
    return bool(os.environ.get("OPENAI_API_KEY"))


def provider_name() -> str:
    if not available():
        return "local"
    return os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")


def stats() -> dict:
    with _lock:
        return dict(_stats, available=available())


def chat(system: str, user: str, max_tokens: int = 1200) -> str | None:
    """One chat completion, or None if unavailable/failed (caller falls back)."""
    if not available():
        return None
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("UAA_MODEL", "gpt-4o-mini")
    try:
        with httpx.Client(timeout=45) as client:
            r = client.post(f"{base}/chat/completions",
                            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                            json={"model": model, "max_tokens": max_tokens,
                                  "messages": [{"role": "system", "content": system},
                                               {"role": "user", "content": user}]})
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
        with _lock:
            _stats.update(calls=_stats["calls"] + 1, provider=base,
                          prompt_chars=_stats["prompt_chars"] + len(system) + len(user),
                          completion_chars=_stats["completion_chars"] + len(text))
        return text
    except Exception:
        with _lock:
            _stats["failures"] += 1
        return None
