"""Run with python3 scripts/test_save_article.py; no external dependencies."""

from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from save_article import article_title, output_path, slugify
from test_review_style import reviewed_fixture


def review_args(directory, content):
    draft = Path(directory) / "draft.txt"
    review = Path(directory) / "review.json"
    draft.write_text(content, encoding="utf-8")
    review.write_text(json.dumps(reviewed_fixture(content, content)), encoding="utf-8")
    return ["--draft", str(draft), "--review", str(review)]


assert slugify("Codex 5：我跑了一遍!") == "codex-5-我跑了一遍"
assert article_title("# 标题\n\n正文") == "标题"
try:
    article_title("# 标题一\n\n# 标题二")
except ValueError:
    pass
else:
    raise AssertionError("multiple H1 headings must be rejected")

with TemporaryDirectory() as directory:
    fixed_now = datetime(2026, 11, 9, 12, tzinfo=ZoneInfo("Asia/Shanghai"))
    first = output_path("Codex 5：我跑了一遍!", directory, fixed_now)
    assert first.name == "20261109-codex-5-我跑了一遍.md"
    first.touch()
    assert output_path("Codex 5：我跑了一遍!", directory, fixed_now).name == "20261109-codex-5-我跑了一遍-2.md"

with TemporaryDirectory() as directory:
    script = Path(__file__).with_name("save_article.py")
    article = "# 收拾书桌的记录\n\n## 一、整理过程\n\n这篇文章记录了一次整理过程。\n\n下一步，我会把这个过程换一组材料再试一次。\n"
    reviewed = review_args(directory, article)
    result = subprocess.run(
        [sys.executable, str(script), "--output-dir", directory] + reviewed,
        input=article, capture_output=True, text=True,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    saved = list(Path(directory).glob("*.md"))
    assert len(saved) == 1 and saved[0].read_text(encoding="utf-8") == article

    duplicate = subprocess.run(
        [sys.executable, str(script), "--output-dir", directory] + reviewed,
        input=article, capture_output=True, text=True,
    )
    assert duplicate.returncode == 0, (duplicate.stdout, duplicate.stderr)
    assert len(list(Path(directory).glob("*.md"))) == 2
    assert any(path.stem.endswith("-2") for path in Path(directory).glob("*.md"))

    blocked = subprocess.run(
        [sys.executable, str(script), "--output-dir", directory] + reviewed,
        input="# Test article\n\n当然可以，本文将总结一下。\n", capture_output=True, text=True,
    )
    assert blocked.returncode != 0
    assert len(list(Path(directory).glob("*.md"))) == 2

    blocked = subprocess.run(
        [sys.executable, str(script), "--output-dir", directory] + reviewed,
        input="# 书桌整理记录\n\n## 一、整理过程\n\n这标志着一次革命性变革。\n\n下一步，我会换一组材料再试。\n",
        capture_output=True, text=True,
    )
    assert blocked.returncode != 0
    assert len(list(Path(directory).glob("*.md"))) == 2

with TemporaryDirectory() as directory:
    analysis = (
        "# 资料分析\n\n## 记录\n\n官方评测包含测试记录。\n\n"
        "| 项目 | 数量 |\n| --- | --- |\n| 样本 | 20 |\n\n"
        "[原始资料](https://example.com/report)\n"
    )

    def save_analysis(article_type=None, content=analysis):
        command = [sys.executable, str(script), "--output-dir", directory] + review_args(directory, content)
        if article_type is not None:
            command.extend(["--article-type", article_type])
        return subprocess.run(command, input=content, capture_output=True, text=True)

    # The CLI must pass the type through validate to the real checker child.
    # Without it this exact input fails R3 and must not create a file.
    for article_type in (None, "unknown", "hands-on", "evaluation", "integration"):
        result = save_analysis(article_type)
        assert result.returncode != 0 and "[R3]" in result.stdout, (result.stdout, result.stderr)
        assert not list(Path(directory).glob("*.md"))
    result = save_analysis("source-analysis")
    assert result.returncode == 0, (result.stdout, result.stderr)
    saved = list(Path(directory).glob("*.md"))
    assert len(saved) == 1 and saved[0].read_text(encoding="utf-8") == analysis

    for content in (
        analysis.replace("[原始资料](https://example.com/report)", ""),
        analysis + "\n这标志着一次革命性变化。\n",
    ):
        result = save_analysis("source-analysis", content)
        assert result.returncode != 0, (result.stdout, result.stderr)
        assert len(list(Path(directory).glob("*.md"))) == 1

with TemporaryDirectory() as directory:
    root = Path(directory).resolve()
    workspace = root / "稿件's workspace"
    workspace.mkdir()
    reviewed = review_args(root, article)
    command = [sys.executable, str(script), "--draft", reviewed[1], "--review", reviewed[3]]
    result = subprocess.run(command, cwd=workspace, input=article, capture_output=True, text=True)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert len(list((workspace / "output").glob("*.md"))) == 1
    other = root / "explicit"
    result = subprocess.run(command + ["--workspace", str(other)], cwd=workspace, input=article, capture_output=True, text=True)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert len(list((other / "output").glob("*.md"))) == 1
    result = subprocess.run(command + ["--workspace", str(other), "--output", "custom/final.md"], cwd=workspace, input=article, capture_output=True, text=True)
    assert result.returncode == 0 and (other / "custom/final.md").read_text(encoding="utf-8") == article
    blocked = other / "not-a-directory"
    blocked.write_text("keep", encoding="utf-8")
    result = subprocess.run(command + ["--workspace", str(blocked)], cwd=workspace, input=article, capture_output=True, text=True)
    assert result.returncode != 0 and blocked.read_text(encoding="utf-8") == "keep"

print("PASS: naming/collision/strict-save compatibility, article-type passthrough, no write on failed gates")
