#!/usr/bin/env python3
"""Render an evidence-traceable literature-map JSON file as a readable SVG."""

from __future__ import annotations

import argparse
import json
import math
import textwrap
from html import escape
from pathlib import Path


COLORS = {
    "established": ("#E8F3EC", "#347A52"),
    "contested": ("#FCE9E7", "#B84A3A"),
    "gap": ("#FFF4D6", "#B98216"),
    "proposed": ("#EAE8FA", "#6557B2"),
}


def wrapped(label: str, width: int = 16) -> list[str]:
    lines = textwrap.wrap(label, width=width, break_long_words=True, break_on_hyphens=False)
    return lines[:4] or [label]


def validate(graph: dict) -> None:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if len(nodes) < 3 or len(edges) < 2:
        raise ValueError("A literature map requires at least 3 nodes and 2 edges")
    node_ids = [node.get("id") for node in nodes]
    if None in node_ids or len(node_ids) != len(set(node_ids)):
        raise ValueError("Node IDs must be present and unique")
    known = set(node_ids)
    for edge in edges:
        if edge.get("source") not in known or edge.get("target") not in known:
            raise ValueError(f"Edge references an unknown node: {edge.get('id')}")
        if edge.get("evidence_status") != "inferred" and not edge.get("record_ids"):
            raise ValueError(f"Direct or synthesized edge lacks evidence: {edge.get('id')}")
        if not edge.get("rationale"):
            raise ValueError(f"Edge lacks rationale: {edge.get('id')}")


def render(graph: dict) -> str:
    validate(graph)
    nodes = graph["nodes"]
    edges = graph["edges"]
    lane_values = sorted({int(node["lane"]) for node in nodes})
    lane_index = {lane: index for index, lane in enumerate(lane_values)}
    grouped = {lane: [] for lane in lane_values}
    for node in nodes:
        grouped[int(node["lane"])].append(node)

    box_w, box_h = 220, 96
    x_gap, y_gap = 70, 34
    margin_x, margin_y = 55, 115
    max_rows = max(len(values) for values in grouped.values())
    width = margin_x * 2 + len(lane_values) * box_w + max(0, len(lane_values) - 1) * x_gap
    height = margin_y + max_rows * box_h + max(0, max_rows - 1) * y_gap + 120

    positions: dict[str, tuple[float, float]] = {}
    for lane, values in grouped.items():
        x = margin_x + lane_index[lane] * (box_w + x_gap)
        total_h = len(values) * box_h + max(0, len(values) - 1) * y_gap
        start_y = margin_y + max(0, (max_rows * box_h + (max_rows - 1) * y_gap - total_h) / 2)
        for row, node in enumerate(values):
            positions[node["id"]] = (x, start_y + row * (box_h + y_gap))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<defs><marker id="arrow" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto"><polygon points="0 0, 9 3.5, 0 7" fill="#667085"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        f'<text x="{margin_x}" y="38" font-family="Segoe UI, Microsoft YaHei, sans-serif" font-size="22" font-weight="700" fill="#17212B">{escape(graph.get("research_question", "Literature map"))}</text>',
        f'<text x="{margin_x}" y="66" font-family="Segoe UI, Microsoft YaHei, sans-serif" font-size="13" fill="#52606D">{escape(graph.get("caption", ""))}</text>',
    ]

    for edge in edges:
        sx, sy = positions[edge["source"]]
        tx, ty = positions[edge["target"]]
        start_x, start_y = sx + box_w, sy + box_h / 2
        end_x, end_y = tx, ty + box_h / 2
        if tx <= sx:
            start_x, end_x = sx + box_w / 2, tx + box_w / 2
            start_y, end_y = sy + box_h, ty
        mid_x = (start_x + end_x) / 2
        dash = ' stroke-dasharray="7 5"' if edge.get("evidence_status") == "inferred" else ""
        parts.append(
            f'<path d="M {start_x:.1f} {start_y:.1f} C {mid_x:.1f} {start_y:.1f}, {mid_x:.1f} {end_y:.1f}, {end_x:.1f} {end_y:.1f}" fill="none" stroke="#667085" stroke-width="1.7"{dash} marker-end="url(#arrow)"/>'
        )
        label_x = mid_x
        label_y = (start_y + end_y) / 2 - 5
        parts.append(
            f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="middle" font-family="Segoe UI, Microsoft YaHei, sans-serif" font-size="11" fill="#475467">{escape(edge["relation"])}</text>'
        )

    for node in nodes:
        x, y = positions[node["id"]]
        fill, stroke = COLORS.get(node.get("status", "established"), COLORS["established"])
        parts.append(f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="1.8"/>')
        parts.append(f'<text x="{x + 12}" y="{y + 19}" font-family="Segoe UI, Microsoft YaHei, sans-serif" font-size="10" font-weight="700" fill="{stroke}">{escape(node["type"].upper())} · {escape(node["id"])}</text>')
        for index, line in enumerate(wrapped(node["label"])):
            parts.append(f'<text x="{x + 12}" y="{y + 43 + index * 16}" font-family="Segoe UI, Microsoft YaHei, sans-serif" font-size="13" fill="#17212B">{escape(line)}</text>')

    legend_y = height - 56
    legend = [("established", "已建立"), ("contested", "争议"), ("gap", "缺口"), ("proposed", "拟议创新")]
    for index, (status, label) in enumerate(legend):
        fill, stroke = COLORS[status]
        x = margin_x + index * 150
        parts.append(f'<rect x="{x}" y="{legend_y}" width="18" height="18" rx="4" fill="{fill}" stroke="{stroke}"/>')
        parts.append(f'<text x="{x + 26}" y="{legend_y + 14}" font-family="Segoe UI, Microsoft YaHei, sans-serif" font-size="12" fill="#344054">{label}</text>')
    parts.append(f'<text x="{width - margin_x}" y="{legend_y + 14}" text-anchor="end" font-family="Segoe UI, Microsoft YaHei, sans-serif" font-size="11" fill="#667085">实线：直接/综合证据　虚线：综述推断</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_json")
    parser.add_argument("output_svg")
    args = parser.parse_args()
    source = Path(args.input_json)
    target = Path(args.output_svg)
    graph = json.loads(source.read_text(encoding="utf-8"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(graph), encoding="utf-8")
    print(json.dumps({"status": "rendered", "nodes": len(graph["nodes"]), "edges": len(graph["edges"]), "output": str(target)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
