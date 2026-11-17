#!/usr/bin/env python3
"""Inventory local material candidates and compute a writing research route."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


RELEVANCE = {"relevant", "irrelevant", "uncertain"}


class PreflightError(ValueError):
    pass


def text(value):
    return isinstance(value, str) and bool(value.strip())


def require(condition, message):
    if not condition:
        raise PreflightError(message)


def workspace_path(value=None):
    if value is None:
        value = Path.cwd()
    require(isinstance(value, (str, Path)) and str(value).strip(), "workspace 必须是非空目录路径")
    workspace = Path(value).expanduser().resolve()
    require(not workspace.exists() or workspace.is_dir(), "workspace 不是目录")
    return workspace


def material_path(value, workspace):
    require(text(value), "materials.path 必须为非空路径")
    path = Path(value).expanduser()
    path = path if path.is_absolute() else workspace / path
    require(not path.name.startswith("."), "系统隐藏项不作为材料")
    return path.resolve()


def file_record(path):
    require(path.is_file(), f"素材不存在或不是常规文件：{path}")
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return {"path": str(path), "sha256": digest.hexdigest(), "read_error": None}
    except OSError as exc:
        return {"path": str(path), "sha256": None, "read_error": str(exc)}


def inventory(workspace=None, selected_paths=None, allow_empty_selection=False):
    workspace = workspace_path(workspace)
    paths = []
    if selected_paths is not None:
        require(isinstance(selected_paths, list) and (selected_paths or allow_empty_selection) and all(text(p) for p in selected_paths),
                "selected_paths 必须是非空路径数组；空选择须有明确用户指令依据，不得用 [] 绕过候选清单")
        paths = [material_path(p, workspace) for p in selected_paths]
    else:
        briefs = workspace / "briefs"
        require(not briefs.exists() or briefs.is_dir(), "briefs 不是目录")
        require(not briefs.is_symlink(), "briefs 是符号链接，请使用显式 selected_paths 选择实际文件")
        if briefs.exists():
            def failed(exc):
                raise PreflightError(f"无法完整读取素材目录：{exc}")

            for directory, dirs, files in os.walk(briefs, onerror=failed, followlinks=False):
                dirs[:] = sorted(d for d in dirs if not d.startswith("."))
                for child in dirs:
                    require(not (Path(directory) / child).is_symlink(), "候选目录含符号链接，请用 selected_paths 明确选择实际文件")
                for name in sorted(files):
                    if name.startswith("."):
                        continue
                    path = Path(directory) / name
                    require(not path.is_symlink(), "候选文件含符号链接，请用 selected_paths 明确选择实际文件")
                    paths.append(path.resolve())
    require(len(paths) == len(set(paths)), "候选路径重复或多个路径指向同一文件")
    result = {"workspace": str(workspace), "materials": [file_record(p) for p in sorted(paths)]}
    if selected_paths is not None:
        result["selected_paths"] = sorted(str(p) for p in paths)
    return result


def route(manifest, workspace=None):
    require(isinstance(manifest, dict), "素材清单必须是 JSON 对象")
    require(text(manifest.get("topic")), "topic 必须非空")
    workspace = workspace_path(workspace)
    if "workspace" in manifest:
        require(workspace_path(manifest["workspace"]) == workspace, "清单 workspace 与执行工作区不一致")
    selected = manifest.get("selected_paths") if "selected_paths" in manifest else None
    if "selected_paths" in manifest:
        require(selected is not None, "selected_paths 不得为 null；未明确选择时省略")
    empty_selection = selected == []
    if empty_selection:
        require(text(manifest.get("selection_reason")) and text(manifest.get("selection_source_ref")),
                "空选择必须提供 selection_reason 与 selection_source_ref，引用用户明确不使用本地素材的指令")
    current = inventory(workspace, selected, allow_empty_selection=empty_selection)
    rows = manifest.get("materials")
    require(isinstance(rows, list) and all(isinstance(row, dict) for row in rows), "materials 必须是对象数组")
    records = {}
    for row in rows:
        path = str(material_path(row.get("path"), workspace))
        require(path not in records, "materials 包含重复路径")
        require(text(row.get("relevance")) and row["relevance"] in RELEVANCE, "relevance 必须为 relevant/irrelevant/uncertain")
        require(row.get("read_status") in ("success", "failed"), "read_status 必须为 success/failed")
        require(text(row.get("reason")), "每份材料必须填写本次相关性判断 reason")
        require(text(row.get("summary")) or row["read_status"] == "failed", "读取成功的材料必须填写 summary")
        records[path] = row
    require(set(records) == {row["path"] for row in current["materials"]},
            "materials 必须完整覆盖本次候选：存在遗漏、新增或不属于本次选择的文件，请重新 inventory")
    materials, usable, excluded, unresolved, issues = [], [], [], [], []
    for observed in current["materials"]:
        path = observed["path"]
        row = records[path]
        require("sha256" in row and row["sha256"] == observed["sha256"], f"素材哈希缺失或已变化，请重新读取并分类：{path}")
        normalized = {**observed, "relevance": row["relevance"], "read_status": row["read_status"],
                      "reason": row["reason"].strip(), "summary": row.get("summary", "").strip() if isinstance(row.get("summary", ""), str) else ""}
        materials.append(normalized)
        if observed["read_error"] or row["read_status"] == "failed" or row["relevance"] == "uncertain":
            unresolved.append(path)
            issues.append({"path": path, "reason": observed["read_error"] or row["reason"]})
        elif row["relevance"] == "relevant":
            usable.append(path)
        else:
            excluded.append(path)
    result = {"policy_version": "1", "topic": manifest["topic"].strip(), "workspace": str(workspace),
              "materials": materials, "mode": "brief_first_verify_mode" if usable or unresolved else "publish_mode",
              "can_proceed": not unresolved, "usable_materials": usable, "excluded_materials": excluded,
              "unresolved_materials": unresolved, "issues": issues}
    if selected is not None:
        result["selected_paths"] = current["selected_paths"]
    if empty_selection:
        result["selection_reason"] = manifest["selection_reason"].strip()
        result["selection_source_ref"] = manifest["selection_source_ref"].strip()
    return result


def validate_preflight(preflight, topic, mode):
    if not isinstance(preflight, dict):
        return ["preflight: 缺少脚本生成的素材预检；旧研究记录重新用于写作前须补预检"]
    try:
        require(text(preflight.get("workspace")) and Path(preflight["workspace"]).is_absolute(), "preflight.workspace 必须是已解析的绝对路径")
        current = route(preflight, preflight["workspace"])
    except (OSError, ValueError, TypeError) as exc:
        return [f"preflight: {exc}"]
    errors = []
    if current != preflight or type(preflight.get("can_proceed")) is not bool:
        errors.append("preflight: 内容与当前文件重算结果不一致，不得手改 mode/can_proceed/清单")
    if current["topic"] != topic:
        errors.append("preflight: topic 与本次研究主题不一致")
    if mode != "explore_mode" and current["mode"] != mode:
        errors.append("preflight: 研究 mode 与相关素材计算出的模式不一致")
    if not current["can_proceed"]:
        errors.append("preflight: 存在未解析或相关性待确认材料，先处理具体缺口，不得宣称预检通过")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inventory", "route"))
    parser.add_argument("--workspace", help="本轮工作区；省略时使用进程当前工作目录")
    parser.add_argument("--select", action="append", help="inventory 的本轮明确选取文件，可重复；route 使用 stdin 的 selected_paths")
    args = parser.parse_args()
    if args.command == "inventory":
        result = inventory(args.workspace, args.select)
    else:
        require(args.select is None, "route 的选取范围请写在 stdin.selected_paths，不能另传 --select")
        result = route(json.load(sys.stdin), args.workspace)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("can_proceed", True) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, TypeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
