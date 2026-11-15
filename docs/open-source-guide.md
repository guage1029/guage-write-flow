# 开源分发说明

项目名称、Skill 名称、安装目录和 zip 根目录统一为 `guage-write-flow`。仓库只分发 `skill/` 内的写作能力，不包含图卡文案或配图生产流程。

安装命令、升级方式与职责边界见 [README](../README.md)。

## 安装目标

| 参数 | 默认 Skills 目录 | 环境变量覆盖 |
|---|---|---|
| `--tool hermes` | `~/.hermes/skills` | `HERMES_SKILLS_DIR` |
| `--tool claude-code` | `~/.claude/skills` | `CLAUDE_SKILLS_DIR` |
| `--tool codex` | `~/.codex/skills` | `CODEX_HOME` |
| `--tool custom` | `--skills-dir` 指定的目录 | — |
| `--tool auto` | 检测后选择已安装工具 | — |
| `--tool skip` | 不安装，只初始化 workspace | — |

安装脚本只同步分发包。已有同名安装会先询问是否覆盖；覆盖时删除已从分发包移除的文件，因此应先备份个人定制。旧名称 `ai-write-flow` 的安装副本不会自动删除，也不会移动已有工作区。

## 工作区配置

安装时按 `--workspace`、`GUAGE_WRITE_FLOW_WORKSPACE`、旧变量 `AI_WRITE_FLOW_WORKSPACE`、交互输入的顺序选择目录，转换为绝对路径。

该路径同时写入安装副本的 `references/workspace-config.md`、`scripts/prepare_research.py` 和 `scripts/save_article.py`。不再生成或读取旧的 `workspace-local.md`。安装后的默认路径不依赖某个 Agent 进程临时设置的环境变量；改变目录时重新安装并传入新路径。

运行时用户明确指定的工作区优先。预检传入 `--workspace`；保存到另一工作区时传入 `--output-dir <workspace>/output`。没有执行安装时，源码默认使用 `~/Documents/workspace/guage-write-flow`。

工作区包含：

- `briefs/`：候选材料；按主题判断相关性，不因目录非空直接进入素材核验模式。
- `research/`：仅在用户明确要求保存研究结果时写入。
- `output/`：通过检查后的完整文章；审校报告不混入正文。

安装和打包均不收集工作区内容。不要把个人素材、真实业务数据或凭据加入仓库。

## 维护与验证

- 修改写作能力时同步受影响的脚本、测试、README 和 `evals/evals.json`。
- 新增或升级的保存调用必须传 `--draft` 和 `--review`；初稿分离、逐段改写、全文复查和手册迭代见 `skill/references/style-review.md`。已确认的风格规则集中在 `style-guide.md`，用户未授权时不自行持久化私人反馈。
- 版本写在 `skill/SKILL.md` 的 `metadata.version` 中，README badge 与发布包版本保持一致。
- `quick_validate.py` 检查分发包基本字段及必需文件，不等同于完整 YAML schema 或行为校验。
- 写作脚本单测验证可执行逻辑；`scripts/test_distribution.py` 验证安装路径、兼容变量、隔离保存和 zip 结构。
- `evals/run_evals.py` 执行脚本场景并检查行为用例定义；工作流用例仍需真实 Agent 会话执行。
