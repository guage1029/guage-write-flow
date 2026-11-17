"""Isolated material routing checks; no real workspace changes or network calls."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from prepare_research import PreflightError, inventory, route, validate_preflight


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="guage-preflight-")
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name).resolve()
        self.briefs = self.workspace / "briefs"
        self.briefs.mkdir()

    def add(self, name="other.md", content="与本题无关的合成材料"):
        p = self.briefs / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def test_default_workspace_is_current_directory_and_can_be_overridden(self):
        self.add()
        with patch("prepare_research.Path.cwd", return_value=self.workspace):
            self.assertEqual(inventory()["workspace"], str(self.workspace))
            other = self.workspace / "other"
            self.assertEqual(inventory(other)["workspace"], str(other))
            self.assertFalse(other.exists())
        data = route(self.manifest(), self.workspace)
        del data["workspace"]
        self.assertTrue(validate_preflight(data, data["topic"], "publish_mode"))

    def manifest(self):
        data = inventory(self.workspace)
        data["topic"] = "GPT-6 Luna 合成测试"
        for row in data["materials"]:
            row.update(relevance="irrelevant", read_status="success", reason="材料描述另一合成主题，与本轮问题无关", summary="另一主题的简报")
        return data

    def test_four_unrelated_materials_route_publish(self):
        for i in range(4):
            self.add(f"other-{i}.md")
        self.add(".DS_Store", "metadata")
        data = self.manifest()
        output = route(data, self.workspace)
        self.assertEqual(len(output["materials"]), 4)
        self.assertEqual(output["mode"], "publish_mode")
        self.assertTrue(output["can_proceed"])
        self.assertEqual(len(output["excluded_materials"]), 4)
        self.assertEqual(validate_preflight(output, data["topic"], "publish_mode"), [])

    def test_relevant_and_unresolved_materials(self):
        self.add()
        data = self.manifest(); data["materials"][0]["relevance"] = "relevant"
        output = route(data, self.workspace)
        self.assertEqual(output["mode"], "brief_first_verify_mode")
        self.assertTrue(output["can_proceed"])
        for field, value in (("relevance", "uncertain"), ("read_status", "failed")):
            changed = copy.deepcopy(data); changed["materials"][0][field] = value
            output = route(changed, self.workspace)
            self.assertFalse(output["can_proceed"])
            self.assertTrue(output["issues"])
            self.assertTrue(validate_preflight(output, data["topic"], "brief_first_verify_mode"))

    def test_missing_and_hidden_materials(self):
        self.add(".DS_Store"); self.add(".hidden/private.md")
        self.assertEqual(inventory(self.workspace)["materials"], [])
        self.assertEqual(route(self.manifest(), self.workspace)["mode"], "publish_mode")
        absent = self.workspace / "not-created"
        self.assertEqual(route({"topic": "topic", "materials": []}, absent)["mode"], "publish_mode")
        self.assertFalse(absent.exists())

    def test_explicit_selection_and_empty_choice_evidence(self):
        chosen = self.add("chosen.md"); self.add("unselected.md")
        data = self.manifest()
        data["selected_paths"] = [str(chosen)]
        data["materials"] = [m for m in data["materials"] if m["path"] == str(chosen)]
        data["materials"][0]["relevance"] = "relevant"
        self.assertEqual(route(data, self.workspace)["mode"], "brief_first_verify_mode")
        data.update(selected_paths=[], materials=[])
        with self.assertRaises(PreflightError):
            route(data, self.workspace)
        data.update(selection_reason="用户明确要求不使用本地素材", selection_source_ref="test-user-message-1")
        output = route(data, self.workspace)
        self.assertEqual(output["mode"], "publish_mode")
        self.assertEqual(output["materials"], [])
        self.assertEqual(validate_preflight(output, data["topic"], "publish_mode"), [])
        del output["selection_source_ref"]
        self.assertTrue(validate_preflight(output, data["topic"], "publish_mode"))

    def test_inventory_coverage_and_hash_changes(self):
        p = self.add(); data = self.manifest()
        missing = copy.deepcopy(data); missing["materials"] = []
        with self.assertRaises(PreflightError):
            route(missing, self.workspace)
        duplicate = copy.deepcopy(data); duplicate["materials"].append(copy.deepcopy(duplicate["materials"][0]))
        with self.assertRaises(PreflightError):
            route(duplicate, self.workspace)
        output = route(data, self.workspace)
        p.write_text("changed after classification")
        self.assertTrue(validate_preflight(output, data["topic"], "publish_mode"))
        p.write_text("与本题无关的合成材料"); self.add("new.md")
        self.assertTrue(validate_preflight(output, data["topic"], "publish_mode"))

    def test_tampering_topic_mode_and_explore(self):
        self.add(); data = self.manifest(); output = route(data, self.workspace)
        for key, value in (("mode", "brief_first_verify_mode"), ("can_proceed", False), ("materials", []), ("usable_materials", ["fake"])):
            modified = copy.deepcopy(output); modified[key] = value
            self.assertTrue(validate_preflight(modified, data["topic"], "publish_mode"))
        self.assertTrue(validate_preflight(output, "another topic", "publish_mode"))
        self.assertTrue(validate_preflight(output, data["topic"], "brief_first_verify_mode"))
        self.assertEqual(validate_preflight(output, data["topic"], "explore_mode"), [])
        self.assertTrue(validate_preflight(None, data["topic"], "publish_mode"))

    def test_selected_missing_duplicate_and_hidden(self):
        p = self.add()
        for selection in ([str(p), str(p)], ["missing.md"], ["briefs/.DS_Store"], [None], None):
            data = self.manifest(); data["selected_paths"] = selection
            with self.subTest(selection=selection), self.assertRaises(PreflightError):
                route(data, self.workspace)

    def test_cli_stdin_readonly_and_blocked_exit(self):
        self.add(); data = self.manifest()
        script = str(Path(__file__).with_name("prepare_research.py"))
        cmd = [sys.executable, script, "route", "--workspace", str(self.workspace)]
        before = {str(p): p.read_bytes() for p in self.workspace.rglob("*") if p.is_file()}
        result = subprocess.run(cmd, input=json.dumps(data), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["mode"], "publish_mode")
        data["materials"][0]["relevance"] = "uncertain"
        result = subprocess.run(cmd, input=json.dumps(data), capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["can_proceed"])
        result = subprocess.run(cmd, input="{", capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.workspace.rglob("*") if p.is_file()})

    def test_cli_selected_file_can_live_outside_pool(self):
        self.add("unselected.md")
        external = self.workspace / "current-input.md"
        external.write_text("本轮明确提供的材料")
        script = str(Path(__file__).with_name("prepare_research.py"))
        result = subprocess.run([sys.executable, script, "inventory", "--workspace", str(self.workspace), "--select", str(external)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(result.stdout)
        self.assertEqual(manifest["selected_paths"], [str(external)])
        manifest["topic"] = "本轮主题"
        manifest["materials"][0].update(relevance="relevant", read_status="success", reason="用户本轮指定材料", summary="本轮输入")
        self.assertEqual(route(manifest, self.workspace)["mode"], "brief_first_verify_mode")


if __name__ == "__main__":
    unittest.main()
