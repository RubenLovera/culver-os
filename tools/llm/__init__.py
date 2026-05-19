"""
tools/llm — LLM-agnostic wrapper for CulverOS.

Usage:
    from tools.llm import call_llm

    response = call_llm(
        prompt="Summarize this article: ...",
        provider="gemini",          # or "claude" / "openai"
        model="gemini-2.5-flash",   # provider-specific model name
        key="YOUR_API_KEY",
    )

Provider is resolved from LLM_PROVIDER env var if not passed explicitly.
"""

import os
from typing import Optional


def call_llm(
    prompt: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    key: Optional[str] = None,
) -> str:
    """
    Call the configured LLM and return the text response.

    Falls back to env vars:
        LLM_PROVIDER  (gemini | claude | openai)
        LLM_MODEL     (provider-specific model name)
        LLM_API_KEY   (API key for the provider)
    """
    provider = provider or os.environ.get("LLM_PROVIDER", "gemini")
    model = model or os.environ.get("LLM_MODEL")
    key = key or os.environ.get("LLM_API_KEY")

    if not key:
        raise EnvironmentError("LLM_API_KEY not set in environment")

    if provider == "gemini":
        from tools.llm.gemini import call_llm as _call
    elif provider == "claude":
        from tools.llm.claude import call_llm as _call
    elif provider == "openai":
        from tools.llm.openai import call_llm as _call
    else:
        raise ValueError(f"Unknown LLM provider: '{provider}'. Supported: gemini, claude, openai")

    return _call(prompt=prompt, model=model, key=key)
