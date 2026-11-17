#!/usr/bin/env bash
# scripts/install.sh — guage-write-flow Agent Skill 安装脚本
# 支持 Hermes / Claude Code / Codex / Custom 目录
# 只复制 skill/ 目录内容，不复制 workspace/、docs/、evals/
#
# 用法：
#   bash scripts/install.sh --tool hermes
#   bash scripts/install.sh --tool claude-code
#   bash scripts/install.sh --tool codex
#   bash scripts/install.sh --tool custom --skills-dir /path/to/skills
#   bash scripts/install.sh --tool hermes --workspace ~/Documents/workspace/guage-write-flow
#   bash scripts/install.sh --tool auto
#   bash scripts/install.sh          # 交互式选择

set -e

SKILL_NAME="guage-write-flow"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$SCRIPT_DIR/../skill"

# ─── 解析参数 ────────────────────────────────────────────────────────────────

TOOL=""
WORKSPACE_ARG=""
SKILLS_DIR_ARG=""

VALID_TOOLS="hermes claude-code codex custom auto skip"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tool|--workspace|--skills-dir)
            if [ $# -lt 2 ] || [ -z "$2" ] || [[ "$2" == --* ]]; then
                echo "错误：$1 需要非空参数值" >&2
                exit 1
            fi
            ;;
    esac
    case "$1" in
        --tool)
            TOOL="$2"
            if [[ ! " $VALID_TOOLS " =~ " $TOOL " ]]; then
                echo "错误：不支持的 --tool 值：$TOOL"
                echo "支持的值：hermes | claude-code | codex | custom | auto"
                echo "用法：bash scripts/install.sh [--tool hermes|claude-code|codex|custom|auto] [--workspace PATH] [--skills-dir PATH]"
                exit 1
            fi
            shift 2
            ;;
        --workspace)
            WORKSPACE_ARG="${2/#\~/$HOME}"
            shift 2
            ;;
        --skills-dir)
            SKILLS_DIR_ARG="${2/#\~/$HOME}"
            shift 2
            ;;
        *)
            echo "未知参数：$1"
            echo "用法：bash scripts/install.sh [--tool hermes|claude-code|codex|custom|auto] [--workspace PATH] [--skills-dir PATH]"
            exit 1
            ;;
    esac
done

echo "========================================="
echo " guage-write-flow Agent Skill 安装向导"
echo "========================================="
echo ""

# ─── 验证 Skill 源目录 ──────────────────────────────────────────────────────
if [ ! -f "$SKILL_SRC/SKILL.md" ]; then
    echo "错误：在 $SKILL_SRC 下找不到 SKILL.md"
    echo "请确保从项目根目录或 scripts/ 目录内执行此脚本"
    exit 1
fi

# ─── 目录检测函数 ────────────────────────────────────────────────────────────

detect_tools() {
    local found=()
    [ -d "${HERMES_SKILLS_DIR:-$HOME/.hermes/skills}" ] && found+=("hermes")
    [ -d "${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}" ] && found+=("claude-code")
    [ -d "${CODEX_HOME:-$HOME/.codex}/skills" ] && found+=("codex")
    echo "${found[@]}"
}

resolve_skills_dir() {
    local tool="$1"
    case "$tool" in
        hermes)
            echo "${HERMES_SKILLS_DIR:-$HOME/.hermes/skills}"
            ;;
        claude-code)
            echo "${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
            ;;
        codex)
            echo "${CODEX_HOME:-$HOME/.codex}/skills"
            ;;
        custom)
            echo "$SKILLS_DIR_ARG"
            ;;
    esac
}

tool_display_name() {
    case "$1" in
        hermes)      echo "Hermes" ;;
        claude-code) echo "Claude Code" ;;
        codex)       echo "Codex" ;;
        custom)      echo "Custom" ;;
        *)           echo "$1" ;;
    esac
}

# ─── 选择安装工具 ────────────────────────────────────────────────────────────

if [ -z "$TOOL" ]; then
    echo "请选择安装目标："
    echo "  1) Hermes        (~/.hermes/skills)"
    echo "  2) Claude Code   (~/.claude/skills)"
    echo "  3) Codex         (~/.codex/skills)"
    echo "  4) Custom        （手动指定 Skills 目录）"
    echo "  5) 仅初始化 workspace，跳过 Skill 安装"
    echo ""
    printf "请输入编号："
    read -r MENU_CHOICE
    case "$MENU_CHOICE" in
        1) TOOL="hermes" ;;
        2) TOOL="claude-code" ;;
        3) TOOL="codex" ;;
        4) TOOL="custom" ;;
        5) TOOL="skip" ;;
        *)
            echo "无效选择，退出。"
            exit 1
            ;;
    esac
    echo ""
fi

if [ "$TOOL" = "auto" ]; then
    read -ra FOUND_TOOLS <<< "$(detect_tools)"
    if [ ${#FOUND_TOOLS[@]} -eq 0 ]; then
        echo "未检测到已安装的 Agent 工具目录（hermes / claude-code / codex）。"
        echo "请使用 --tool custom --skills-dir /path/to/skills 指定目标目录。"
        exit 1
    elif [ ${#FOUND_TOOLS[@]} -eq 1 ]; then
        TOOL="${FOUND_TOOLS[0]}"
        echo "检测到工具：$(tool_display_name "$TOOL")，将安装到对应目录。"
        echo ""
    else
        echo "检测到多个已安装工具，请选择安装目标："
        for i in "${!FOUND_TOOLS[@]}"; do
            dir="$(resolve_skills_dir "${FOUND_TOOLS[$i]}")"
            echo "  $((i+1))) $(tool_display_name "${FOUND_TOOLS[$i]}")  ($dir)"
        done
        echo ""
        printf "请输入编号："
        read -r AUTO_CHOICE
        idx=$((AUTO_CHOICE - 1))
        if [ "$idx" -lt 0 ] || [ "$idx" -ge ${#FOUND_TOOLS[@]} ]; then
            echo "无效选择，退出。"
            exit 1
        fi
        TOOL="${FOUND_TOOLS[$idx]}"
        echo ""
    fi
fi

# ─── 解析目标 Skills 目录 ────────────────────────────────────────────────────

DEST=""
if [ "$TOOL" != "skip" ]; then
    if [ "$TOOL" = "custom" ]; then
        if [ -z "$SKILLS_DIR_ARG" ]; then
            printf "请输入目标 Skills 目录路径："
            read -r SKILLS_DIR_ARG
            SKILLS_DIR_ARG="${SKILLS_DIR_ARG/#\~/$HOME}"
        fi
        if [ -z "$SKILLS_DIR_ARG" ]; then
            echo "错误：未指定 --skills-dir，退出。"
            exit 1
        fi
        SKILLS_BASE="$SKILLS_DIR_ARG"
    else
        SKILLS_BASE="$(resolve_skills_dir "$TOOL")"
    fi

    mkdir -p "$SKILLS_BASE"
    DEST="$SKILLS_BASE/$SKILL_NAME"
fi

# --workspace 保留为可选目录初始化，不再绑定安装副本的运行路径。
WORKSPACE_PATH=""
if [ -n "$WORKSPACE_ARG" ] || [ "$TOOL" = "skip" ]; then
    WORKSPACE_PATH="$(python3 - "$WORKSPACE_ARG" <<'PYWORKSPACE'
from pathlib import Path
import sys
print(Path(sys.argv[1] or Path.cwd()).expanduser().resolve())
PYWORKSPACE
)"
    mkdir -p "$WORKSPACE_PATH/briefs" "$WORKSPACE_PATH/research" "$WORKSPACE_PATH/output"
    echo "Workspace initialized: $WORKSPACE_PATH"
    echo "此参数仅初始化目录；运行时请从该目录启动任务，或向 Agent 明确指定工作区。"
fi

# ─── 安装 Skill ──────────────────────────────────────────────────────────────

if [ -n "$DEST" ]; then
    if [ -d "$DEST" ]; then
        printf "检测到已安装的旧版本 %s，是否覆盖？个人配置将被替换，请先备份 persona.md 和 style.md。(y/n) " "$DEST"
        read -r OVERWRITE
        if [ "$OVERWRITE" != "y" ]; then
            echo "已取消覆盖，保留旧版本。"
            DEST=""
        fi
    fi
fi

if [ -n "$DEST" ]; then
    rsync -a --delete \
        --exclude='.git/' \
        --exclude='.DS_Store' \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        --exclude='briefs/' \
        --exclude='research/' \
        --exclude='output/' \
        "$SKILL_SRC/" "$DEST/"

    cp "$SCRIPT_DIR/../LICENSE" "$DEST/LICENSE"
    cp "$SCRIPT_DIR/../README.md" "$DEST/README.md"
    echo "Skill installed: $DEST"
fi

# ─── 完成提示 ────────────────────────────────────────────────────────────────

echo ""
echo "========================================="
echo " 安装完成！"
echo "========================================="
echo ""
echo "运行时工作区：用户明确指定的路径优先，否则使用任务启动目录。"
echo ""
if [ -n "$DEST" ]; then
    echo "按需修改作者配置："
    echo "  $DEST/references/persona.md"
    echo "  $DEST/references/style.md"
    echo "在稿件目录启动 Agent，或明确指定工作区，再提出写作/审校请求。"
else
    echo "未安装 Skill；如需安装，请重新运行并选择安装目标。"
fi
