"""Provider-neutral model boundary; no network call occurs without an injected transport."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

import jsonschema


@dataclass(frozen=True)
class ProviderRequest:
    agent: str
    model: str
    instructions: str
    input_artifacts: list[dict[str, Any]] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    data_sensitivity: str = "restricted"
    external_content_approved: bool = False


@dataclass(frozen=True)
class ProviderObservation:
    outcome: str
    model: str
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)
    summary: str = ""


class ProviderAdapter(Protocol):
    provider_id: str
    def execute(self, request: ProviderRequest) -> ProviderObservation: ...


class OpenAICompatibleAdapter:
    """Small adapter for OpenAI-compatible transports, including local servers.

    The transport is dependency-injected so the core owns neither credentials nor
    a provider SDK. Callers must enforce the project's sensitivity policy before
    supplying any content beyond artifact references.
    """
    def __init__(self, provider_id: str, transport: Callable[[dict[str, Any]], dict[str, Any]], *, is_local: bool = False):
        self.provider_id = provider_id
        self.transport = transport
        self.is_local = is_local

    def execute(self, request: ProviderRequest) -> ProviderObservation:
        if request.data_sensitivity in {"restricted", "personal", "confidential"} and not (self.is_local or request.external_content_approved):
            raise PermissionError("Sensitive research content requires an explicit external-provider approval")
        payload = {
            "model": request.model,
            "instructions": request.instructions,
            "input_artifacts": request.input_artifacts,
            "tools": request.allowed_tools,
            "metadata": {**request.metadata, "agent": request.agent, "data_sensitivity": request.data_sensitivity},
        }
        raw = self.transport(payload)
        return ProviderObservation(
            outcome=raw["outcome"], model=raw.get("model", request.model),
            artifacts=raw.get("artifacts", []), tool_calls=raw.get("tool_calls", []),
            token_usage=raw.get("token_usage", {}), summary=raw.get("summary", ""),
        )


class ProviderRegistry:
    def __init__(self, repository_root: str | Path):
        root = Path(repository_root)
        registry = json.loads((root / "config/providers.json").read_text(encoding="utf-8"))
        schema = json.loads((root / "schemas/provider-adapter.schema.json").read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        for provider in registry["providers"]:
            validator.validate(provider)
        self.config = registry
        self.adapters: dict[str, ProviderAdapter] = {}

    def register(self, adapter: ProviderAdapter) -> None:
        configured = {item["provider_id"] for item in self.config["providers"]}
        if adapter.provider_id not in configured:
            raise KeyError(f"Provider is not declared in config/providers.json: {adapter.provider_id}")
        self.adapters[adapter.provider_id] = adapter

    def get(self, provider_id: str) -> ProviderAdapter:
        if provider_id not in self.adapters:
            raise RuntimeError(f"Provider adapter is not active: {provider_id}")
        return self.adapters[provider_id]
