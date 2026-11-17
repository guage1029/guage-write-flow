# guage-write-flow

![skill version](https://img.shields.io/badge/skill-v0.0.11-blue)

面向中文技术文章和公众号长文的 Agent Skill：调研核验、选题、两阶段创作、独立风格审校和 Markdown 交付。内置可直接使用的基础人设与风格模板，用户可按自己的身份、读者和表达偏好修改。

也支持已有文章润色、降低 AI 味及只检查。已有文章默认保留原作者声音。非技术文体可以自行扩展，但需检查调研、审校与脚本规则，不能保证只改人设就适配小说或广告文案。不负责图卡分卡文案、配图策划、图片生成及回填；已有截图仍可作为素材或证据。

## 运行要求与安装

- 宿主需要能够加载 Skill、读取引用文件、执行 Python 脚本、使用临时目录并保存文件。没有脚本执行能力的纯聊天环境不能完成全部门禁。
- Python 3.9+，并有可用的 `Asia/Shanghai` 时区数据。写作脚本只使用标准库；仓库基础校验器可选使用 PyYAML，没有时使用简化解析。
- 安装脚本需要 Bash、Python 和 rsync；打包另需 zip/unzip。也可手动复制目录到宿主支持的 Skills 位置。
- 完整调研需要搜索和网页原文读取能力。Tavily、Exa 可选，具体顺序与降级规则见下文。
- PDF、DOCX、图片和表格的内容提取依赖宿主。预检脚本只负责盘点、哈希和流程路由，不附带这些格式的解析器；无法读取时会报告缺口。

```bash
git clone https://github.com/guage1029/guage-write-flow.git
cd guage-write-flow

# 选择一种安装目标
bash scripts/install.sh --tool codex
# bash scripts/install.sh --tool claude-code
# bash scripts/install.sh --tool hermes
# bash scripts/install.sh --tool custom --skills-dir /path/to/skills
# bash scripts/install.sh --tool auto
# 不带参数会进入安装目标选择向导
```

安装目录是目标 Skills 位置下的 `guage-write-flow/`，包含指令、脚本、README 和 MIT 许可证。手动安装时，复制 `skill/` 的内容，并附带仓库的 README.md 和 LICENSE；解压发布 zip 可直接得到完整的同名目录。

安装脚本可选接受 `--workspace /path/to/writing`，仅初始化 `briefs/`、`research/`、`output/`，不把路径绑定到安装副本。`--tool skip --workspace /path/to/writing` 只初始化目录。安装工具的目录选择沿用宿主现有环境变量；旧的 `GUAGE_WRITE_FLOW_WORKSPACE` 与 `AI_WRITE_FLOW_WORKSPACE` 不再决定写作工作区。

安装目标提供 Hermes、Claude Code、Codex 和自定义目录入口；目录安装成功不等于相应宿主的完整对话流程均已实测。当前变更已在 macOS 验证脚本、隔离安装和打包；Windows、Linux 及各宿主端到端对话尚未验证。

## 第一次使用

安装后无需先填写个人资料，默认以技术解释与资料分析视角工作，不虚构作者职业、经历或感受。在稿件目录启动任务，或者直接向 Agent 指定工作区。

完整写作：

```text
使用 guage-write-flow，围绕 MCP 工具开发写一篇技术文章，
读者是有 Python 基础、刚开始使用 Agent 的工程师。
```

带自己的素材写作：

```text
工作区是 /path/to/writing。基于 briefs 中的素材写一篇技术文章，
重点回答方案怎么接入、实际效果如何、有哪些限制。
```

已有文章审校：

```text
润色下面的文章，降低 AI 味，保留我的声音和已有截图。
```

只检查：

```text
只检查下面文章的问题，不改写正文，不保存文件。
```

完整写作会在“选题与工作标题”和“文章骨架”两处等待用户确认；正文证据促使标题需要调整时，也先确认新标题。调研记录、脚本检查和审校记录由 Agent 处理，用户不用手填内部 JSON。

审校快捷入口跳过 Steps 1–4。局部润色记录结构或证据缺口，不自动扩写、追加事实或重做选题；只检查不输出修订全文、不落盘。

## 搜索顺序与受限网络

每个独立问题按 **Tavily → Exa → 宿主内置 Web Search** 使用工具，不要求三种工具全跑。前一个工具提供足够证据后停止；需要独立复核时才继续。顺序代表工具使用偏好，不代表来源可信度排名，官方资料仍优先于社区转述。

| 情况 | 工作流如何处理 |
|---|---|
| 未配置 Tavily 或 Exa | 记录不可用及原因，继续下一个工具；它们不是必装依赖 |
| 网络受限、权限不足、调用报错 | 如实记录原因并降级，不反复调用已确认不可用的工具 |
| 没结果、缺少一手来源或证据不足 | 继续下一工具，只补查缺口 |
| 只有内置搜索可用 | 记录前两个工具不可用后使用内置搜索，事实标准保持不变 |
| 用户给出已知链接 | 直接读取原文，无需先搜索或补齐形式上的搜索轮次 |
| 搜索全不可用且给定来源也不足 | 报告阻塞，不把未核实内容当作确定事实；仍可按范围局部润色或只检查 |

Skill 使用宿主已经配置的工具，不自动安装 Tavily/Exa、登录、修改凭据或网络配置。Tavily 可通过现有连接器或 CLI 使用，Exa 可通过现有搜索工具使用；工具名称以宿主实际暴露的能力为准。搜索发现来源后仍需读取原文，摘要、highlights 和搜索排名本身不能代替证据。

## 修改人设与写作风格

以下两个文件都位于 **Skill 安装目录**中，可直接编辑，也可明确要求 Agent 帮你修改。仓库中对应路径多一层 `skill/` 前缀。

```text
guage-write-flow/
└── references/
    ├── persona.md    # 谁写、写给谁、写什么
    └── style.md      # 怎么表达、怎么审校
```

| 文件 | 可修改内容 | 生效阶段 |
|---|---|---|
| `references/persona.md` | 真实作者身份、目标读者、发布平台、内容领域、立场与声音概述 | Step 3 选题、Step 4 创作、Step 5 审校 |
| `references/style.md` | 语气、术语密度、句段节奏、结构偏好、禁用表达、可选本人样文 | Step 4 创作、Step 5 风格审校；Step 6 校验当前规则绑定 |

例如，人设可以改为“面向有开发基础的后端工程师，主要写数据库与服务端实践”；风格可以改为“语气正式，减少设问，保留完整术语和必要限定”。也可选择轻松表达，不强制熟人聊天、个人口头禅或虚构第一人称。

两份模板内部都有字段说明，不修改也能执行。本轮明确要求与事实准确性优先；风格文件的具体规则优先于人设中的概括性声音描述，请配套检查冲突。已有文章润色默认保护原作者声音，明确要求转换风格时才切换。

部分 Markdown 格式还有脚本硬检查：唯一 H1、至少一个 H2、标题逐级、禁止 H5+、H4 连续圈号。H2 默认中文编号可在本轮调整；改变硬检查规则则需同时修改脚本和测试，不能只改风格文件。

### 学习反馈与升级

- “这段短一点”等局部反馈默认仅用于本轮文章，不自动成为长期规则。
- 明确要求更新人设/风格，或授权持续维护后，Agent 才按授权范围写回有依据的偏好。每轮仍复盘；没有新依据或未获写回授权时保持文件不变。
- 用户只确认选题、骨架或事实，不代表确认风格。Agent 自评、生成样句和脚本通过也不能作为用户偏好。
- 私人样文、身份信息和反馈不自动进入公共模板或推送远端。样文用于学习表达，不移用其中的经历、数据与结论。
- 升级前将两份文件备份到安装目录和发布目录之外，再对比新版模板合并个人修改。安装覆盖会替换个人配置并清除移除的文件，第一版不做自动迁移；请勿把唯一备份放在会被覆盖的目录中。
- 从旧版升级时，旧风格文件名为 `style-guide.md`，新文件名为 `style.md`。已有临时审校记录因文件名或规则哈希变化需重新生成；已保存文章不会被自动修改。
- 旧版安装时绑定的工作区不再作为默认值；在原稿件目录启动任务，或在本轮明确指定该路径即可，无需移动素材或重新绑定。

## 工作区与输出

运行时优先使用用户明确指定的工作区，否则使用任务启动时的工作目录，解析为绝对路径后本轮固定使用。没有明确工作目录时先询问，不猜测个人目录，不用 Skill 安装目录保存稿件。

- `briefs/` 是候选材料池，目录不存在按空素材处理；只有本轮相关且成功读取的材料进入创作约束。
- `output/` 保存通过审校的最终 Markdown；文件名为 `YYYYMMDD-title-slug.md`，日期使用 Asia/Shanghai，重名自动追加序号，不覆盖。
- 单独指定输出文件或目录只改变保存位置，不改变素材工作区。相对输出路径按已解析工作区解释；路径不可写时报告错误。
- 用户要求只在对话中交付时不保存。研究 JSON、骨架与审校报告默认不保存；临时初稿、终稿与审校记录完成后清理，用户要求保留时例外。审校报告不混入正式文章。

Agent 必须给预检和保存命令传入同一个 `--workspace`，不受中途切换执行目录影响。直接运行脚本且省略此参数时，脚本使用进程当前目录。

## 来源时效

30 天约束易变事实的重新核验时间，不要求所有资料最近发表：

| 事实 | 核验要求 |
|---|---|
| 当前版本、价格、功能、额度、可用性及“最新”判断 | 写作前 30 天内重新核验当前资料、版本与适用条件 |
| 发布、更新等事件 | 记录真实事件日期，旧事件不自动代表最新状态 |
| 技术原理、经典论文、稳定背景 | 不因来源年龄阻断，检查原始来源、适用范围与修正 |
| 无明确发布日期的官方文档 | 可使用，但须实际读取原文、核对适用条件并记录核验时间 |

研究 JSON 中 `source_date` 记录原文发布日期或更新日期，未知时用 null；`verified_at` 记录实际核验时间，不能互换。claim 使用 `fact_type: dynamic/event/stable`，event 另记 event_date，省略类型时按 dynamic 保守检查。旧研究记录缺少核验时间时须补做实际核验，不直接填今天日期。事实类型由 Agent 判断，不能为绕过门禁把当前状态标成稳定知识。

## 流程与审校边界

| 步骤 | 主要行为 | 交接条件 |
|---|---|---|
| Step 1 工作区与素材 | 读取、分类、哈希及 preflight | 清单完整，无未处理读取/相关性缺口 |
| Step 2 调研 | 原文读取、来源与事实核验 | JSON 校验通过，差异已处理 |
| Step 3 选题 | 角度、标题、证据要求 | 用户选定选题与工作标题 |
| Step 4 创作 | 确认骨架，再写正文并冻结初稿 | 骨架及三份清单齐全，获得确认 |
| Step 5 审校 | 读者兑现、内容、逐段改写、全文复查与手册复盘 | 问题处理完成，记录及机械检查通过 |
| Step 6 交付 | 默认保存 Markdown 并给出绝对路径 | strict 检查通过且写入成功 |

骨架包含读者兑现映射表、证据账单与自设参数清单。实测/接入/评测需至少两类真实产物；官方资料解析使用 `source-analysis`，正文须有真实来源数据表与 HTTP(S) 来源链接，不冒充亲测。

逐段风格审校是必经步骤，有多少问题处理多少，不按改写数量或轮数过关。记录绑定真实初稿、终稿与规则哈希，覆盖全文并登记问题及六项风格依据；模板默认待审，禁止批量填通过。脚本通过只证明已编码的结构、记录与一致性检查通过，不能保证事实绝对正确、证据真实或文章已经像作者本人。

## 验证与打包

以下命令均在仓库根目录执行：

```bash
python3 quick_validate.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skill/scripts -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_distribution.py
PYTHONDONTWRITEBYTECODE=1 python3 evals/run_evals.py
bash scripts/package-skill.sh dist 0.0.11
```

`evals/run_evals.py` 检查用例定义并执行脚本场景，不执行 Agent 多轮对话。完整写作、风格遵从和工具调用的语义质量仍需真实会话验收。安装后也可运行 `python3 quick_validate.py /path/to/installed/guage-write-flow`，这里的 quick_validate.py 是仓库根目录的工具。

脚本入口示例（路径替换为实际值）：

```bash
python3 skill/scripts/prepare_research.py inventory --workspace "/path/to/writing"
python3 skill/scripts/validate_research.py - --report < research.json
# 实际逐段审校后生成待填写记录，模板自身不能通过门禁
python3 skill/scripts/review_style.py --draft "/tmp/draft.md" --final "/tmp/final.md" > "/tmp/review.json"
# 按审校契约实际完成全部检查并填写记录，再检查与保存
python3 skill/scripts/check_article.py "/tmp/final.md" --strict --article-type source-analysis --draft "/tmp/draft.md" --review "/tmp/review.json"
python3 skill/scripts/save_article.py --workspace "/path/to/writing" --article-type source-analysis --draft "/tmp/draft.md" --review "/tmp/review.json" < "/tmp/final.md"
```

仓库的 `skill/` 是运行源码，`scripts/` 提供安装、打包和分发自检，`evals/` 保存用例，`docs/open-source-guide.md` 说明维护边界。发布包排除缓存与工作区产物，不收集个人素材。

## 许可证

沿用仓库 LICENSE 中的 MIT 许可证与原版权声明。安装与 zip 包包含同一许可证。
