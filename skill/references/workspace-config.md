# workspace-config.md

## Workspace Resolution

The shared default workspace is:

```text
~/Documents/workspace/guage-write-flow
```

The installer replaces this default with the selected absolute workspace path in the installed copy and binds the script defaults to the same path. Every agent using this skill must read this file and use the same path. Do not select a different workspace based on agent-local environment variables or machine-local discovery.

Resolve the runtime workspace at the start of every session using this priority order:

1. If the user explicitly provides a workspace path in this conversation → use that path
2. Otherwise → use the shared default workspace above

The final Markdown for a completed longform article is saved by default after Step 5 passes. Research JSON, outlines, and review reports are not saved by default. Do not write runtime files into the installed Skill directory. Draft/rewrite/review records use a system temporary directory and are cleaned after completion unless retention is requested. Authorized maintenance of the persistent style handbook and its Skill patch version is a separate exception; follow style-guide.md and do not publish private feedback.

## Runtime Directories

| Directory | Purpose |
|-----------|---------|
| `briefs/` | Candidate material pool. Only the current topic's selected, relevant, readable materials constrain this run. Accept PDFs, Markdown, text files, screenshots, DOCX, spreadsheets, JSON, and web excerpts. |
| `research/` | Research JSON, only when the user explicitly asks to save research results. |
| `output/` | Final longform Markdown articles, written after quality checks; other content only when the user explicitly asks to save it. |

## Save Destination

- A completed longform article defaults to `~/Documents/workspace/guage-write-flow/output/`; if the user specifies an article path or workspace, use it.
- Name articles `{Asia/Shanghai YYYYMMDD}-{title-slug}.md`. Slugs use lowercase text, retain Unicode letters and digits, replace runs of punctuation/whitespace with one hyphen, and trim edge hyphens. `scripts/save_article.py` implements this rule, date selection, strict validation, and collision handling; use it for every completed longform article so agents produce the same path.
- If a file with that name already exists, append `-2`, `-3`, etc. before `.md`; never overwrite by default.
- Do not save briefs, outlines, research JSON, or review reports unless the user asks.
- A saved article does not imply saving its research JSON.

## Multi-Format Brief Handling

Run `prepare_research.py inventory --workspace <resolved-workspace>` to list visible regular candidates and hashes. Hidden files/directories such as `.DS_Store` are not materials. A nonempty shared pool does not select the research mode by itself.

For each current candidate, generate a material entry:

- **文件名**：原始文件名
- **类型**：PDF / Markdown / TXT / DOCX / 图片 / 表格 / JSON / 其他
- **读取状态**：成功 / 失败
- **提取摘要**：主要内容要点（100字以内）
- **可信度备注**：来源性质（用户原创素材、截图、第三方文章等）
- **本轮相关性**：relevant / irrelevant / uncertain，附明确 reason 与 summary
- **文件绑定**：保留 inventory 的绝对 path 与 sha256，文件变动后重新读取、分类和预检

Files that cannot be parsed must appear in an "未解析文件清单" — never silently skip them.

Pass the classified manifest to `prepare_research.py route` via stdin. Keep its complete output as the research JSON's `preflight`; the validator recomputes it against current files. Relevant readable inputs use `brief_first_verify_mode`; no relevant inputs use `publish_mode`, including when every old shared file is irrelevant. Uncertain or failed reads produce an explicit unresolved list and block a claimed preflight pass.

When the user explicitly selects files, run inventory with repeatable `--select /absolute/file`, retain the returned nonempty `selected_paths` and cover that selection exactly. Explicitly selected existing files may be outside the shared pool. `selected_paths: []` is allowed only with nonempty `selection_reason` and `selection_source_ref` recording the user's express instruction to use no local materials. Otherwise omit selected_paths and cover the full visible pool; do not silently replace it with an empty selection. Source references are recorded instructions, not independent identity proof.

Inventory, route and validation are read-only, emit stdout and do not save research or manipulate the pool. A missing workspace/briefs directory is an empty candidate pool and is not created by preflight. Unreadable directories, changed hashes, missing entries or duplicate paths require correction. Automatically discovered symlinks require explicit selection of the actual files instead of silently following them.

## Safety Rules

- Never delete or overwrite files in `briefs/`.
- Never overwrite an existing file without explicit instruction; use a non-conflicting filename instead.
- Never hardcode API keys or credentials in any output file.
