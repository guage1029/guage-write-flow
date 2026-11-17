#!/usr/bin/env python3
"""Prepare a pending style-review record and verify its binding to both drafts."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


SKILL_ROOT = Path(__file__).resolve().parent.parent
RULE_FILES = ("style.md", "persona.md", "ai-flavor-patterns.md", "checklist.md", "style-review.md", "human-voice-policy.md")
VOICE_CHECKS = ("judgment", "presence", "explanation", "rhythm", "restraint", "structure")


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def blocks(content):
    """Keep all blank-line-separated Markdown blocks, including evidence and code."""
    return [part.strip() for part in re.split(r"\n[ \t]*\n", content.strip()) if part.strip()]


def rule_hashes(root=SKILL_ROOT):
    return {name: digest((root / "references" / name).read_text(encoding="utf-8")) for name in RULE_FILES}


def review_template(draft, final, root=SKILL_ROOT):
    return {
        "draft_sha256": digest(draft), "final_sha256": digest(final),
        "rules_sha256": rule_hashes(root),
        "blocks": [{"index": i, "sha256": digest(block), "status": "pending", "reason": ""}
                   for i, block in enumerate(blocks(final), 1)],
        "voice_checks": [{"id": key, "status": "pending", "evidence": "", "reason": ""}
                         for key in VOICE_CHECKS],
        "findings": [],
        "handbook_iteration": {"decision": "pending", "basis": ""},
    }


def text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_review(draft, final, review, root=SKILL_ROOT):
    # shortcut: records are Agent-reported; add a host-controlled reviewer when independent execution proof is required.
    if not isinstance(review, dict):
        return ["审校记录必须是 JSON 对象"]
    errors = []
    if review.get("draft_sha256") != digest(draft):
        errors.append("初稿哈希不匹配，不能替换已审校初稿")
    if review.get("final_sha256") != digest(final):
        errors.append("终稿哈希不匹配，正文变化后必须重新审校")
    if review.get("rules_sha256") != rule_hashes(root):
        errors.append("风格规则已变化或未绑定当前手册，必须按最新规则复查")

    final_blocks = blocks(final)
    coverage = review.get("blocks")
    if not isinstance(coverage, list) or len(coverage) != len(final_blocks) or not final_blocks:
        errors.append("逐段复查必须完整覆盖终稿的全部 Markdown 块")
    else:
        for i, (block, row) in enumerate(zip(final_blocks, coverage), 1):
            if not isinstance(row, dict) or row.get("index") != i or row.get("sha256") != digest(block):
                errors.append(f"第 {i} 块的审校定位或哈希不匹配")
            elif row.get("status") != "pass" or not text(row.get("reason")):
                errors.append(f"第 {i} 块尚未完成风格复查，需写明修改后判断或保留依据")

    checks = review.get("voice_checks")
    if not isinstance(checks, list) or len(checks) != len(VOICE_CHECKS) or any(not isinstance(row, dict) for row in checks):
        errors.append("必须提供全部六项口吻检查")
    else:
        if sorted(str(row.get("id")) for row in checks) != sorted(VOICE_CHECKS):
            errors.append("口吻检查缺项、重复或包含未知项目")
        for row in checks:
            evidence = row.get("evidence")
            if row.get("status") != "pass" or not text(row.get("reason")) or not text(evidence) or evidence not in final:
                errors.append("六项口吻检查必须通过，并引用终稿原句说明依据")

    findings = review.get("findings")
    if not isinstance(findings, list):
        errors.append("findings 必须逐项列出全部问题及处理结果，无问题时为空数组")
    else:
        if draft != final and not findings:
            errors.append("正文发生改写，必须登记实际问题及处理，不得只补通过结论")
        for row in findings:
            if not isinstance(row, dict):
                errors.append("每项改写必须是对象")
                continue
            before, after = row.get("before"), row.get("after")
            if not text(before) or before not in draft or row.get("status") != "resolved" or not text(row.get("reason")):
                errors.append("仍有未处理问题，或问题缺少初稿原句与改写原因")
            if row.get("action") == "delete":
                if text(before) and before in final:
                    errors.append("标记删除的问题原句仍出现在终稿")
            elif row.get("action") != "rewrite" or not text(after) or after not in final or before == after:
                errors.append("改写后原句必须存在于终稿且与初稿不同")

    iteration = review.get("handbook_iteration")
    if not isinstance(iteration, dict) or iteration.get("decision") not in ("updated", "unchanged") or not text(iteration.get("basis")):
        errors.append("必须完成风格手册复盘：记录已更新的用户依据，或说明无新依据而保持规则")
    return errors


def validate_review_files(draft_path, review_path, final):
    try:
        draft = Path(draft_path).read_text(encoding="utf-8")
        review = json.loads(Path(review_path).read_text(encoding="utf-8"))
        return validate_review(draft, final, review)
    except (OSError, ValueError, TypeError) as exc:
        return [f"无法核验风格审校记录：{exc}"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", required=True, help="完整初稿；不得用终稿倒填初稿")
    parser.add_argument("--final", required=True, help="完成逐段改写后的正文")
    args = parser.parse_args()
    try:
        template = review_template(Path(args.draft).read_text(encoding="utf-8"), Path(args.final).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"无法生成审校模板：{exc}\n")
    json.dump(template, sys.stdout, ensure_ascii=False, indent=2)
    print()
