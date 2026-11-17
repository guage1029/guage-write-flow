#!/usr/bin/env python3
"""Validate research records from a file or stdin; never writes runtime files."""
import argparse
import json
import re
import sys
from datetime import date, datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from prepare_research import validate_preflight

SEARCH_ORDER = ("tavily", "exa", "web")
FALLBACK_OUTCOMES = {"unavailable", "error", "no_results", "no_primary_source", "insufficient_evidence"}
FETCH_TOOLS = {"tavily_extract", "exa_fetch", "web_fetch", "tavily_search_raw"}
MODES = {"publish_mode", "brief_first_verify_mode", "explore_mode"}
MAX_AGE_DAYS = 30
ROUND_FIELDS = {"goal": "本轮目标", "changes": "实际改动", "verification": "验证结果", "risks": "风险与阻塞", "next": "下一轮建议"}


def text(value):
    return isinstance(value, str) and bool(value.strip())


def url(value):
    if not text(value):
        return False
    try:
        parsed = urlparse(value)
        return parsed.scheme in {"https", "http"} and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def validate_data(data, today=None):
    """Returns errors; checks recorded provenance, not actual runtime tool calls."""
    errors = []
    today = today or datetime.now(ZoneInfo("Asia/Shanghai")).date()
    if not isinstance(data, dict):
        return ["顶层必须是 JSON 对象"]

    def check_date(value, label, max_age=None):
        try:
            parsed = date.fromisoformat(value) if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else None
        except ValueError:
            parsed = None
        if parsed is None:
            errors.append(f"{label}: 日期必须为非空 YYYY-MM-DD")
        elif parsed > today or (max_age is not None and (today - parsed).days > max_age):
            errors.append(f"{label}: 日期在未来或超过 {max_age} 天" if max_age is not None else f"{label}: 日期不得在未来")
        return parsed

    def records(key):
        value = data.get(key)
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            errors.append(f"{key}: 必须是对象数组")
            return []
        return value

    if not text(data.get("topic")):
        errors.append("topic: 必须非空")
    mode = data.get("mode")
    if not text(mode) or mode not in MODES:
        errors.append("mode: 无效模式")
    errors.extend(validate_preflight(data.get("preflight"), data.get("topic"), mode))
    if not text(data.get("topic_type")) or data.get("topic_type") not in {"product", "concept", "open-source", "news"}:
        errors.append("topic_type: 无效主题类型")
    research_date = check_date(data.get("research_date"), "research_date", MAX_AGE_DAYS)
    attempts = records("search_attempts")
    previous = {}
    discovered = set()
    for i, attempt in enumerate(attempts):
        label = f"search_attempts[{i}]"
        task, provider, outcome = (attempt.get(k) for k in ("task_id", "provider", "outcome"))
        if not text(task) or provider not in SEARCH_ORDER:
            errors.append(f"{label}: task_id/provider 无效")
            continue
        if not text(outcome) or outcome not in FALLBACK_OUTCOMES | {"success"} or not text(attempt.get("query")):
            errors.append(f"{label}: query/outcome 无效")
        if text(outcome) and outcome in FALLBACK_OUTCOMES and not text(attempt.get("reason")):
            errors.append(f"{label}: 降级或失败必须说明 reason")
        prior = previous.get(task)
        rank = SEARCH_ORDER.index(provider)
        if prior is None and rank != 0:
            errors.append(f"{label}: 每项任务必须从 Tavily 开始，不可用也须记录")
        if prior and provider != prior[0]:
            if rank != SEARCH_ORDER.index(prior[0]) + 1:
                errors.append(f"{label}: 必须按 Tavily → Exa → Web 降级")
            if (not text(prior[1]) or prior[1] not in FALLBACK_OUTCOMES) and attempt.get("advance_reason") != "independent_crosscheck":
                errors.append(f"{label}: 前工具成功后换工具须声明 independent_crosscheck")
        result_urls = attempt.get("result_urls")
        if not isinstance(result_urls, list) or any(not url(u) for u in result_urls):
            errors.append(f"{label}: result_urls 必须是 HTTP(S) URL 数组")
        else:
            if outcome == "success" and not result_urls:
                errors.append(f"{label}: success 不能没有结果")
            if text(outcome) and outcome in {"no_results", "unavailable"} and result_urls:
                errors.append(f"{label}: 无结果/不可用状态不能含结果")
            discovered.update((task, provider, u) for u in result_urls)
        previous[task] = (provider, outcome)

    sources = records("sources")
    by_url = {}
    for i, source in enumerate(sources):
        label = f"sources[{i}]"
        source_url = source.get("url")
        if not url(source_url):
            errors.append(f"{label}: 无效来源 URL")
            continue
        if source_url in by_url:
            errors.append(f"{label}: 重复来源 URL")
        by_url[source_url] = source
        if not text(source.get("title")) or str(source.get("tier")) not in {"1", "2a", "2b", "3", "4"}:
            errors.append(f"{label}: title/tier 无效")
        if "source_date" not in source:
            errors.append(f"{label}: 必须记录 source_date，原文无日期时使用 null，不得用访问日期替代")
        elif source["source_date"] is not None:
            check_date(source["source_date"], f"{label}.source_date")
        verified = check_date(source.get("verified_at"), f"{label}.verified_at")
        if verified and research_date and verified > research_date:
            errors.append(f"{label}: 核验时间不得晚于 research_date")
        provider = source.get("discovered_by")
        if provider != "direct" and (not text(source.get("task_id")) or not text(provider) or (source.get("task_id"), provider, source_url) not in discovered):
            errors.append(f"{label}: 找不到对应搜索结果记录；已知 URL 使用 direct")
        if source.get("fetch_status") != "success" or (not text(source.get("fetched_by")) or source.get("fetched_by") not in FETCH_TOOLS) or source.get("content_kind") != "full_text":
            errors.append(f"{label}: 必须成功读取来源原文，摘要不能作为证据")

    claims = records("claims")
    if mode != "explore_mode" and not claims:
        errors.append("claims: 写作前至少需要一条已核实事实")
    ids = set()
    for i, claim in enumerate(claims):
        label = f"claims[{i}]"
        claim_id = claim.get("claim_id")
        if not text(claim_id) or claim_id in ids:
            errors.append(f"{label}: claim_id 缺失或重复")
        if text(claim_id):
            ids.add(claim_id)
        if not text(claim.get("claim_text")) or claim.get("status") != "supported":
            errors.append(f"{label}: 可用事实必须非空且 supported；缺口放 excluded_claims")
        fact_type = claim.get("fact_type", "dynamic")
        if not text(fact_type) or fact_type not in {"dynamic", "event", "stable"}:
            errors.append(f"{label}: fact_type 必须为 dynamic/event/stable；省略时按 dynamic 检查")
        if fact_type == "event":
            check_date(claim.get("event_date"), f"{label}.event_date")
        source_url = claim.get("source_url")
        source = by_url.get(source_url) if isinstance(source_url, str) else None
        if source is None:
            errors.append(f"{label}: 来源未在 sources 中登记")
        else:
            if str(source.get("tier")) not in {"1", "2a"} or str(claim.get("tier")) != str(source.get("tier")):
                errors.append(f"{label}: 事实必须由一致的 Tier 1/2a 来源支撑")
            if claim.get("source_date") != source.get("source_date"):
                errors.append(f"{label}: 来源日期不一致")
            if fact_type == "dynamic":
                check_date(source.get("verified_at"), f"{label}: 易变事实的 verified_at", MAX_AGE_DAYS)
        if not text(claim.get("evidence_quote")):
            errors.append(f"{label}: 缺少 evidence_quote")

    candidates = records("tier_1_candidates")
    discrepancies = records("discrepancies")
    for candidate in candidates:
        if not text(candidate.get("verification_status")) or candidate.get("verification_status") not in {"verified", "unverified", "discrepancy"}:
            errors.append("候选事实 verification_status 无效")
        if candidate.get("verification_status") == "discrepancy":
            errors.append("候选事实存在差异，需用户确认后重新核验")
    if discrepancies:
        errors.append("discrepancies: 存在未解决差异")
    excluded = records("excluded_claims")
    if any(not text(item.get("claim_text")) or not text(item.get("reason")) for item in excluded):
        errors.append("excluded_claims: 必须填写 claim_text/reason")
    report = data.get("round_report")
    if not isinstance(report, dict) or any(not text(report.get(k)) for k in ROUND_FIELDS):
        errors.append("round_report: 必须包含本轮目标、实际改动、验证结果、风险与阻塞、下一轮建议")
    # shortcut: provenance fields are Agent-reported; use runtime-generated logs if strict invocation proof is required.
    qc = data.get("quality_check")
    if not isinstance(qc, dict) or qc.get("passed") is not True:
        errors.append("quality_check.passed 必须为 true；最终通过状态由上述检查独立决定")
    return errors


def validate(path, report=False):
    try:
        if path == "-":
            data = json.load(sys.stdin)
        else:
            with open(path, encoding="utf-8") as stream:
                data = json.load(stream)
    except (OSError, ValueError) as exc:
        print(f"[ERROR] 无法读取调研 JSON：{exc}", file=sys.stderr)
        return False
    errors = validate_data(data)
    if report:
        fields = data.get("round_report", {}) if isinstance(data, dict) else {}
        if not isinstance(fields, dict):
            fields = {}
        print("# 调研轮次报告")
        for key, heading in ROUND_FIELDS.items():
            print(f"\n## {heading}\n\n{fields.get(key, '未提交')}")
    print("【调研质量校验通过】" if not errors else "【调研质量校验失败】")
    for error in errors:
        print(f"[ERROR] {error}", file=sys.stderr)
    return not errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="研究 JSON 路径；- 表示标准输入")
    parser.add_argument("--report", action="store_true", help="输出固定五部分报告及独立校验结论；不保存文件")
    args = parser.parse_args()
    sys.exit(0 if validate(args.path, args.report) else 1)
