"""Construct a LangChain chat model only when this optional adapter is enabled."""

from __future__ import annotations

import os
from urllib.parse import urlparse
from typing import Any

from .base import require_langchain


def create_model(model_id: str, *, injected_model: Any = None, timeout_seconds: int = 900) -> Any:
    if injected_model is not None:
        return injected_model
    if model_id == "openai-compatible":
        endpoint = os.environ.get("RESEARCH_OS_MODEL_BASE_URL", "").rstrip("/")
        model = os.environ.get("RESEARCH_OS_MODEL_NAME", "")
        key = os.environ.get("RESEARCH_OS_MODEL_API_KEY", "")
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("RESEARCH_OS_MODEL_BASE_URL must be a clean HTTPS endpoint")
        if not model or not key:
            raise ValueError("RESEARCH_OS_MODEL_NAME and RESEARCH_OS_MODEL_API_KEY are required")
        require_langchain()
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError("Install requirements-langchain.txt for the OpenAI-compatible model") from exc
        return ChatOpenAI(model=model, api_key=key, base_url=endpoint,
                          timeout=timeout_seconds, max_retries=1)
    if not model_id or ":" not in model_id:
        raise ValueError("LangChain model_id must be explicit as provider:model")
    require_langchain()
    from langchain.chat_models import init_chat_model

    return init_chat_model(model_id, timeout=timeout_seconds)
