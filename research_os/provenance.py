"""Portable scientific data-chain records and backward tracing."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema

from .store import atomic_json, canonical_hash, sha256_file, utc_now


NODE_TYPES = {
    "RawDataset", "Transformation", "AnalysisDataset", "Code", "ModelRun",
    "Estimate", "TableFigure", "NumericClaim", "ManuscriptClaim",
}


@dataclass
class ProvenanceGraph:
    project_id: str
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    edges: list[dict[str, str]] = field(default_factory=list)

    def add_file_node(self, node_id: str, node_type: str, path: str | Path,
                      project_root: str | Path, **metadata: Any) -> None:
        if node_type not in NODE_TYPES:
            raise ValueError(f"Unsupported provenance node type: {node_type}")
        root, target = Path(project_root).resolve(), Path(path).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError("Provenance file must exist below the project root")
        self.nodes[node_id] = {
            "node_id": node_id, "node_type": node_type,
            "path": target.relative_to(root).as_posix(), "sha256": sha256_file(target),
            "metadata": metadata,
        }

    def add_value_node(self, node_id: str, node_type: str, **metadata: Any) -> None:
        if node_type not in NODE_TYPES:
            raise ValueError(f"Unsupported provenance node type: {node_type}")
        self.nodes[node_id] = {
            "node_id": node_id, "node_type": node_type,
            "value_hash": canonical_hash(metadata), "metadata": metadata,
        }

    def relate(self, source: str, predicate: str, target: str) -> None:
        if source not in self.nodes or target not in self.nodes:
            raise KeyError("Provenance relation endpoints must already exist")
        edge = {"source": source, "predicate": predicate, "target": target}
        if edge not in self.edges:
            self.edges.append(edge)

    def trace(self, node_id: str) -> dict[str, Any]:
        if node_id not in self.nodes:
            raise KeyError(node_id)
        visited: set[str] = set()
        ordered: list[str] = []

        def walk(current: str) -> None:
            if current in visited:
                return
            visited.add(current); ordered.append(current)
            for edge in self.edges:
                if edge["source"] == current:
                    walk(edge["target"])

        walk(node_id)
        return {
            "start_node": node_id,
            "nodes": [self.nodes[value] for value in ordered],
            "edges": [edge for edge in self.edges if edge["source"] in visited and edge["target"] in visited],
            "reaches_raw_dataset": any(self.nodes[value]["node_type"] == "RawDataset" for value in visited),
        }

    def document(self) -> dict[str, Any]:
        value = {
            "schema_version": "provenance-chain/1.0", "project_id": self.project_id,
            "created_at": utc_now(), "nodes": list(self.nodes.values()), "edges": self.edges,
        }
        value["graph_hash"] = canonical_hash(value)
        return value

    def write(self, output: str | Path, schema: str | Path | None = None) -> dict[str, Any]:
        value = self.document()
        if schema is not None:
            jsonschema.Draft202012Validator(json.loads(Path(schema).read_text(encoding="utf-8"))).validate(value)
        atomic_json(Path(output), value)
        return value


def verify_analysis_chain(project_root: str | Path, request: dict[str, Any]) -> dict[str, Any]:
    """Recompute the minimal dataset-code-run-result-report chain."""
    root = Path(project_root).resolve()

    def checked(relative: str, expected: str | None = None) -> Path:
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise FileNotFoundError(relative)
        digest = sha256_file(path)
        if expected and digest != expected:
            raise ValueError(f"hash mismatch: {relative}")
        return path

    dataset = checked(request["dataset_artifact"], request.get("dataset_sha256"))
    code = checked(request["code_artifact"], request.get("code_sha256"))
    result_path = checked(request["result_artifact"], request.get("result_sha256"))
    receipt_path = checked(request["execution_receipt"], request.get("execution_receipt_sha256"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    expected = request["expected"]
    tolerance = float(expected.get("tolerance", 1e-9))
    result_inputs = {item["path"]: item["sha256"] for item in receipt.get("inputs", [])}
    result_outputs = {item["path"]: item["sha256"] for item in receipt.get("artifacts", [])}
    checks = {
        "execution_complete": receipt.get("status") == "complete" and receipt.get("tool") == "python",
        "dataset_bound_to_run": result_inputs.get(request["dataset_artifact"]) == sha256_file(dataset),
        "code_bound_to_run": result_inputs.get(request["code_artifact"]) == sha256_file(code),
        "result_bound_to_run": result_outputs.get(request["result_artifact"]) == sha256_file(result_path),
        "result_dataset_hash": result.get("dataset_sha256") == sha256_file(dataset),
        "result_code_hash": result.get("code_sha256") == sha256_file(code),
        "sample_match": int(result.get("n", -1)) == int(expected["n"]),
        "coefficient_match": abs(float(result.get("coefficient")) - float(expected["coefficient"])) <= tolerance,
    }
    report_path = None
    if request.get("report_artifact"):
        report_path = checked(request["report_artifact"], request.get("report_sha256"))
        report = report_path.read_text(encoding="utf-8", errors="replace")
        checks["report_contains_verified_value"] = expected["report_value"] in report
    return {
        "schema_version": "analysis-chain-verification/1.0",
        "status": "pass" if all(checks.values()) else "blocked",
        "checks": checks,
        "input_hashes": {
            "dataset": sha256_file(dataset), "code": sha256_file(code),
            "result": sha256_file(result_path), "execution_receipt": sha256_file(receipt_path),
            **({"report": sha256_file(report_path)} if report_path else {}),
        },
        "verified_values": {"n": result.get("n"), "coefficient": result.get("coefficient")},
        "timestamp": utc_now(),
    }
