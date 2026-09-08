#!/usr/bin/env python3
"""Create a non-overwriting economics paper project from a validated manifest."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "schemas" / "economics-paper-project.schema.json"


def latex_escape(value: str) -> str:
    table = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    }
    return "".join(table.get(ch, ch) for ch in value)


def load_and_validate(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(manifest)
    return manifest


def initialize(manifest_path: Path, output_root: Path) -> Path:
    manifest = load_and_validate(manifest_path)
    project_dir = output_root.resolve() / manifest["project_id"]
    if project_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing project: {project_dir}")

    dirs = [
        "literature", "design", "analysis", "paper/sections", "paper/tables",
        "paper/figures", "paper/appendix", "audit", "submission",
    ]
    for rel in dirs:
        (project_dir / rel).mkdir(parents=True, exist_ok=False)

    shutil.copy2(manifest_path, project_dir / "project.json")
    design = {
        "schema_version": "design-register/1.0",
        "project_id": manifest["project_id"],
        "paper_type": manifest["paper_type"],
        "research_question": manifest["research_question"],
        "research_design": manifest.get("research_design"),
        "approval": manifest["approvals"]["research_design"],
        "changes": [],
    }
    (project_dir / "design" / "design-register.json").write_text(
        json.dumps(design, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (project_dir / "design" / "research-design.tex").write_text(
        "\\section*{研究设计登记}\n"
        f"研究问题：{latex_escape(manifest['research_question'])}\\par\n"
        "% TODO: 从 design-register.json 生成并经研究者确认；不得据结果反向改写。\n",
        encoding="utf-8",
    )
    claims = {"schema_version": "numeric-claims/1.0", "claims": []}
    (project_dir / "audit" / "numeric-claims.json").write_text(
        json.dumps(claims, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    checkpoints = {
        "schema_version": "paper-checkpoints/1.0",
        "project_id": manifest["project_id"],
        "stages": {stage: "pending" for stage in ["frame", "design", "evidence", "analysis", "outline", "draft", "audit", "revision", "package"]},
    }
    (project_dir / "audit" / "checkpoints.json").write_text(
        json.dumps(checkpoints, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    sections = [
        ("01-introduction.tex", "引言"), ("02-literature.tex", "文献与贡献"),
        ("03-framework.tex", "理论与研究假说"), ("04-data-design.tex", "数据与研究设计"),
        ("05-results.tex", "实证结果"), ("06-robustness.tex", "稳健性与扩展分析"),
        ("07-conclusion.tex", "结论与启示"),
    ]
    for filename, heading in sections:
        (project_dir / "paper" / "sections" / filename).write_text(
            f"\\section{{{heading}}}\n% TODO: 仅写入已核验的证据与可追溯结果。\n", encoding="utf-8"
        )
    inputs = "\n".join(f"\\input{{sections/{name}}}" for name, _ in sections)
    title = latex_escape(manifest["title_working"])
    main = f"""\\documentclass[UTF8]{{ctexart}}
\\usepackage[a4paper,margin=2.5cm]{{geometry}}
\\usepackage{{booktabs,graphicx,amsmath,hyperref,natbib}}
\\title{{{title}}}
\\author{{}}
\\date{{}}
\\begin{{document}}
\\maketitle
\\begin{{abstract}}
% TODO: 研究问题、设计、主要发现、贡献；数字必须来自结果文件。
\\end{{abstract}}
{inputs}
\\bibliographystyle{{plainnat}}
\\bibliography{{references}}
\\end{{document}}
"""
    (project_dir / "paper" / "main.tex").write_text(main, encoding="utf-8")
    (project_dir / "paper" / "references.bib").write_text("", encoding="utf-8")
    (project_dir / "paper" / "revision-log.tex").write_text(
        "\\section*{修订记录}\n% 记录变更、理由、证据和批准状态。\n", encoding="utf-8"
    )
    (project_dir / "submission" / "submission-checklist.tex").write_text(
        "\\section*{投稿检查清单}\n"
        "\\begin{itemize}\n"
        "\\item[$\\square$] 目标期刊最新格式已核验。\n"
        "\\item[$\\square$] 引用、数字、表图和附录审计通过。\n"
        "\\item[$\\square$] 数据与代码可得性声明已完成。\n"
        "\\item[$\\square$] 隐私、许可、匿名化和利益冲突已检查。\n"
        "\\end{itemize}\n", encoding="utf-8"
    )
    (project_dir / "submission" / "data-code-availability.tex").write_text(
        "\\section*{数据与代码可得性声明}\n% 按真实授权、隐私和复现条件填写。\n", encoding="utf-8"
    )
    reproducibility = {
        "schema_version": "reproducibility-manifest/1.0",
        "project_id": manifest["project_id"],
        "status": "pending",
        "source_artifacts": [],
        "generated_artifacts": [],
        "software_environments": [],
        "restrictions": [],
    }
    (project_dir / "submission" / "reproducibility-manifest.json").write_text(
        json.dumps(reproducibility, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return project_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = initialize(args.manifest, args.output_root)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
