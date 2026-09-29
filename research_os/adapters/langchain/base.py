"""Small boundary around optional LangChain installation and injected runners."""

from __future__ import annotations

from typing import Any, Callable, Protocol

ToolRunner = Callable[[str, dict[str, Any], str], dict[str, Any]]


class AgentHarness(Protocol):
    def invoke(self, inputs: dict[str, Any], *, config: dict[str, Any]) -> dict[str, Any]: ...


def require_langchain() -> None:
    try:
        import langchain  # noqa: F401
        import langchain_core  # noqa: F401
        import pydantic  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("LangChain adapter is optional; install requirements-langchain.txt") from exc
