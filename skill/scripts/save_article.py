#!/usr/bin/env python3
"""Strictly validate stdin Markdown and save it using the shared article naming rule."""

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


SKILL_ROOT = Path(__file__).resolve().parent.parent
# The installer binds this default to the selected workspace in the installed copy.
DEFAULT_OUTPUT_DIR = Path.home() / "Documents" / "workspace" / "guage-write-flow" / "output"
SHANGHAI = ZoneInfo("Asia/Shanghai")
H1 = re.compile(r"^#[ \t]+(.+?)\s*#*\s*$", re.M)


def slugify(title):
    """Keep Unicode letters and numbers; collapse all other characters to hyphens."""
    return "-".join(re.findall(r"[^\W_]+", title.casefold(), flags=re.UNICODE))


def article_title(content):
    titles = H1.findall(content)
    if len(titles) != 1:
        raise ValueError(f"完整文章必须有且仅有一个 H1 标题，当前找到 {len(titles)} 个")
    title = titles[0].strip()
    if not title:
        raise ValueError("H1 标题不能为空")
    return title


def available_path(path):
    if not path.exists():
        return path
    n = 2
    while True:
        candidate = path.with_name(f"{path.stem}-{n}{path.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def output_path(title, output_dir=DEFAULT_OUTPUT_DIR, now=None):
    date = (now or datetime.now(SHANGHAI)).strftime("%Y%m%d")
    slug = slugify(title)
    if not slug:
        raise ValueError("标题中没有可用于文件名的文字或数字")
    return available_path(Path(output_dir) / f"{date}-{slug}.md")


def requested_path(value, title):
    path = Path(value).expanduser()
    if path.exists() and path.is_dir():
        return output_path(title, path)
    if not path.suffix:
        return path.with_suffix(".md")
    return path


def validate(content, destination, draft, review, article_type=None):
    checker = SKILL_ROOT / "scripts" / "check_article.py"
    command = [sys.executable, str(checker), "-", "--strict", "--draft", str(draft), "--review", str(review)]
    if article_type is not None:
        command.extend(["--article-type", article_type])
    result = subprocess.run(
        command,
        input=content, capture_output=True, text=True, check=False,
    )
    output = (result.stdout + result.stderr).replace("标准输入", str(destination))
    if output:
        print(output, end="" if output.endswith("\n") else "\n")
    return result.returncode == 0


def save(content, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    while True:
        destination = available_path(destination)
        try:
            with destination.open("x", encoding="utf-8", newline="\n") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            return destination
        except FileExistsError:
            continue
        except Exception:
            destination.unlink(missing_ok=True)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="explicit destination file; takes precedence over the default path")
    parser.add_argument("--output-dir", help="explicit destination directory; keeps the default date-title filename")
    parser.add_argument("--article-type", help="pass the explicit article type to the strict checker")
    parser.add_argument("--draft", required=True, help="风格审校前的完整初稿")
    parser.add_argument("--review", required=True, help="全部问题处理并逐段复查后的风格审校 JSON")
    args = parser.parse_args()
    if args.output and args.output_dir:
        parser.error("use only one of --output or --output-dir")

    content = sys.stdin.read()
    try:
        title = article_title(content)
        if args.output:
            destination = requested_path(args.output, title)
        else:
            destination = output_path(title, Path(args.output_dir).expanduser() if args.output_dir else DEFAULT_OUTPUT_DIR)
    except ValueError as exc:
        parser.error(str(exc))

    if not validate(content, destination, args.draft, args.review, article_type=args.article_type):
        print("未保存：严格校验未通过。", file=sys.stderr)
        return 1
    try:
        destination = save(content, destination)
    except OSError as exc:
        print(f"保存失败：{destination}: {exc}", file=sys.stderr)
        return 1
    print(f"已保存：{destination.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
