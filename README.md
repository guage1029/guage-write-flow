# guage-write-flow

![skill version](https://img.shields.io/badge/skill-v0.0.5-blue)

中文技术文章和公众号长文写作 Agent Skill。提供调研、选题、两阶段创作、多轮审校和 Markdown 交付，也支持直接审校已有文章、降低 AI 味。

**职责边界：** 不提供图卡分卡文案、配图策划、图片生成或生成图片的回填。用户已有的截图仍可作为素材或证据读取、核验和引用。配图是独立任务，不影响文章流程单独完成。

遵循 [Agent Skills 开放标准](https://agentskills.io/specification)。安装脚本支持 Hermes、Claude Code、Codex，以及通过 `--tool custom --skills-dir` 指定的其他 Agent Skills 目录。

## 安装

需要 Bash、Python 3.9+ 和 rsync；打包另需 zip/unzip。Python 校验脚本仅使用标准库，`quick_validate.py` 有 PyYAML 时会使用它解析 frontmatter。

```bash
git clone https://github.com/guage1029/guage-write-flow.git
cd guage-write-flow

# 选择一种安装目标；workspace 可以使用已有稿件目录
bash scripts/install.sh --tool codex --workspace ~/Documents/workspace/writing
# bash scripts/install.sh --tool claude-code --workspace ~/Documents/workspace/writing
# bash scripts/install.sh --tool hermes --workspace ~/Documents/workspace/writing
# bash scripts/install.sh --tool custom --skills-dir ~/.your-agent/skills --workspace ~/Documents/workspace/writing

# 不传参数时使用交互式安装向导；--tool auto 可检测已安装工具
# bash scripts/install.sh
```

Skill 安装到目标 Skills 目录下的 `guage-write-flow/`。安装目录存放指令与脚本，工作区独立存放输入材料和成品文章。

安装时工作区选择顺序：`--workspace` → `GUAGE_WRITE_FLOW_WORKSPACE` → 旧变量 `AI_WRITE_FLOW_WORKSPACE` → 交互询问。环境变量用于安装时选择目录；安装脚本将绝对路径绑定到安装副本的 `references/workspace-config.md`、预检脚本和保存脚本。

运行时读取安装副本的工作区配置；用户在任务中明确指定的路径优先。另选工作区时，保存命令应传 `--output-dir <工作区>/output`，与预检使用同一目录。直接使用未安装的源码时，默认工作区为 `~/Documents/workspace/guage-write-flow`。

### 从 ai-write-flow 更新

项目和安装目录现在统一命名为 `guage-write-flow`。已有 Git 检出可更新远端地址：

```bash
git remote set-url origin https://github.com/guage1029/guage-write-flow.git
```

重新安装时可继续传原有 workspace 路径，例如 `~/Documents/workspace/ai-write-flow`，无需移动素材或文章。脚本不会自动删除旧的 `ai-write-flow` 安装目录；确认新版本可用后，自行停用旧 skill，避免同名能力重复匹配。覆盖已有 `guage-write-flow` 安装前会询问；覆盖会同步分发包并清除已移除的规则文件，请先备份个人定制。

## 使用

完整写作：

```text
使用 guage-write-flow，帮我写一篇关于 MCP 工具开发的文章。
```

已有文章审校：

```text
帮我审校这篇文章，降低 AI 味，保留我的表达和已有截图。
```

只检查：

```text
只检查这篇文章的问题，先别改正文。
```

审校快捷入口跳过 Steps 1–4，直接进入 Step 5。局部润色只报告结构或证据缺口，不擅自扩写、追加事实或重做选题；只检查时不输出修订全文、不落盘。

## 长文主流程

| 步骤 | 行为 | 进入下一步的条件 |
|---|---|---|
| Step 1 工作区与素材 | 盘点文件、读取内容、判断本轮相关性并保留哈希，生成 preflight | 清单完整，读取与相关性缺口已处理 |
| Step 2 调研核验 | 核查来源原文、可用事实、排除项和差异，运行 JSON 校验 | 校验通过，未解决差异不得放行 |
| Step 3 选题 | 给出选题、标题、证据要求和工作量 | 用户选定选题与工作标题 |
| Step 4 两阶段创作 | 先确认骨架和三份清单，再写正文 | 骨架获确认；三份清单齐全 |
| Step 5 多轮审校 | R1–R5 读者兑现、内容、口吻、作者手迹、AI 味与格式检查 | 完整稿通过规定门禁 |
| Step 6 交付 | 默认保存 Markdown，报告绝对路径 | strict 校验通过并写入成功 |

调研按**本轮素材的相关性和可读性**选择模式：有相关可读素材用 `brief_first_verify_mode`，没有则用 `publish_mode`；共享目录非空不代表材料与本轮相关。读取失败或相关性待确认时先解决缺口。旧研究 JSON 重新使用前仍须补预检、检查来源与时效。

骨架阶段必须包含【读者兑现映射表】【证据账单】【自设参数清单】。R1–R4 覆盖冷启动、标题承诺、证据使用和自设参数披露，完整稿不通过时返工；R5 检查结尾是否提供新信息。

实测、接入和评测文章需要真实产物证据。明确为 `source-analysis` 的资料解析需要真实来源数据表和正文 HTTP(S) 来源链接，不能冒充作者亲测。检查脚本只能识别已编码的结构、格式和证据形式，不能证明图片真实、来源可靠或文章已经接近作者口吻。

## 输出与个人定制

- 完整长文默认保存到 `<workspace>/output/YYYYMMDD-title-slug.md`，日期使用 Asia/Shanghai；重名追加序号，禁止覆盖。
- 用户要求只在对话中交付时不保存。审校结果、骨架和研究 JSON 默认留在对话中，明确要求保存时才写文件。
- 审校报告不写入最终文章文件。运行产物不得写入 skill 安装目录。
- 新文章默认参考瓜哥的作者画像；安装后可修改 `references/persona.md`。已有文章优先保留原作者声音。
- 调整工作区时重新运行安装脚本，以同步规则与脚本默认路径。

## 仓库结构

```text
guage-write-flow/
├── skill/                  # 可分发的 skill，安装时只复制此目录
│   ├── SKILL.md
│   ├── references/         # 事实、调研、作者声音、审校及工作区规范
│   ├── assets/brief-template.md
│   └── scripts/           # prepare_research、validate_research、check_article、save_article 及测试
├── scripts/               # 安装、打包与分发自检
├── evals/                 # 行为用例定义与脚本场景校验
├── docs/open-source-guide.md
├── quick_validate.py      # 分发包基础结构检查
└── LICENSE
```

## 验证与打包

```bash
python3 quick_validate.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skill/scripts -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_distribution.py
PYTHONDONTWRITEBYTECODE=1 python3 evals/run_evals.py
bash scripts/package-skill.sh dist 0.0.5
```

`evals/run_evals.py` 校验用例结构、文件引用并执行脚本场景；**不会实际运行 Agent 多轮对话**。行为场景需要在独立会话中验收，不能将用例定义检查通过当成行为测试通过。

调研 JSON、文章检查均支持 stdin，例如：

```bash
python3 skill/scripts/validate_research.py - --report < research.json
python3 skill/scripts/check_article.py - --strict --article-type source-analysis < article.md
python3 skill/scripts/save_article.py --article-type source-analysis --output-dir /your/workspace/output < article.md
```

不要提交个人素材、运行产物、密钥或凭据；默认作者画像可按需调整，测试素材中的数字和产品表述不能当作发布事实。

## 许可证

MIT
