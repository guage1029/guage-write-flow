# research-config.md — 调研行为规范

> Step 2 的调研行为与数据契约。机器门禁由 `scripts/validate_research.py` 实现。
> 输出门禁（哪些 claim 可进入最终输出）见 `references/fact-policy.md`。

---

## 搜索工具与执行顺序

- 每个独立调研问题使用一个 `task_id`。默认 Tavily → Exa → Agent 内置 Web Search；不强制三种工具全跑。
- Tavily 使用已配置的搜索工具或 `tvly search --json`；Exa 使用 `web_search_exa`；内置 Web 使用运行环境提供的搜索能力。不可用时记录 `unavailable` 和真实原因，不自动安装、登录或修改工具配置。本工作流的可用性检查与降级规则优先于搜索辅助 skill 的自动安装要求。
- 前工具不可用、报错、无结果、无一手来源或证据不足时，记录对应 outcome 和 reason 后进入下一工具；不得跳级。前工具成功后，只有独立复核需要才换工具，并填写 `advance_reason: independent_crosscheck`。
- 用户给出或素材包含的已知 URL 直接读取，记为 `discovered_by: direct`，无需为了填记录而搜索。
- 搜索发现页面后读取来源原文：Tavily Extract、Exa Fetch 或内置 Web Fetch/Open。Tavily 搜索实际返回完整原文时可记为 `tavily_search_raw`，不重复抓取；摘要或 highlights 不算原文。full_text 表示读取原始页面内容，可为相关原文片段，不要求抓取整个站点。
- 独立问题可以并行，但每个 task_id 内部保持上述顺序。该 skill 不自动要求组建多智能体团队。
- 所有拟用于写作的事实必须关联成功读取的来源原文。工具排名不改变来源 Tier。
- 每项拟用事实有来源、必要的交叉核查完成且无未解决差异时停止搜索；不足时只补查缺口。
- 如所有工具都不可用，保留失败记录、报告阻塞，不伪造调研成功。

**可验证边界：** 验证器检查 Agent 提交的记录及引用一致性，无法独立证明真实工具调用或来源权威性。不得虚构工具记录、读取状态或来源日期。

## 每轮交付与校验

规划 → 按问题执行 → 汇总核查 → 交付。开始前列出任务 ID、调研问题、已有材料和所需证据；默认展示后继续，方向不明时再澄清。

JSON 在当前上下文保留，不默认落盘。每轮通过标准输入运行：

```bash
python3 {skill_root}/scripts/validate_research.py - --report
```

实际 JSON 从 stdin 传入；不要把示例占位符当成真实记录。脚本输出固定五部分：本轮目标、实际改动、验证结果、风险与阻塞、下一轮建议，以及独立计算的通过/失败结论。用户报告中用事实 ID 与来源链接说明结论；调研没有改文件时如实注明。

退出码非零：仍可展示失败报告，停止进入选题/创作，修复后复查。`explore_mode` 允许 claims 为空；其线索不得直接作为发布事实。完整写作前仍须通过 publish/brief 核验。

执行清单：任务范围明确；工具降级有记录；已读原文；事实可追溯；差异已解决；缺口已列出；校验通过后再交接。

## 执行模式

| 模式 | 触发时机 | 门禁状态 |
|------|---------|---------|
| `brief_first_verify_mode` | Step 2，预检确认有本轮相关、读取成功的素材 | Stage A→B→C 三段式，Stage C 有差异则阻断 |
| `publish_mode` | Step 2，无本轮相关素材；共享目录全是无关材料也适用 | 全部 4 层生效，任一不达标则阻断 |
| `explore_mode` | Step 3 选题讨论（为角度探索提供线索） | 仅执行 Layer 1+2，不做 Claim 核查 |

### 素材预检是模式的唯一计算入口

先运行 `python3 {skill_root}/scripts/prepare_research.py inventory --workspace {workspace}`，再阅读、分类返回的候选。默认覆盖共享 briefs/ 的全部可见常规文件，忽略系统隐藏项；显式 selected_paths 则覆盖用户本轮选定的文件。脚本不做语义分类。

将下列清单从 stdin 传给 `prepare_research.py route --workspace {workspace}`；sha256 必须复制对应 inventory 的实际值，不能使用占位符：

```json
{
  "topic": "本次准确主题",
  "materials": [
    {
      "path": "/absolute/workspace/briefs/actual-file.md",
      "sha256": "实际 inventory 返回的 SHA-256",
      "relevance": "irrelevant",
      "read_status": "success",
      "reason": "实际阅读后，与本次主题无关的具体理由",
      "summary": "实际素材要点"
    }
  ]
}
```

relevance 取 relevant/irrelevant/uncertain；read_status 取 success/failed。相关性由 Agent 根据用户任务判断并给理由；代码只验证清单、文件和路由一致性，不证明语义判断正确。未解析或待确认材料输出 unresolved_materials 和具体 issues、can_proceed=false；先由团队解决可修复问题，确需用户信息才提问，不能把无关旧资料当成本轮约束。

明确选取文件时可运行 inventory --select /absolute/file（多个文件重复 --select），返回的非空 selected_paths 原样保留，可引用共享池外的真实文件。用户明确要求完全不用本地素材时才允许 selected_paths=[]，同时填写 selection_reason、selection_source_ref；引用真实指令，不可为方便而编造。脚本保留并校验字段完整性，不能独立认证对话授权。

把 route 的完整 JSON 输出原样嵌入研究 JSON 的 preflight。validate_research.py 会重新盘点当前范围并计算哈希、mode、can_proceed，核对 topic 与本次研究一致；不能只提交自填 mode 或删除排除项。explore_mode 保留其探索模式，但仍携带同主题预检，不能借探索模式绕过未解决材料。旧研究数据不自动迁移；重新用于新稿前补充预检，历史记录不因读取被修改。

---

## brief_first_verify_mode 三段式规范

仅 preflight.usable_materials 中的本轮素材（截图、手写数据、简报）定义为 **`Tier 1 Candidate`**，不是 `Tier 1 Final`。须经 Stage B 核查通过后才能升级为 `verified`；excluded_materials 与 unresolved_materials 不进入候选事实。

### 高风险字段（Stage A 必须提取，Stage B 必须核查）

| 字段类型 | 说明 |
|---------|------|
| 产品名称 | 相近名称但主体不同，容易混淆 |
| 产品定位 | '专为 X 设计' vs '支持 X' 的归属差异 |
| 发布主体 | 公司名、团队、上下级关系 |
| 版本 / 日期 | 版本号、发布时间、截图时效性 |
| 截图功能归属 | 截图中演示的功能是否归属于该产品 |
| 价格 / API / 兼容性 | 会随时间变动的字段，需确认最新性 |

### Stage B 核查原则

- 只验证高风险字段，不机械跑与候选事实无关的 Layer
- 外部来源按下方 Source Tiers 判断质量
- 候选事实与外部来源**一致** → 标记 `verified`
- **找不到**外部来源 → 候选保留 `unverified`，原断言移入 `excluded_claims`，不得靠归因直接写入正文；有其他已核实事实时可继续，否则阻断。弱化表达另立 claim 核验。
- 候选事实与外部来源**矛盾** → 标记 `discrepancy`，**必须阻断**

### 差异门禁触发条件（任一满足即阻断）

- 用户截图和公开资料表述不一致
- 产品名称相近但主体不同
- 功能演示成立，但官方定位描述不同
- 时间相关信息（版本、定价、可用性）无法确认最新性

---

## 4 层核心机制（publish_mode 使用）

```
Layer 1  主题解析      判断 topic_type → 确定权威来源形态
Layer 2  来源分层      Tier 1-4，事实结论只接受 Tier 1/2 支撑
Layer 3  Claim 核查    原子级事实拆解 + supported/unverified/contradicted
Layer 4  时效门禁      30 天统一硬门禁，不达标直接阻断
```

---

## Layer 1：主题类型枚举

| topic_type | 涵盖子类型 | 权威来源应包含 |
|-----------|-----------|-------------|
| `product` | 产品发布、模型发布、公司公告、功能更新 | 官网 + 官方文档 + release/changelog + GitHub org |
| `concept` | 技术概念、方法论、学术论文、标准规范 | 原始论文 + 作者主页 + 参考实现 |
| `open-source` | 开源项目、框架、工具库 | GitHub repo + docs + releases + changelog |
| `news` | 行业新闻、投融资、政策法规、收购事件 | 第一手公告 + 原始材料（须 ≥2 个独立来源交叉确认）|

---

## Layer 2：来源分层（Source Tiers）

| Tier | 来源类型 | 能否支撑发布级高风险事实 |
|------|---------|----------------------|
| 1 | 官方文档、release notes、公告、论文原文、GitHub releases | ✅ 是 |
| 2a | **官方维护者声明**：项目创始人/核心维护者以官方身份发布的博客、GitHub Issue/PR 评论、公开演讲（明确代表项目立场）| ✅ 是 |
| 2b | **第三方分析线索**：非官方技术博客、媒体分析、实验室报告、社区转述 | ❌ 仅用于找线索，不支撑高风险字段 |
| 3 | 权威科技媒体（TechCrunch、The Verge 等）| ❌ 仅用于找线索 |
| 4 | 社区帖子、论坛、问答 | ❌ 仅用于找线索 |

**高风险字段（版本号、性能数据、价格、模型名、平台数量、安装命令、发布时间）必须由 Tier 1 或 Tier 2a 来源支撑。**
Tier 2b 不得作为高风险字段的充分来源，即使该来源看起来"权威"。

---

## Layer 3：Claim 级 JSON Schema

调研结果使用以下 JSON 结构，并在当前写作上下文中保留。默认不写入文件；只有用户明确要求保存研究结果时，才按 `workspace-config.md` 的共享路径规则保存：

```json
{
  "topic": "string",
  "topic_type": "product | concept | open-source | news",
  "research_date": "YYYY-MM-DD",
  "mode": "brief_first_verify_mode | publish_mode | explore_mode",
  "preflight": {
    "policy_version": "1",
    "topic": "string",
    "workspace": "/absolute/workspace",
    "materials": [],
    "mode": "publish_mode",
    "can_proceed": true,
    "usable_materials": [],
    "excluded_materials": [],
    "unresolved_materials": [],
    "issues": []
  },
  "freshness_policy": {
    "max_age_days": 30,
    "blocking": true
  },
  "tier_1_candidates": [
    {
      "field": "string",
      "candidate_text": "string",
      "source": "brief",
      "verification_status": "verified | unverified | discrepancy",
      "discrepancy_note": "string (仅 status=discrepancy 时填写)"
    }
  ],
  "discrepancies": [
    {
      "field": "string",
      "user_claim": "string",
      "external_evidence": "string",
      "source_url": "string",
      "risk": "string"
    }
  ],
  "sources": [
    {
      "tier": 1,
      "title": "string",
      "url": "https://official.example/docs",
      "source_date": "YYYY-MM-DD",
      "task_id": "r001",
      "discovered_by": "tavily",
      "fetched_by": "web_fetch",
      "fetch_status": "success",
      "content_kind": "full_text"
    }
  ],
  "claims": [
    {
      "claim_id": "c001",
      "claim_text": "string",
      "tier": 1,
      "source_url": "https://official.example/docs",
      "source_date": "YYYY-MM-DD",
      "evidence_quote": "string",
      "status": "supported | unverified | contradicted"
    }
  ],
  "quality_check": {
    "citation_coverage": "100%",
    "unsupported_claim_count": 0,
    "contradiction_count": 0,
    "discrepancy_count": 0,
    "stale_source_count": 0,
    "passed": true
  },
  "search_attempts": [
    {
      "task_id": "r001",
      "provider": "tavily",
      "query": "string",
      "outcome": "success",
      "result_urls": [
        "https://official.example/docs"
      ]
    }
  ],
  "excluded_claims": [],
  "round_report": {
    "goal": "本轮问题与范围",
    "changes": "新增或修正的事实、来源；是否修改文件",
    "verification": "检查与证据，未执行项如实说明",
    "risks": "未解决问题；无则写无",
    "next": "进入选题或具体补查任务"
  }
}
```

---

### 新增字段约束

- preflight 必须是 prepare_research.py route 的完整实际输出；上例仅演示空候选形状，不可把占位路径直接当运行结果。需预检的相关文件一旦改变、新增或丢失，重新 inventory、阅读、分类和 route；显式选择范围之外的旧材料不影响该范围。
- `search_attempts[]` 按真实发生顺序填写，按 task_id 分别检查顺序。provider 取 tavily/exa/web；outcome 取 success/unavailable/error/no_results/no_primary_source/insufficient_evidence。非 success 填 reason；成功结果包含 result_urls。
- `sources[]` URL 唯一；搜索发现的 URL 必须对应 search_attempts 的 task_id、provider、result_urls。已知 URL 使用 direct。fetched_by 取 tavily_extract/exa_fetch/web_fetch/tavily_search_raw。
- `claims[]` 仅包含可用的 supported 事实，claim_id 唯一，source_url 必须已登记，tier 和 source_date 与来源一致，evidence_quote 非空。候选与排除项不混入此数组。
- `tier_1_candidates[]`、`discrepancies[]`、`excluded_claims[]` 均为必填数组，无则空数组。未解决的 discrepancy 阻断。
- 非 explore 模式至少一条可用事实。空日期、未来日期、摘要证据、未知来源及不合格 Tier 均阻断。quality_check.passed 是提交声明，不能覆盖脚本独立检查结果。
- 历史研究 JSON 允许保留旧的 `output_mode`、`card_safe_claims` 等图卡字段，不迁移历史记录，不豁免 `preflight`、来源与 30 天时效等通用门禁。

## Layer 4：时效门禁

- **30 天统一硬门禁**，无例外
- 背景材料可用旧资料，但必须显式标注 `"type": "background"`，**不得进入发布正文**
- 任何用于核验的来源没有明确日期 → 视为不合格；列为缺口，不能编造日期。计算日期以 Asia/Shanghai 为准。

---

## 阻断条件

### brief_first_verify_mode（Stage C 触发）

- `tier_1_candidates` 中有任一 `verification_status == "discrepancy"` → 阻断，输出【差异确认】格式，等待用户确认

### publish_mode（Layer 1-4 触发）

- `status == "unverified"` 的 claim 存在
- `status == "contradicted"` 的 claim 存在
- 任何 claim 的 `source_date` 超过 30 天
- 任何来源没有明确日期
- `quality_check.passed == false`
- 发布正文中出现未标注的旧资料
