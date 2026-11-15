"""Run with python3 scripts/test_check_article.py; no external dependencies."""

import subprocess
import sys
import tempfile
from pathlib import Path

from check_article import _r1_cold_start, _r2_promise, _r3_artifact_evidence


article = "# 实测 Foobar 提升 99%\n\n今天完成了整理。"
for prefix in ("", "\n", "\n\n", "文章说明\n\n"):
    assert _r1_cold_start(prefix + article) == _r1_cold_start(article)
    assert _r2_promise(prefix + article) == _r2_promise(article)
assert len(_r2_promise(article)) == 2
assert _r1_cold_start("# Foobar")
assert _r2_promise("# 实测提升 99%")
assert not _r2_promise("# 实测提升 99%\n\n运行日志：\n```text\n99%\n```")

script = Path(__file__).with_name("check_article.py")
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "article.md"
    samples = {
        "R1": "# Foobar\n\n## 一、整理记录\n\n今天完成了整理。",
        "R2": "# 节省 99%\n\n## 一、整理记录\n\n今天完成了整理。",
        "R3": "# 工作小记\n\n## 一、实测\n\n实测完成，测试结束。",
        "R4": "# 工作小记\n\n## 一、判断\n\n阈值设为 80，结果通过。",
        "R5": "# 工作小记\n\n## 一、记录\n\n这次整理结束以后，我把过程重新记录了一遍，希望读者可以理解这套整理过程的来龙去脉和整体经过。",
    }
    for rule, content in samples.items():
        path.write_text(content, encoding="utf-8")
        for strict in (False, True):
            result = subprocess.run(
                [sys.executable, str(script), str(path)] + (["--strict"] if strict else []),
                capture_output=True, text=True,
            )
            blocked = strict and rule != "R5"
            assert result.returncode == int(blocked), (rule, strict, result.stdout, result.stderr)
            assert ("[ERROR] " if blocked else "[WARN] ") + "[" + rule + "]" in result.stderr

    path.write_text("# Only title\n\n正文。", encoding="utf-8")
    result = subprocess.run([sys.executable, str(script), str(path), "--strict"], capture_output=True, text=True)
    assert result.returncode != 0 and "requires at least one H2" in result.stderr

    path.write_text("# 标题\n\n## 章节\n\n正文。\n\n##### 过深标题\n", encoding="utf-8")
    result = subprocess.run([sys.executable, str(script), str(path)], capture_output=True, text=True)
    assert result.returncode != 0 and "above H4" in result.stderr

    path.write_text("# 标题\n\n## 章节\n\n```text\n当然可以\n```\n\n正文。", encoding="utf-8")
    result = subprocess.run([sys.executable, str(script), str(path)], capture_output=True, text=True)
    assert result.returncode == 0, (result.stdout, result.stderr)

    path.write_text("# 标题\n\n## 章节\n\n这标志着一场革命性变革。", encoding="utf-8")
    result = subprocess.run([sys.executable, str(script), str(path)], capture_output=True, text=True)
    assert result.returncode != 0 and "Banned expression" in result.stderr

    valid = "# 整理记录\n\n## 一、过程\n\n今天完成了整理。\n"
    result = subprocess.run([sys.executable, str(script), "-", "--strict"], input=valid, capture_output=True, text=True)
    assert result.returncode == 0, (result.stdout, result.stderr)
    result = subprocess.run(
        [sys.executable, str(script), "-"],
        input="# 整理记录\n\n今天完成了整理。\n", capture_output=True, text=True,
    )
    assert result.returncode != 0 and "requires at least one H2" in result.stderr
table = "| 项目 | 官方记录 |\n| --- | --- |\n| 样本数量 | 20 |"
source = "[原始资料](https://example.com/report)"
analysis = "# 资料分析\n\n## 结果\n\n官方评测记录了测试结果。\n\n" + table + "\n\n" + source + "\n"

def run_article(content, article_type=None):
    command = [sys.executable, str(script), "-", "--strict"]
    if article_type is not None:
        command.extend(["--article-type", article_type])
    return subprocess.run(command, input=content, capture_output=True, text=True)


# Explicit analysis must supply both evidence forms, even without trigger words.
for content in (
    analysis.replace(table, ""),
    analysis.replace(source, ""),
    analysis.replace(table, "| 项目 | 记录 |\n| --- | --- |"),
    analysis.replace(table, "```text\n" + table + "\n```"),
    analysis.replace(source, "```text\n" + source + "\n```"),
    analysis.replace(source, "`" + source + "`"),
    analysis.replace(source, "![截图](https://example.com/report.png)"),
    analysis.replace(source, "[资料](file:///tmp/report.md)"),
    analysis.replace(source, "[资料](https://[)"),
    "# 资料分析\n\n## 结果\n\n说明。\n",
):
    result = run_article(content, "source-analysis")
    assert result.returncode != 0 and "[R3]" in result.stderr, (result.stdout, result.stderr)

result = run_article(analysis, "source-analysis")
assert result.returncode == 0, (result.stdout, result.stderr)

# Existing/default/unknown behavior stays conservative; explicit practical types
# cannot evade the two-artifact check simply by avoiding trigger words.
assert _r3_artifact_evidence(analysis)
assert _r3_artifact_evidence(analysis, "unknown") == _r3_artifact_evidence(analysis)
for article_type in (None, "unknown", "hands-on", "evaluation", "integration"):
    result = run_article(analysis, article_type)
    assert result.returncode != 0 and "[R3]" in result.stderr, (article_type, result.stdout, result.stderr)
for article_type in ("hands-on", "evaluation", "integration"):
    assert _r3_artifact_evidence(table + "\n" + source, article_type)
    result = run_article(analysis + "\n```python\nprint(1)\n```\n", article_type)
    assert result.returncode == 0, (article_type, result.stdout, result.stderr)

# Analysis changes only R3; all other strict gates still block bad content.
for bad, signal in (
    (analysis.replace("## 结果", "### 结果"), "Heading level skipped"),
    (analysis + "\n这标志着一次革命性变化。\n", "Banned expression"),
    (analysis.replace("资料分析", "Foobar"), "[R1]"),
    (analysis.replace("# 资料分析", "# 节省99%"), "[R2]"),
    (analysis + "\n阈值设为80，结果通过。\n", "[R4]"),
):
    result = run_article(bad, "source-analysis")
    assert result.returncode != 0 and signal in result.stderr, (signal, result.stdout, result.stderr)

print("PASS: existing structure/style/R1-R5, explicit article-type evidence, conservative fallback, and unchanged strict gates")
