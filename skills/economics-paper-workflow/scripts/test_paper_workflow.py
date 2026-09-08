import json
import tempfile
import unittest
from pathlib import Path

from audit_paper import audit
from init_paper_project import initialize


class PaperWorkflowTest(unittest.TestCase):
    def manifest(self, root: Path, stage: str = "design") -> Path:
        data = {
            "schema_version": "economics-paper-project/1.0",
            "project_id": "demo-paper",
            "title_working": "贸易开放与基层治理",
            "paper_type": "empirical",
            "stage": stage,
            "research_question": "贸易开放如何改变农村基层政治参与结构？",
            "target_journals": [{"name": "待定", "family": "chinese_economics"}],
            "contribution_claims": ["连接贸易冲击与基层治理"],
            "research_design": {
                "unit_of_analysis": "村民-年份",
                "treatment_or_exposure": "地区贸易开放暴露",
                "outcomes": ["投票参与", "村民大会参与"],
                "estimand": "开放暴露对参与结果的平均效应",
                "identification_strategy": "待审批的准实验设计",
                "assumptions": ["条件趋势可比"],
                "threats": ["选择性迁移"],
                "inference_plan": "按政策赋值层级聚类"
            },
            "data_sensitivity": "restricted",
            "literature_project_id": None,
            "empirical_run_ids": [],
            "approvals": {"question_and_contribution": True, "research_design": False, "outline_and_journal": False},
            "output_format": "latex"
        }
        path = root / "manifest.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def test_initialize_and_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = initialize(self.manifest(root), root / "projects")
            self.assertTrue((project / "paper" / "main.tex").exists())
            result = audit(project)
            self.assertEqual(result["overall_status"], "review-required")

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.manifest(root)
            initialize(manifest, root / "projects")
            with self.assertRaises(FileExistsError):
                initialize(manifest, root / "projects")

    def test_missing_citation_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = initialize(self.manifest(root), root / "projects")
            section = project / "paper" / "sections" / "01-introduction.tex"
            section.write_text(section.read_text(encoding="utf-8") + "\\citep{missing2026}\n", encoding="utf-8")
            result = audit(project)
            self.assertEqual(result["overall_status"], "blocked")


if __name__ == "__main__":
    unittest.main()
