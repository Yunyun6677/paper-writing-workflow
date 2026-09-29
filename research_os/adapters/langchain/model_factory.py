"""Construct a LangChain chat model only when this optional adapter is enabled."""

from __future__ import annotations

from typing import Any

from .base import require_langchain


def create_model(model_id: str, *, injected_model: Any = None, timeout_seconds: int = 900) -> Any:
    if injected_model is not None:
        return injected_model
    if not model_id or ":" not in model_id:
        raise ValueError("LangChain model_id must be explicit as provider:model")
    require_langchain()
    from langchain.chat_models import init_chat_model

    return init_chat_model(model_id, timeout=timeout_seconds)
