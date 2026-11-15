"""Synthetic review records test the gate, not whether prose sounds like Guage."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from review_style import blocks, review_template, validate_review


ARTICLE = "# 整理记录\n\n## 过程\n\n今天完成了整理。\n"


def reviewed_fixture(draft, final):
    """Only synthetic tests may mark every check passed without editorial work."""
    record = review_template(draft, final)
    for row in record["blocks"]:
        row.update(status="pass", reason="合成测试：确认该块的表达与证据边界")
    for row in record["voice_checks"]:
        row.update(status="pass", evidence=blocks(final)[-1], reason="合成测试：定位终稿中的审校证据")
    record["handbook_iteration"] = {"decision": "unchanged", "basis": "合成测试没有用户风格反馈，不形成个人偏好"}
    if draft != final:
        record["findings"] = [{"before": draft.strip(), "after": final.strip(), "action": "rewrite",
                               "status": "resolved", "reason": "合成测试：整段替换"}]
    return record


class ReviewTests(unittest.TestCase):
    def test_template_cannot_pass_and_no_edit_quota(self):
        self.assertTrue(validate_review(ARTICLE, ARTICLE, review_template(ARTICLE, ARTICLE)))
        self.assertEqual(validate_review(ARTICLE, ARTICLE, reviewed_fixture(ARTICLE, ARTICLE)), [])

    def test_all_findings_must_be_resolved_without_a_count_limit(self):
        draft = "\n\n".join(f"原句{i}。" for i in range(8))
        final = "\n\n".join(f"改写{i}。" for i in range(8))
        record = reviewed_fixture(draft, final)
        record["findings"] = [{"before": f"原句{i}。", "after": f"改写{i}。", "action": "rewrite",
                               "status": "resolved", "reason": "合成测试：处理具体问题"} for i in range(8)]
        self.assertEqual(validate_review(draft, final, record), [])
        record["findings"][-1]["status"] = "pending"
        self.assertTrue(validate_review(draft, final, record))

    def test_rejects_stale_drafts_rules_and_partial_coverage(self):
        mutations = [
            lambda r: r.update(draft_sha256="stale"),
            lambda r: r.update(final_sha256="stale"),
            lambda r: r["rules_sha256"].update({"style-guide.md": "stale"}),
            lambda r: r["blocks"].pop(),
            lambda r: r["blocks"][0].update(status="pending"),
            lambda r: r["blocks"][0].update(reason=""),
            lambda r: r["blocks"][0].update(index=2),
            lambda r: r["voice_checks"].pop(),
            lambda r: r["voice_checks"][0].update(evidence="不存在的引文"),
            lambda r: r["voice_checks"][0].update(reason=""),
            lambda r: r["voice_checks"][0].update(id="rhythm"),
            lambda r: r["handbook_iteration"].update(decision="pending"),
        ]
        for change in mutations:
            record = reviewed_fixture(ARTICLE, ARTICLE)
            change(record)
            with self.subTest(record=record):
                self.assertTrue(validate_review(ARTICLE, ARTICLE, record))

    def test_actual_rewrite_or_deletion_and_no_unregistered_change(self):
        draft = ARTICLE + "\n冗余句。\n"
        record = reviewed_fixture(draft, ARTICLE)
        record["findings"] = [{"before": "冗余句。", "action": "delete", "status": "resolved", "reason": "合成测试：删除重复内容"}]
        self.assertEqual(validate_review(draft, ARTICLE, record), [])
        record["findings"] = []
        self.assertTrue(validate_review(draft, ARTICLE, record))
        record = reviewed_fixture(draft, ARTICLE)
        record["findings"][0]["after"] = "不在终稿里的改写"
        self.assertTrue(validate_review(draft, ARTICLE, record))

    def test_bad_record_types_are_errors(self):
        for value in (None, [], "pass", 1):
            self.assertTrue(validate_review(ARTICLE, ARTICLE, value))
        for key in reviewed_fixture(ARTICLE, ARTICLE):
            for value in (None, {}, [], 12):
                if key == "findings" and value == []:
                    continue
                record = reviewed_fixture(ARTICLE, ARTICLE)
                record[key] = value
                self.assertTrue(validate_review(ARTICLE, ARTICLE, record), (key, value))

    def test_cli_delivery_and_save_require_current_review(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            draft_path = root / "draft.md"
            review_path = root / "review.json"
            draft_path.write_text(ARTICLE, encoding="utf-8")
            script = Path(__file__).with_name("save_article.py")
            command = [sys.executable, str(script), "--output-dir", str(root / "output")]
            missing = subprocess.run(command, input=ARTICLE, text=True, capture_output=True)
            self.assertNotEqual(missing.returncode, 0)
            self.assertFalse((root / "output").exists())
            command += ["--draft", str(draft_path), "--review", str(review_path)]
            missing = subprocess.run(command, input=ARTICLE, text=True, capture_output=True)
            self.assertNotEqual(missing.returncode, 0)
            self.assertFalse((root / "output").exists())
            review_path.write_text(json.dumps(reviewed_fixture(ARTICLE, ARTICLE)), encoding="utf-8")
            good = subprocess.run(command, input=ARTICLE, text=True, capture_output=True)
            self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
            stale = subprocess.run(command, input=ARTICLE + "\n新增段落。\n", text=True, capture_output=True)
            self.assertNotEqual(stale.returncode, 0)
            self.assertEqual(len(list((root / "output").glob("*.md"))), 1)
            check = [sys.executable, str(script.with_name("check_article.py")), "-", "--strict",
                     "--draft", str(draft_path), "--review", str(review_path)]
            good = subprocess.run(check, input=ARTICLE, text=True, capture_output=True)
            self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
            review_path.write_text("{", encoding="utf-8")
            bad = subprocess.run(check, input=ARTICLE, text=True, capture_output=True)
            self.assertNotEqual(bad.returncode, 0)


if __name__ == "__main__":
    unittest.main()
