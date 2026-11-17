"""Run: python3 scripts/test_validate_research.py. Fixture evidence is synthetic."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from validate_research import validate_data
from prepare_research import route

TODAY = datetime.now(ZoneInfo("Asia/Shanghai")).date()
URL = "https://official.example/docs"
TEST_WORKSPACE = tempfile.TemporaryDirectory(prefix="guage-research-test-")


def fixture():
    day = TODAY.isoformat()
    return {
        "topic": "合成调研测试", "topic_type": "product", "mode": "publish_mode", "research_date": day,
        "preflight": route({"topic": "合成调研测试", "materials": []}, TEST_WORKSPACE.name),
        "search_attempts": [{"task_id": "r1", "provider": "tavily", "query": "fixture", "outcome": "success", "result_urls": [URL]}],
        "sources": [{"url": URL, "title": "合成来源", "tier": 1, "source_date": day, "verified_at": day,
                     "task_id": "r1", "discovered_by": "tavily", "fetched_by": "web_fetch", "fetch_status": "success", "content_kind": "full_text"}],
        "claims": [{"claim_id": "c1", "claim_text": "仅用于测试的事实", "fact_type": "dynamic", "status": "supported", "tier": 1,
                    "source_url": URL, "source_date": day, "evidence_quote": "fixture excerpt"}],
        "tier_1_candidates": [], "discrepancies": [], "excluded_claims": [],
        "quality_check": {"passed": True},
        "round_report": {k: "合成测试记录" for k in ("goal", "changes", "verification", "risks", "next")},
    }


class ResearchTests(unittest.TestCase):
    def test_valid_and_direct(self):
        data = fixture()
        self.assertEqual(validate_data(data, TODAY), [])
        data["search_attempts"] = []
        data["sources"][0]["discovered_by"] = "direct"
        self.assertEqual(validate_data(data, TODAY), [])

    def test_fallback_and_independent_tasks(self):
        data = fixture()
        success = data["search_attempts"][0]
        data["search_attempts"] = [{**success, "outcome": "unavailable", "reason": "fixture: missing CLI", "result_urls": []}, {**success, "provider": "exa"}]
        data["sources"][0]["discovered_by"] = "exa"
        self.assertEqual(validate_data(data, TODAY), [])
        data["search_attempts"].insert(1, {**success, "task_id": "r2"})
        self.assertEqual(validate_data(data, TODAY), [])
        data["search_attempts"][0]["outcome"] = "success"
        data["search_attempts"][0]["result_urls"] = [URL]
        self.assertTrue(validate_data(data, TODAY))
        data["search_attempts"][-1]["advance_reason"] = "independent_crosscheck"
        self.assertEqual(validate_data(data, TODAY), [])

    def test_route_rejection(self):
        for change in (lambda d: d["search_attempts"][0].update(provider="exa"),
                       lambda d: d["search_attempts"][0].update(outcome="unavailable", result_urls=[], reason=""),
                       lambda d: d["search_attempts"][0].update(result_urls=[])):
            data = fixture(); change(data)
            self.assertTrue(validate_data(data, TODAY))
        data = fixture()
        data["search_attempts"].append({**data["search_attempts"][0], "provider": "web", "advance_reason": "independent_crosscheck"})
        self.assertTrue(validate_data(data, TODAY))

    def test_evidence_failures(self):
        cases = [
            ("sources", "content_kind", "snippet"), ("sources", "fetch_status", "failed"),
            ("sources", "discovered_by", "exa"), ("sources", "source_date", ""),
            ("sources", "source_date", (TODAY + timedelta(days=1)).isoformat()),
            ("sources", "verified_at", (TODAY - timedelta(days=31)).isoformat()),
            ("sources", "tier", "2b"), ("claims", "source_url", "https://missing.example"),
            ("claims", "source_date", "2000-01-01"), ("claims", "status", "unverified"),
            ("claims", "status", "invented"), ("claims", "evidence_quote", ""),
        ]
        for key, field, value in cases:
            with self.subTest(key=key, field=field, value=value):
                data = fixture(); data[key][0][field] = value
                self.assertTrue(validate_data(data, TODAY))

    def test_web_only_and_all_tools_unavailable(self):
        data = fixture()
        success = data["search_attempts"][0]
        data["search_attempts"] = [
            {**success, "provider": provider, "outcome": "unavailable", "reason": "合成：无权限或网络不可达", "result_urls": []}
            for provider in ("tavily", "exa")
        ] + [{**success, "provider": "web"}]
        data["sources"][0]["discovered_by"] = "web"
        self.assertEqual(validate_data(data, TODAY), [])
        del data["search_attempts"][1]
        self.assertTrue(validate_data(data, TODAY))
        data = fixture()
        data["search_attempts"] = [
            {**success, "provider": provider, "outcome": "unavailable", "reason": "合成：工具不可用", "result_urls": []}
            for provider in ("tavily", "exa", "web")
        ]
        data.update(sources=[], claims=[])
        self.assertTrue(any("claims" in e for e in validate_data(data, TODAY)))

    def test_stable_and_event_dates(self):
        data = fixture()
        source, claim = data["sources"][0], data["claims"][0]
        source["source_date"] = claim["source_date"] = "1990-01-01"
        self.assertEqual(validate_data(data, TODAY), [])  # Old publication can still support a freshly checked claim.
        source["verified_at"] = (TODAY - timedelta(days=31)).isoformat()
        self.assertTrue(validate_data(data, TODAY))
        claim["fact_type"] = "stable"
        self.assertEqual(validate_data(data, TODAY), [])
        claim.update(fact_type="event", event_date="1990-01-01")
        self.assertEqual(validate_data(data, TODAY), [])
        for value in (None, "", (TODAY + timedelta(days=1)).isoformat()):
            claim["event_date"] = value
            self.assertTrue(validate_data(data, TODAY))
        claim["fact_type"] = "unknown"
        self.assertTrue(validate_data(data, TODAY))

    def test_undated_documents_need_real_verification(self):
        data = fixture()
        data["sources"][0]["source_date"] = data["claims"][0]["source_date"] = None
        self.assertEqual(validate_data(data, TODAY), [])
        for value in (None, "", "invalid", (TODAY + timedelta(days=1)).isoformat()):
            changed = copy.deepcopy(data)
            changed["sources"][0]["verified_at"] = value
            self.assertTrue(validate_data(changed, TODAY))
        data["research_date"] = (TODAY - timedelta(days=1)).isoformat()
        self.assertTrue(validate_data(data, TODAY))

    def test_dynamic_verification_window_boundary(self):
        data = fixture()
        data["sources"][0]["verified_at"] = (TODAY - timedelta(days=30)).isoformat()
        self.assertEqual(validate_data(data, TODAY), [])
        data["sources"][0]["verified_at"] = (TODAY - timedelta(days=31)).isoformat()
        self.assertTrue(validate_data(data, TODAY))
        data = fixture()
        del data["sources"][0]["verified_at"]
        data["claims"][0]["fact_type"] = "stable"
        self.assertTrue(validate_data(data, TODAY))
        data = fixture()
        del data["claims"][0]["fact_type"]
        data["sources"][0]["verified_at"] = (TODAY - timedelta(days=31)).isoformat()
        self.assertTrue(validate_data(data, TODAY))

    def test_empty_conflict_and_report(self):
        data = fixture(); data["claims"] = []
        self.assertTrue(validate_data(data, TODAY))
        data["mode"] = "explore_mode"
        self.assertEqual(validate_data(data, TODAY), [])
        data = fixture(); data["discrepancies"] = [{"field": "fixture"}]
        self.assertTrue(validate_data(data, TODAY))
        data = fixture(); del data["round_report"]["risks"]
        self.assertTrue(validate_data(data, TODAY))
        data = fixture(); data["claims"].append(copy.deepcopy(data["claims"][0]))
        self.assertTrue(validate_data(data, TODAY))

    def test_legacy_card_fields_do_not_bypass_general_gates(self):
        data = fixture()
        data["output_mode"] = "card_post"
        data["card_safe_claims"] = []
        self.assertEqual(validate_data(data, TODAY), [])
        data["card_safe_claims"] = [{**data["claims"][0], "can_use_in_card": True}]
        self.assertEqual(validate_data(data, TODAY), [])

        no_preflight = copy.deepcopy(data)
        del no_preflight["preflight"]
        self.assertTrue(any("preflight" in e for e in validate_data(no_preflight, TODAY)))

        no_evidence = copy.deepcopy(data)
        no_evidence["claims"] = []
        self.assertTrue(any("claims" in e for e in validate_data(no_evidence, TODAY)))

    def test_bad_types_do_not_crash(self):
        self.assertTrue(validate_data([], TODAY))
        for key in fixture():
            for value in (None, [], {}, 12):
                data = fixture(); data[key] = value
                validate_data(data, TODAY)
        for key in ("search_attempts", "sources", "claims"):
            for field in fixture()[key][0]:
                for value in (None, [], {}, 12):
                    data = fixture(); data[key][0][field] = value
                    validate_data(data, TODAY)

    def test_preflight_is_required_and_binds_route(self):
        data = fixture(); del data["preflight"]
        self.assertTrue(any("preflight" in e for e in validate_data(data, TODAY)))
        data = fixture(); data["preflight"]["can_proceed"] = False
        self.assertTrue(any("preflight" in e for e in validate_data(data, TODAY)))
        data = fixture(); data["mode"] = "brief_first_verify_mode"
        self.assertTrue(any("preflight" in e for e in validate_data(data, TODAY)))
        with tempfile.TemporaryDirectory(prefix="guage-research-materials-") as folder:
            root = Path(folder); (root / "briefs").mkdir()
            for i in range(4):
                (root / "briefs" / f"other-{i}.md").write_text("其他主题的合成材料")
            from prepare_research import inventory
            manifest = inventory(root); manifest["topic"] = data["topic"]
            for row in manifest["materials"]:
                row.update(relevance="irrelevant", read_status="success", reason="本轮主题无关", summary="其他主题")
            data = fixture(); data["preflight"] = route(manifest, root)
            self.assertEqual(validate_data(data, TODAY), [])
            manifest["materials"][0]["relevance"] = "relevant"
            data["preflight"] = route(manifest, root)
            self.assertTrue(any("preflight" in e for e in validate_data(data, TODAY)))
            data["mode"] = "brief_first_verify_mode"
            self.assertEqual(validate_data(data, TODAY), [])

    def test_stdin_report_and_failure_exit(self):
        cmd = [sys.executable, str(Path(__file__).with_name("validate_research.py")), "-", "--report"]
        result = subprocess.run(cmd, input=json.dumps(fixture()), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for heading in ("本轮目标", "实际改动", "验证结果", "风险与阻塞", "下一轮建议"):
            self.assertIn("## " + heading, result.stdout)
        result = subprocess.run(cmd, input='{"quality_check":{"passed":true}}', text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("校验失败", result.stdout)
        self.assertNotIn("校验通过", result.stdout)
        self.assertEqual(subprocess.run(cmd, input="{", text=True, capture_output=True).returncode, 1)


if __name__ == "__main__":
    unittest.main()
