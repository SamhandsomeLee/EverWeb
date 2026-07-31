# EverWeb 架构方案 v2.0（冻结版）

> [!WARNING]
> 本文已被 [`EverWeb_Architecture_v2.2_Kimi_First.md`](../architecture/EverWeb_Architecture_v2.2_Kimi_First.md) 取代，仅用于架构演进追溯。文中的“冻结版”只描述当时状态，不再是当前实现基线。

> WebRetriever Challenge 2026 · Protocol III
> 定位：在 v1.0 的领域边界基础上，按官方源码、评分器实现与厂商实况重新校准，以五周内可交付为第一约束

| 项目 | 内容 |
| --- | --- |
| 文档版本 | v2.0.1 |
| 状态 | **已冻结**（Phase A 起以本文为执行基线） |
| 冻结日期 | 2026-07-28 |
| 最近修订 | 2026-07-28：知识层排期定案（§9.7 / §9.8 / §11.1 / §12） |
| 前序文档 | `WebRetriever_Challenge_From_Zero_Architecture_and_Implementation_v1.0.md`（保留为历史参考，不再更新） |
| 工程名 | EverWeb Harness，简称 EverWeb |
| 赛道 | Protocol III，真实网站端到端导航与信息抽取 |
| 主语言 | Python 3.12 |
| 模型 | Phase A: DeepSeek V4 系列；Phase B: Kimi K2.6；Phase C: 混合（待前两阶段达标） |
| 浏览器 | Playwright，经官方传入的 CDP URL 连接 |
| 执行状态记录 | JSONL trace + run.json（非事件溯源） |
| 语义记忆 | EverOS，并行轨道，评测期默认关闭 |

一句话定义：

> **EverWeb 是一个结构化感知、证据驱动、终态可判、失败可回放的 Web Agent Harness。它从指定网站出发，用 Playwright 完成交互，产出既能通过语义判定、又能被评分器的证据通道验证的答案。**

---

## 0. 方案总纲

### 0.1 相对 v1.0 的三处根本性调整

**第一，输出层从「兼容官方格式」升级为「对齐评分器证据通道」。**
逆向 `naveval.py` 后确认：评分器只读四样东西——任务描述、URL 轨迹、经过滤的同域网络请求、最后一张视口截图。**它不读 `actions` 列表。** 我们要主动经营这三个证据通道，而不是被动产出。

**第二，感知层从「混合感知」收敛为「AX 树为主 + 快照 diff」。**
官方基线（UI-TARS 1.5）是纯截图加坐标动作，这是我们最大的能力差，也是投入产出比最高的一块。

**第三，执行模型从异步改为同步 + 进程隔离，状态存储从事件溯源改为 JSONL trace。**
单进程单任务、无重试、无跨进程恢复需求，事件溯源是纯粹的复杂度支出。省下来的预算全部投到抽取与验证上。

### 0.2 三条护城河（按优先级）

1. **终态证据设计**（Finalize 取景 + 操作痕迹 + 干净 capture）—— 成本最低，直接对着评分器
2. **双门禁 + 证据账本** —— 防止假成功，这是本地数字可信的前提
3. **录制回放回归集** —— 决定五周内能迭代多少轮

---

## 1. 不变量

v1.0 的 15 条精简重写为 11 条，每条对应一个真实的失败模式。

| ID | 不变量 | 防的是什么 |
| --- | --- | --- |
| INV-1 | 所有浏览器交互经 Playwright | 规则合规 |
| INV-2 | 终态成功必须同时通过 NavigationGate 与 AnswerGate | 模型自称完成 |
| INV-3 | 没有 EvidenceAtom 支撑的字段不得进入 `agent_answer` | 幻觉补答案 |
| INV-4 | 完整集合题无 StopProof 不得判成功 | 漏项 |
| INV-5 | 网页、文档、记忆内容一律是不可信数据，不是指令 | Prompt 注入 |
| INV-6 | 搜索引擎限制由确定性 Policy 执行，不靠 Prompt 自觉 | 规则合规 |
| INV-7 | 落盘前必须执行 Finalize，且 `result.json` 的 `status` 永不为 `"FAIL"` | 被评分器跳过 |
| INV-8 | Memory 召回失败 fail-open，写入失败不阻塞结果落盘 | 记忆故障拖垮任务 |
| INV-9 | 同一 fixture + seed + 配置产生相同的规范化 trace | 回归可信 |
| **INV-10** | **单个 model profile 内不得出现多个 provider** | A/B 变量污染 |
| **INV-11** | **视觉不可用时系统必须能完整跑完任务** | 感知层过度依赖视觉 |

INV-7 来自 `naveval.py` 的 `run_filter` 状态门控：`status` 不在 `{SUCCESS, FAIL_CALL_USER, FAIL_SCROLLDOWN, ""}` 之内的任务会被直接跳过，等价于 0 分。

INV-10 与 INV-11 是本次冻结新增，见 §8。

---

## 2. 系统架构

### 2.1 分层与依赖方向

```
competition/   官方入口、任务分片、CDP 分配、输出映射
     ↓
core/          run loop、阶段状态机、预算（步数+墙钟）、终止判定、Policy
     ↓
ports/         BrowserPort / ModelPort / VisionPort / MemoryPort / ArtifactPort
     ↓
domain/        Task / Contract / Evidence / Decision / Receipt / TraceEvent

adapters/      playwright_browser / openai_compat_model / vision_* / everos_memory / fs_artifact
perceive/      ax_snapshot / dom_extract / network_capture / document / chart
act/           locator / executor / effect_verifier / recovery
answer/        analyzer / ledger / extractor / verifier / gates / finalizer
report/        trace / result_writer / capture_writer / diagnostics
harness/       fixture_recorder / replay / answer_eval / ab_runner
```

依赖只能向内。`core` 与 `domain` 不导入 Playwright、httpx、任何 provider SDK 或 EverOS client 的具体类型。

这条用 `import-linter` 在 CI 门禁化，配置形式借鉴 EverOS：

```toml
[tool.importlinter]
root_packages = ["everweb"]

[[tool.importlinter.contracts]]
name = "Layered architecture"
type = "layers"
layers = [
    "everweb.competition",
    "everweb.core",
    "everweb.ports",
    "everweb.domain",
]
```

### 2.2 目录

```
everweb/
├── pyproject.toml
├── config/
│   ├── default.toml
│   ├── model_routes.toml        # A/B 的核心配置面
│   └── policy.toml
├── src/everweb/                 # 上述分层
├── tests/
│   ├── unit/ contract/ scenario/
│   └── fixtures/                # 录制的真实站点快照
├── evalset/
│   ├── tasks/                   # 自建 25-30 题（含 ground truth）
│   └── reports/
├── knowledge/                   # 通用操作手册（markdown，第 3 周填充；先于 EverOS 存在）
├── scripts/
│   ├── run_agent.sh             # 对齐官方入口签名
│   ├── record_fixture.py
│   ├── local_eval.py
│   └── validate_output.py
└── var/{runs,artifacts,traces}/
```

### 2.3 技术栈

Python 3.12，uv 管理（正式环境保留 pip 路径），Pydantic v2，**同步 Playwright**，httpx，Typer，pypdf + pdfplumber，lxml，Pillow，pytest + hypothesis，ruff + mypy，import-linter。

不用：asyncio / AnyIO、SQLAlchemy、aiosqlite。

---

## 3. 执行模型

### 3.1 进程与生命周期

对齐官方 runner 的形状：

```
主进程
 ├─ 解析 --input / --output / --cdp_url[] / --model / --api_base / --api_key
 ├─ worker_count = len(cdp_urls)，上限 8
 ├─ 任务分片（按 task_idx 轮转，避免同域名任务扎堆在一个 worker）
 └─ fork N 个 worker 进程
      每个 worker：
        connect_over_cdp(url)  ← 一次，复用
        for task in shard:
            context = browser.new_context()   ← 每任务新建，不复用
            run_one_task(task, context)
            context.close()
```

**与官方基线的一处刻意差异**：基线复用 `browser.contexts[0]` 并只 `new_page()`，cookie 与 localStorage 跨任务残留。我们每任务新建 context，代价是重新协商 TLS 与加载资源，收益是任务间零污染。

若云沙箱不允许 `new_context()`（某些托管浏览器只暴露默认 context），降级为 `new_page()` + 显式 `clear_cookies()`。**这个降级路径必须在冒烟期验证。**

任务分片按 `task_idx` 轮转而非连续切分，让同一站点的多道题落到不同 worker，降低被目标站点限流的概率。

### 3.2 阶段状态机

```
ANALYZE → NAVIGATE ⇄ INTERACT ⇄ RECOVER → EXTRACT → VERIFY → FINALIZE → EMIT
                          ↓                    ↑
                       COLLECT ────────────────┘
```

`FINALIZE` 与 `EMIT` 是**无条件可达**的：任何阶段的任何失败——墙钟硬超时、浏览器断连、模型不可用——都必须能跳到 FINALIZE 走完落盘。这是 INV-7 的实现保障。

### 3.3 双预算

```python
class Budget:
    max_steps: int          # min(100, ceil(reference_length * 2) if present else 100)
    soft_wall_clock_s: int  # 720
    hard_wall_clock_s: int  # 1080
    model_calls_max: int    # 60
```

步数上限同时考虑两个来源：官方硬顶 100，以及任务文件里可能存在的 `reference_length`（基线用 `ceil(reference_length * 2)`）。模板发布前两者都按最宽松取，发布后按实际收紧。

阶段配额是软的、可转移的，**不写死 55/22/13/10**。真正的硬约束是三条触发线：

| 触发线 | 条件 | 行为 |
| --- | --- | --- |
| 收敛线 | 剩余步数 < 20% 或 墙钟过软上限 | 停止探索，只允许补齐已知缺口与验证 |
| 封盘线 | 剩余步数 < 8 或 墙钟过软上限 + 3 分钟 | 进入 FINALIZE，禁止新导航 |
| 硬停线 | 墙钟过硬上限 | 立即 FINALIZE，用现有最佳候选出答案 |

**墙钟比步数更容易先耗尽，这是 v1.0 的盲点。**

### 3.4 循环体

```
1. 预算检查 → 可能触发收敛/封盘
2. Perceive  → PageView（第二步起为 diff）
3. Plan      → Decision（含 expected_effect）
4. Guard     → 确定性 Policy（URL 白名单、非幂等重复、越权）
5. Act       → ActionReceipt
6. Verify    → 校验 expected_effect，不符则 RECOVER
7. Collect   → EvidenceAtom
8. Assess    → 契约覆盖度更新，决定阶段迁移
9. Trace     → 追加写 trace.jsonl
```

第 6 步是防空转的主要机制。连续两次 `expected_effect` 未达成触发 NoProgressRecovery；连续三次相同 PageView 签名 + 相同 Decision 直接强制阶段迁移，不再让模型自己决定。

---

## 4. 感知层

### 4.1 AX 快照

主通道是 CDP 的 `Accessibility.getFullAXTree`，序列化规则参照 2026 年的行业收敛做法（Playwright MCP / Chrome DevTools MCP / Stagehand v3 同源）：

- 折叠 `generic` / `group` / `none` / `presentation` 这类纯包装节点
- 保留语义角色：`navigation` `main` `form` `table` `row` `cell` `list` `dialog` `tablist` `combobox`
- 给每个可交互节点分配稳定 ref（`@e1` `@e2`），背后缓存 `backendDOMNodeId`
- 渲染成缩进文本树，链接 href 内联，checkbox / radio 状态用 markdown 语法

选缩进树而非自造格式的理由：这种形状在 LLM 训练数据里大量出现，解析可靠性最高。

### 4.2 DOM 补充

AX 拿不到的东西才走 DOM：表格的完整表头层级与行结构、`data-*` 里的稳定标识、控件的 `disabled/checked/selected` 真实状态、当前视口内的 bbox（供坐标兜底）。

过滤掉：style / script、重复导航、隐藏广告、超长脚本 JSON、无意义 SVG path。

### 4.3 快照 diff

从第二步开始只发变化部分。同时解决三个问题：token 成本（长任务能压掉 80% 以上）、模型注意力（聚焦「刚才那个动作改变了什么」）、动作效果校验（diff 为空就是动作没生效）。

需要稳定的节点身份算法，否则 diff 会因 DOM 重排全量失效。方案：ref 的稳定性锚定在 `(role, accessible_name, 路径签名)` 三元组上，`backendDOMNodeId` 只作为本步内的执行句柄。

### 4.4 PageView

送进模型的有界视图：

```
page_goal / current_url / title / page_signature
visible_headings
interactive_targets       # 带 ref，按与当前目标的相关性排序，截断到 N 个
active_filters            # 当前生效的筛选器及其值 ★
selected_values
table_schema + 样本行
network_delta             # 本步新增的同域 xhr/fetch 摘要 ★
download_candidates
modal_state
last_action_result        # expected_effect vs actual
contract_progress         # 哪些 required field 还没覆盖 ★
unknowns
```

三个打星字段是 v2.0 新增或强化的。`active_filters` 单列，因为它同时服务三件事：模型决策、验证器核对操作要求、Finalize 阶段确认筛选状态在终态截图里可见。

每项带 provenance 与 token 估算，超预算时按相关性裁剪。**保护项永不裁剪**：当前 AnswerContract、最近一次 ActionReceipt、未覆盖字段、当前 active_filters、最新 verifier 失败。

### 4.5 网络捕获

监听 `xhr` 与 `fetch`，记录 `request_id`、method、URL、resource_type、请求体、响应状态与 content-type、以及关联的 `iteration_id` 与 `action_id`。

**双重用途**：对我们是证据源，对评分器是操作证明。

捕获策略要考虑评分器的 120k token 预算与「从最旧开始丢」的截断规则：对明显噪音（心跳、埋点、同 URL 高频轮询）保守剔除，对单条请求体设体积上限，大响应外置到 artifact。

Cookie、Authorization、token 默认脱敏。评分器的 `request_formatter` 也会删，但**我们不能依赖它**。

### 4.6 证据阶梯（视觉是最后一档）

这是 v2.0 冻结版新增的核心纪律，由 INV-11 强制。任何「看起来需要视觉」的问题，都必须按下列顺序尝试，视觉永远在最底层：

```
1. XHR / JSON 底层数据          ← 最可靠，且评分器直接能看到
2. 页面内的数据表 / 可下载文件
3. DOM 文本 / aria-label / title
4. tooltip 文本节点
5. SVG 内的 <text> 元素
6. 视觉理解                      ← 仅当以上全部耗尽
```

前五档全部与厂商无关。当阶梯耗尽且视觉不可用时，AnswerGate 记 `evidence_gap: visual_only`，走诚实路径——报告能证明的部分，而不是猜。

**埋点要求**：每次阶梯耗尽到只剩视觉时打一个计数器 `visual_only_fallback_count`。这个数除以总任务数，就是视觉能影响的任务比例上界，是 Phase C 决策的关键输入。

### 4.7 文档与图表

文档链路：

```
download 事件或直链 → 校验 content-type 与大小 → 落盘原件
  → pypdf 抽文本 / pdfplumber 抽表格 → 页级分块
  → 扫描页回落视觉（若可用）→ 结构化证据（带 document digest + 页码 + 表头路径）
```

图表取数按 §4.6 的证据阶梯执行，外加最后一步：单位 / 坐标轴 / 排序复核。

### 4.8 VisionPort 与 NullVision

```python
class VisionPort(Protocol):
    def describe(self, image: bytes, question: str) -> VisionResult | Unavailable: ...
    def available(self) -> bool: ...
```

`VisionResult` 必须结构化返回 `description / elements / extracted_values / uncertainty / confidence`，不接受自由文本。

`NullVision` 永远返回 `Unavailable(reason="vision_disabled")`。**每一个调用点都必须处理这个返回值。**

契约测试：挂 `NullVision` 跑完整评测集，不允许任何代码路径抛异常，任务照常完成落盘。

调用视觉的五个条件（且必须已走完证据阶梯前五档）：内容在 canvas 或图片里；AX 与 DOM 都没有目标语义；扫描版 PDF；图表 tooltip 与接口都拿不到；需要判断视觉遮挡或状态。

---

## 5. 动作层

### 5.1 定位优先级

`role + accessible name` → `label` → `text + 容器` → 稳定 CSS → XPath → 截图坐标。

坐标是最后兜底，必须附带截图引用、视口尺寸、缩放比、bbox、视觉置信度，以及一个动作后的确定性校验条件。

### 5.2 动作集与幂等性

```python
class Idempotency(StrEnum):
    PURE = "pure"                      # ReadElement, Observe
    IDEMPOTENT = "idempotent"          # Click(链接), Scroll, Hover, WaitFor
    CONDITIONAL = "conditional"        # Type, Select, Check
    NON_IDEMPOTENT = "non_idempotent"  # Submit, Download, AddToList
```

非幂等动作在状态不明时先 reconcile（查 URL、DOM、网络证据判断是否已生效），**绝不盲目重试**。任务无重试，一次误提交可能直接毁掉整题。

### 5.3 效果校验

`Decision` 携带 `expected_effect`，执行后由确定性代码检查：URL 变化 / AX diff 非空 / 特定网络请求出现 / 控件值变化 / 模态框消失。

校验不过就走 RECOVER，**不允许模型「假装成功继续往下」**。

### 5.4 恢复顺序

弹窗与 cookie banner → 检查 page/context 是否仍连接 → 短时条件等待（不用固定长 sleep）→ 检查动作是否已通过其他证据生效 → 幂等则重新定位一次 → 回退到上一稳定 checkpoint → 输出具体 FailureCode。

FailureCode 集合：
`BROWSER_DISCONNECTED` `PAGE_CRASHED` `NAVIGATION_TIMEOUT` `TARGET_NOT_FOUND` `ACTION_NO_EFFECT` `AMBIGUOUS_SIDE_EFFECT` `BLOCKED_BY_MODAL` `DOWNLOAD_FAILED` `POLICY_REJECTED` `BUDGET_EXHAUSTED` `WALL_CLOCK_EXHAUSTED`

这些是**内部**分类，写进 trace 与诊断报告，**不写进 `result.json` 的 status**（INV-7）。

---

## 6. 答案层

### 6.1 AnswerContract

```python
class RequiredField(BaseModel):
    name: str
    description: str
    value_type: str
    required: bool = True
    normalization: list[str] = []
    evidence_min_count: int = 1

class OpReq(BaseModel):
    kind: str          # filter | sort | search | select | submit
    description: str   # "国家 = France"
    evidence_hint: str # 期望在 URL query 或 XHR body 里看到什么
    satisfied: bool = False

class AnswerContract(BaseModel):
    shape: str                                # scalar|list|set|table|comparison|free_text
    fields: list[RequiredField]
    requires_complete_set: bool = False
    completeness_rule: str | None = None
    ordering_rule: str | None = None
    exclusion_rules: list[str] = []
    source_constraints: list[str] = []
    operation_requirements: list[OpReq] = []  # ★ 新增
    answer_language: str                      # ★ 新增，跟随任务描述语言
```

`operation_requirements` 是针对评分器「数值 / 筛选 / 排序必须精确匹配、极值必须有排序动作」规则的直接产物。TaskAnalyzer 在第一次动作前把任务里的筛选条件与极值判据抽出来，Planner 据此优先寻找站点原生控件，Finalize 阶段逐条核对是否真的在 URL 或网络请求里留下痕迹。

**这是本方案里最直接影响得分的单个设计。**

`answer_language` 跟随任务描述语言。v1.0 写死 `zh-CN` 是错的——任务描述可能是英文、西班牙文、法文。

### 6.2 EvidenceAtom 与账本

```python
class EvidenceAtom(BaseModel):
    evidence_id: str
    claim_key: str
    raw_value: str
    normalized_value: Any
    source_kind: str      # dom_text|accessibility|network_response|document
                          # |chart_data|chart_tooltip|ocr|vision|computed
    source_url: str
    locator: str | None
    network_request_id: str | None
    document_page: int | None
    screenshot_ref: str | None
    confidence: float
    extraction_method: str
    parents: list[str] = []   # computed 必须非空
```

账本以 JSONL 追加写，每条证据落盘即不可变。删除用软归档语义（借鉴 EverOS 的 `deprecated_by`），不物理覆盖。

### 6.3 Extractor

只消费 `EvidenceAtom` 与 `AnswerContract`。**不允许直接使用上下文里出现但未登记为证据的网页文字。**

发现关键信息缺证据时返回 `evidence_request`，由 core 决定是否值得花步数去补。

输出 `AnswerCandidate`：值、字段到证据的映射、归一化说明、缺失字段、歧义点、置信度。

### 6.4 四层验证

| 层 | 方法 | 性质 |
| --- | --- | --- |
| V0 | Schema、类型、空值、格式 | 确定性 |
| V1 | 每个字段到 EvidenceAtom 的引用完整性 | 确定性 |
| V2 | 规则复算：去重、单位、日期、货币、排序、集合完整性、`operation_requirements` 核对 | 确定性 |
| V3 | 独立反例审查 | 模型 |

V3 只看任务、契约、证据、候选答案，**不看 Planner 的推理链**，降低确认偏差。

**单厂商 profile 下的 V3 纪律**：Phase A/B 期间不能用「换个厂商」来降低同源偏差，因此 V3 必须**从原始证据重新推导**，而不是审阅 Extractor 的结论。这是更根本的做法，跨模型只是 Phase C 的额外保险。

### 6.5 双门禁

**NavigationGate**
轨迹中存在目标数据页；页面与任务指定站点的关系可解释；关键筛选器状态已读回确认；URL、DOM 或网络证据与任务条件一致；无未解决的导航 blocker。

**AnswerGate**
required fields 全覆盖；每字段有最少证据；完整集合有 StopProof；V0–V2 全通过；高风险任务 V3 通过；`operation_requirements` 全部 satisfied；`agent_answer` 已生成并反向解析验证。

两个门禁都过 → `status = "SUCCESS"`。
有一个不过 → **仍然走 Finalize**，输出最佳可得答案，`status = ""`（评分器可处理的状态），并在 trace 里记录未通过的门禁与原因。

### 6.6 StopProof

完整集合题必须记录至少一种：

- 接口返回 `total_count` 且已收集数量一致
- 分页到最后一页且所有页码已访问
- next cursor 为空
- 无限滚动连续两次无新增且有明确到底标志
- 站点显示结果总数且去重后一致
- 任务条件下所有分组均已覆盖

去重按稳定键（ID 或 URL），**不按显示文本**。

### 6.7 答案文本规范

用 `answer_language` 作答；关键实体保留原文拼写（大学名、城市名、机构名不翻译，语义比对时原文实体最不容易出错）；答案自足，回述关键约束再给值；集合题完整列举，**禁止「等 N 项」**。

例：任务问 "On the 2024 CWUR GLOBAL 2000 LIST, identify which universities in France are ranked in the top 0.2%"，答案应形如：

> "In the 2024 CWUR Global 2000 list, the French universities ranked in the top 0.2% (i.e., top 4 globally by percentile) are: Université PSL, Université Paris-Saclay, Sorbonne Université."

---

## 7. 输出层：与评分器对齐

这是 v2.0 相对 v1.0 新增的独立一层。

### 7.1 Finalize 阶段

在写 `result.json` 之前，无条件执行：

```
1. 核对 operation_requirements
   逐条检查 URL 轨迹与 capture 里是否有对应痕迹
   缺失且预算允许 → 补做该操作（例如显式点一次排序）
2. 终态取景
   - 导航回答案所在页面（如果中途离开了）
   - 展开必要的折叠区
   - 把答案元素滚进视口中部
   - 确认关键筛选器状态在画面内可见
3. 截最后一张图 → trajectory/{max_index}.png
4. 补齐 urls：确保关键里程碑 URL 在数组里且顺序合理
5. 生成 agent_answer 并反向解析校验（能否从答案文本还原出契约字段）
6. 原子写 result.json 与 capture.json，写完读回校验
```

第 2 步成本 1–3 步，收益是让评分器的状态验证通道从「什么都看不出来」变成「答案就在画面里」。

**这是整份方案里性价比最高的改动。**

### 7.2 result.json

严格对齐官方字段，`website` **原样回写**（评分器用它算根域做请求过滤，不要改大小写或补斜杠）：

```json
{
  "task_idx": 0,
  "task_id": "f0fe04a2...",
  "task": "<原样>",
  "website": "<原样>",
  "status": "SUCCESS",
  "actions": ["click(@e12 button 'Search') @ (640,320)", "..."],
  "thoughts": ["决策摘要 1", "..."],
  "urls": ["https://...", "..."],
  "agent_answer": "..."
}
```

`thoughts` 用简短决策摘要，不放原始推理链。`actions` 写成人类可读、可审计的形式（赛后有操作轨迹合规验证）。模板发布后如有额外字段，**只改 OutputMapper**。

### 7.3 capture.json

结构对齐官方 `{"capture_time", "total_requests", "all_requests"}`。内容策略见 §4.5。

### 7.4 输出一致性测试

CI 每次校验：

- 目录名 `{task_idx}_{task_id}`
- `trajectory/` 编号连续且最后一张存在
- `result.json` 可解析且字段类型正确
- `status` 不为 `"FAIL"`
- SUCCESS 时 `agent_answer` 非空
- `agent_answer` 不含内部 XML、debug JSON 或 prompt 片段
- `capture.json` 可解析
- 无 secret、Authorization、原始 cookie

---

## 8. 模型层：厂商隔离的 A/B

### 8.1 抽象

```python
class ModelPort(Protocol):
    def complete(self, req: ModelRequest, timeout_s: float) -> ModelReceipt: ...
    def capabilities(self) -> ModelCapabilities: ...
```

`core` 只见 `ModelRequest / ModelResponse / ModelUsage / ModelCapabilities / ModelError / ModelReceipt`。provider 特有字段（DeepSeek 的 `reasoning_content` 回传、Anthropic 的 thinking block）只存在于 adapter 内部。

### 8.2 厂商隔离原则（INV-10）

**Phase A 与 Phase B 期间，单个 profile 内不得出现多个 provider。**

这条的直接后果：DeepSeek V4 是纯文本模型，所以 `profile.deepseek` 的 vision 角色是**空**，不是路由到别处。

这不是妥协。原设计里两个 profile 都挂着 K2.6 做视觉，视觉这个变量被污染了，永远测不出它值多少分。隔离后两臂天然构成对照：

```
profile.deepseek  =  纯文本感知（DOM / AX / 网络 / 文档解析）
profile.kimi      =  多模态感知（上述 + 原生视觉）
```

差值就是视觉的边际价值。配合 §4.6 的 `visual_only_fallback_count` 埋点，Phase A 结束时就能拿到视觉价值的上界，无需等 Phase B。

### 8.3 角色路由

```toml
# config/model_routes.toml

[profile.deepseek]
task_analyzer  = { provider="deepseek", model="deepseek-v4-pro",   thinking="max"  }
navigator      = { provider="deepseek", model="deepseek-v4-pro",   thinking="high" }
navigator_fast = { provider="deepseek", model="deepseek-v4-flash", thinking="high" }
summarizer     = { provider="deepseek", model="deepseek-v4-flash", thinking="off"  }
extractor      = { provider="deepseek", model="deepseek-v4-pro",   thinking="max"  }
verifier       = { provider="deepseek", model="deepseek-v4-pro",   thinking="max"  }
vision         = { provider="none" }

[profile.kimi]
task_analyzer  = { provider="moonshot", model="kimi-k2.6", thinking="on"  }
navigator      = { provider="moonshot", model="kimi-k2.6", thinking="on"  }
navigator_fast = { provider="moonshot", model="kimi-k2.6", thinking="off" }
summarizer     = { provider="moonshot", model="kimi-k2.6", thinking="off" }
extractor      = { provider="moonshot", model="kimi-k2.6", thinking="on"  }
verifier       = { provider="moonshot", model="kimi-k2.6", thinking="on"  }
vision         = { provider="moonshot", model="kimi-k2.6" }

# [profile.mixed] —— Phase C 再填，需 allow_cross_vendor = true
```

`profile` 是 A/B 的一等公民：切换 profile 不改任何代码，RunManifest 记录 `model_route_digest`，报告按 profile 分组对比。

**机器强制隔离**，不靠自觉。配置加载器校验：

```
任一 profile 中出现多于一个 provider（none 不计） → 启动失败
唯一例外：profile 名为 "mixed" 且显式设置 allow_cross_vendor = true
```

Phase A/B 期间任何人手滑写出跨厂商路由都会立刻炸，而不是悄悄跑出被污染的对比数据。

### 8.4 Phase C 的候选配置（尚未冻结）

待 Phase A、B 都达标后填入，当前记录设计意图：

```
navigator / vision   → kimi-k2.6        （BrowseComp 83.2 / OSWorld 73.1 / CharXiv 80.4）
extractor            → deepseek-v4-pro  （1M 上下文 + 极便宜缓存）
verifier             → 与 extractor 不同厂商（交叉检查）
summarizer / fast    → deepseek-v4-flash
```

Stable Prefix 的归属有实际收益差：DeepSeek 缓存命中价 $0.003625/M，K2.6 是 $0.16/M，差 44 倍。长而稳定的部分（AnswerContract、证据账本、工具 schema）压在 DeepSeek 那一侧更划算。

### 8.5 模型事实基线

**DeepSeek V4 系列**（无版本上限）

| | 输入未命中 | 输入命中 | 输出 | 上下文 | 模态 |
| --- | ---: | ---: | ---: | ---: | --- |
| V4-Pro | $0.435 | $0.003625 | $0.87 | 1M | 纯文本 |
| V4-Flash | $0.14 | $0.0028 | $0.28 | 1M | 纯文本 |

**Kimi K2.6**（Moonshot 版本上限，恰在天花板）

| 项 | 值 |
| --- | --- |
| 架构 | MoE，1T 总参 / 32B 激活，384 experts 选 8，61 层，MLA |
| 上下文 | 262,144（256K） |
| 模态 | 原生多模态：文本 + 图像 + 视频，MoonViT 400M |
| 接口 | `https://api.moonshot.ai/v1`，OpenAI 全兼容 |
| 价格 | 命中 $0.16 / 未命中 $0.95 / 输出 $4.00（每 1M），自动缓存 |
| 权重 | Modified MIT 开源 |

相关 benchmark：BrowseComp 83.2%、OSWorld-Verified 73.1%、CharXiv(RQ) 80.4%、MMMU-Pro 79.4%、HLE-Full w/ tools 54.0%。

参照：CharXiv 上 Gemini 3.1 Pro 是 80.2%，与 K2.6 持平；MMMU-Pro Gemini 83.0% 略强。**在最关键的图表读数上，K2.6 与 Gemini 3.1 同级。**

### 8.6 成本与延迟

按每题 40 次调用、平均 30k 输入（27k 命中缓存）、1k 输出：

| Profile | 每题 | 100 题一轮 |
| --- | ---: | ---: |
| 全 DeepSeek V4-Pro | ~$0.09 | ~$9 |
| 全 Kimi K2.6 | ~$0.45 | ~$45 |

**成本不是选型依据，按质量与延迟选。**

**真正的约束是墙钟**：thinking-max 单次可能 30–60 秒，一题 40 次调用就是 20–40 分钟；8 worker 各跑 12.5 题就是 4–8 小时。所以 summarizer 与 navigator_fast 必须走 Flash 或关闭 thinking，高档 thinking 只留给 analyzer、extractor、verifier 这三个低频高价值角色。

### 8.7 合规约束

```python
MAX_VERSION = {
    "openai": "gpt-5.4", "anthropic": "claude-4.6", "google": "gemini-3.1",
    "xai": "grok-4.3", "zhipu": "glm-5v-turbo", "moonshot": "kimi-k2.6",
}
# deepseek / qwen 等未列出厂商不受限
```

**Kimi 的特殊风险**：K2.6 恰在天花板，而 Moonshot 同时提供 `kimi-k2.7-code`、`kimi-k2.7-code-highspeed`、`kimi-k3`——这些都是**禁用版本**。任何 `kimi-latest` 别名或聚合商路由都可能悄悄用到更高版本，而组委会明确会审查「闭源模型通过中转接口调用禁用版本」。

对策四条：

1. 配置里硬编码 `kimi-k2.6` 字面量，不用任何别名
2. 直连 `api.moonshot.ai/v1`，不走任何中转
3. doctor 启动时发最小请求，校验响应 `model` 字段字面等于配置值
4. RunManifest 记录每次调用返回的 model 值

**不自部署 K2.6 权重**——虽然是 Modified MIT，托管 API 是干净得多的路径。

### 8.8 Moonshot 图像输入约束

官方文档明确：**不支持远程图片 URL**，只支持 base64 编码内容或通过 file ID 上传。

工程要求：截图用 base64 data URI；请求体总大小上限 100MB；图片 token 按分辨率动态计算（有 estimate API 可预估）。1920×1080 PNG 转 base64 不小，**视觉调用前必须压缩到必要分辨率**——官方截图保原分辨率，Vision 用压缩副本。

### 8.9 超时与错误

官方上限 180 秒，客户端设 160–165 秒主动超时，留出落盘余量。

错误分类：`auth` `permission` `rate_limit` `timeout_before_headers` `stream_idle_timeout` `stream_protocol` `invalid_request` `context_overflow` `provider_unavailable` `model_unavailable` `cancelled` `malformed_structured_output`

只对明确未发送或未开始的幂等请求重试，`timeout_after_send` 标记 ambiguous。

DeepSeek 思考模式下发生工具调用时，后续请求需完整回传 `reasoning_content`，adapter 必须保存 `ProviderConversationState`，否则长链会 400。但 `reasoning_content` **不进 thoughts、不进日志、不进记忆**。

---

## 9. 记忆层：EverOS 并行轨道

### 9.1 定位

三条独立价值线，优先级从高到低：

**线一：开发迭代期的经验飞轮（评测期不参与）。**
本地跑几十轮评测，每轮产生大量「这个站点的高级搜索藏在哪」「这类分页的停止信号是什么」「这个失败从哪一步开始偏」。这些进 `agent_case`，每周 Reflection 蒸馏成连贯叙事，聚类成 `agent_skill`，人工精修成 knowledge document。

**线二：自建通用操作文档（已决定进评测期，排期后移至第 3 周）。**
见 §9.7。论文的 Protocol II 消融给了这条路一个 +8 点的先验。

**线三：赛后的长期资产。**
站点 playbook 库、失败模式分类、Web Agent 领域的 agent_skill 集合。独立于比赛成绩存在。

评测期定位的数据依据：Protocol III 只有 100 题，整个基准是 800 个站点、平均不到 2 题一站，一次正式 run 里几乎不会在同一域名遇到第二道题——**站点级记忆在评测期的复用机会接近于零**。

### 9.2 EverOS 的真实设计（调研结论）

它不是「一个带 add/search 接口的记忆服务」，而是有明确哲学的本地记忆运行时。七条核心思想：

1. **Markdown 是唯一真相源，索引是可重建的派生物。** md 原子写（tmp + fsync + rename）成功即返回，cascade 守护进程 watch 文件变更、500ms debounce、entry 级 diff、单事务同步 LanceDB。LanceDB 挂了不阻塞，变更缓冲在 SQLite `md_change_state` 队列，恢复时按 LSN 重放。
2. **双轨制。** user track（episode / profile / atomic_fact / foresight）与 agent track（agent_case / agent_skill）并列，`user_id` 与 `agent_id` **互斥**。我们只用 agent 轨。
3. **正交检索。** 按 `user_id` / `agent_id` / `app_id` / `project_id` / `session_id` 五维检索。`app_id` / `project_id` 在磁盘层分区，**search 与 get 永不跨 scope**。
4. **Reflection：离线记忆演化。** Select → Merge → Re-extract → Deprecate，簇内碎片合并成连贯叙事，软归档原件（`deprecated_by`，默认搜索排除）。默认每周一 02:00，默认关闭。
5. **Knowledge 子系统。** `/api/v2/knowledge/*`，可编辑、有来源、带分类法的 Markdown 知识页，完整 CRUD 加主题混合搜索。
6. **PromptSlot 三层覆盖。** 目前 Layer 1 已上线（`boundary_detection` / `episode_extract`），Layer 2/3 待实现。
7. **everalgo 边界。** 抽取算法作为独立 PyPI 包，纯函数、不碰存储。

架构上是严格 DDD 单向分层（`entrypoints → service → memory → infra`），用 import-linter 在 CI 强制。

### 9.3 v1.0 关于 EverOS 的四处出入（已修正）

| # | v1.0 写法 | 实况 | 后果 |
| --- | --- | --- | --- |
| 1 | `agent_id = everweb:<role>:<version>` | charset `^[a-zA-Z0-9_.-]+$` 不含冒号；且 agent_id 会成为目录名 `agents/<agent_id>/` | **会 422 / 路径非法**，必须改 `everweb_navigator_v1` |
| 2 | `/api/v1/memory/...` | `/api/v2` 是 canonical，`/api/v1` 为永久兼容别名 | 功能不坏，但新接入应写 v2 |
| 3 | 「写后短时间可能搜索不到」 | 典型亚秒，**负载下可达 10–15 秒** | visibility overlay 有效期按 15 秒设计，不是 1–2 秒 |
| 4 | `submit_verified_case(case: VerifiedCase)` | `/add` 收 `messages[]`，OpenAI Chat Completions 形状 | **EverOS 期待对话轨迹，不是结构化记录**，决定 adapter 形状 |

### 9.4 接口

```python
class MemoryPort(Protocol):
    def recall(self, req: RecallRequest) -> RecallReceipt: ...
    def submit_run(self, trace: RunTrace) -> StoreReceipt: ...   # 不再是 VerifiedCase
    def health(self) -> MemoryHealth: ...
```

`submit_run` 接原始运行轨迹，由 adapter 内部完成 trace → messages 的转换，`core` 层不需要知道 EverOS 期待对话形状。

实现：`NullMemory`（默认）、`InMemoryMemory`、`FaultInjectingMemory`、`EverOsBackend`。

### 9.5 EverOsBackend 的具体形状

**Scope**

```
app_id     = webretriever
project_id = global | site_<sanitized_domain>       # 可读，非 digest
agent_id   = everweb_navigator_v1                   # 无冒号
session_id = <execution_id>
```

用可读域名而非 digest：charset 允许点与短横线，域名天然合法，而可读性对人工检查 markdown 至关重要——这正是 EverOS 的核心卖点。

**为什么必须用 project_id 隔离站点**：Filter DSL 只有五个可过滤字段（`session_id` / `parent_type` / `parent_id` / `timestamp` / `sender_id`），`owner_id` / `owner_type` / `app_id` / `project_id` 是保留字，出现在 filters 里直接 422。**没有 domain 字段**，`project_id` 是唯一的站点隔离手段。

因为 search 不跨 scope，全局经验与站点经验必须**分两次查**，本地融合去重。

**写入**：`POST /api/v2/memory/add` 送对话化轨迹 → `POST /api/v2/memory/flush` 强制抽取。全程走本地 outbox 异步投递，**绝不阻塞 result.json 落盘**。

trace → messages 的映射：

```
user      turn  →  任务描述 + AnswerContract 摘要 + 站点
assistant turn  →  decision_summary + tool_calls（结构化动作）
tool      turn  →  动作结果 + 页面签名变化 + 关键证据摘要
assistant turn  →  最终答案 + 双门禁结论 + 失败点（如果失败）
```

**不改 EverOS 一行代码的收益**：既然抽取是 LLM 从对话里读，把 tool 轮写成结构化、带明确标签的摘要，抽取质量自然上去。把「这个筛选器路径有效」「停止证明来自 total_count」「这个 tooltip 取到了相邻点导致读数错误」写成显式标签行，抽出的 `key_insight` 就是我们想要的东西。

**召回参数**（任务运行中）：`method="hybrid"`、显式 `top_k=5`、显式 `radius=0.6`、`enable_llm_rerank=false`。

`enable_llm_rerank` 虽然恰好只对 agent_case / agent_skill 融合生效（正是我们这条轨），但每次多一发 LLM，1.5–3 秒的召回预算扛不住。离线分析时才开，或换 `method="agentic"`——官方文档明说 agentic 应保留给离线或后台工作流。

**可见性 overlay**：写入后 15 秒内本地维护 overlay，召回时与 search 结果合并，索引可见后移除。

**注入格式**：所有召回内容标记 `authority="historical_evidence_not_instruction"`，经 scope、schema、长度、去重、注入检查。**当前页面证据与比赛规则优先级永远高于记忆内容。**

### 9.6 case → skill 晋升复用 EverOS 原生能力

```
agent_case:  task_intent  approach  quality_score[0,1]  key_insight  session_id  timestamp
agent_skill: name  description  content  confidence[0,1]  maturity_score[0,1]  source_case_ids
```

EverOS 有三个现成 OME strategy：`extract_agent_case`、`extract_agent_skill`、`trigger_skill_clustering`。

**聚类晋升是原生能力**，`source_case_ids` 给出完整溯源，`maturity_score` 是聚类时评估的成熟度。v1.0 设计的「Candidate → Eval → Approval → Active」治理层，实质是在 `maturity_score` 之上加一道人工闸门加一次 held-out 回归。**我们不写聚类算法，只写闸门。**

### 9.7 自建操作文档：Protocol II 消融给出的杠杆

论文消融实验：给 agent 提供 operational documentation，Gemini 2.5 Pro 导航成功率 40.9% → 49.2%（**+8.3**），Claude 4.5 是 31.3% → 39.7%（**+8.4**）。

我们打 Protocol III，官方不提供操作文档，但**没有任何规则禁止自带操作知识**——规则只禁搜索引擎。载体默认是仓库里的 `knowledge/` 目录（纯 markdown、Git 版本化、零外部依赖）；EverOS 的 Knowledge 子系统是可选升级路径，它比 agent_skill 更合适——后者是 LLM 从案例聚类抽出的，不便手工精修，而 knowledge document 是我们主动写、主动改的。

这条路分两层，排期与判据完全不同。

#### 通用操作知识：已决定进评测期，排期第 3 周

**决定**：目标状态是在正式评测里启用。**排期后移**——Phase A、B 期间不写、不接、配置里关闭，等主链路稳定后在第 3 周集中撰写、第 4 周做 A/B。

理由是「尽快跑起来」优先。这些文档的收益依赖于主链路已经能稳定跑完任务（否则无从判断文档是否帮上忙），提前写只会分散注意力，而且那时我们对失败模式的理解还很浅，写出来的东西质量低。第 3 周时手上已有两轮实测的失败分布，写出来的内容会准得多。

**内容范围**（不绑定站点的模式）：

- 如何证明分页列表已到底（六种停止证明判据，对齐 §6.6）
- 如何确认筛选器真的生效（读回控件值 / 查 URL query / 查 XHR body）
- 从图表拿底层数据的六条途径及优先级（对齐 §4.6 证据阶梯）
- 表单级联下拉的操作顺序
- 多版本文档如何确定任务要哪一版
- 五个任务族各自的典型陷阱（由第 1–2 周的失败记录反推）

**载体**：先写成 `knowledge/` 下的 markdown，不依赖 EverOS。运行时按主题召回注入 Volatile Segment，注入纪律与记忆召回相同（§9.5 的 `authority` 标记与检查链）。是否导入 EverOS Knowledge 子系统是实现细节，不影响这条决定。

**A/B 的定位**：由于已决定进评测期，A/B 不再是准入门槛，而是**否决权**——只有当 held-out 上出现可测量的负收益时才回退关闭。这与 §9.8 中 EverOS 记忆的准入规则不同，是刻意的差别。

#### 站点专属 playbook：默认不做

**决定**：Phase A、B 期间**零投入**。不作为独立工作项，不占用任何工程时间。

官方措辞是「比赛题目与开源数据集中的**评测题目**互不重叠」——**题目**不重叠，没说**网站**不重叠。数据集的站点选取方法论是「每板块按流量取前 30 + 权威垂直站」，若比赛题沿用同一套构造方法，站点池可能高度重合。但这是推测，不足以在主链路未跑通前分配资源。

**唯一保留的动作是一个副产品**：建开发集时本来就要列出题目对应的站点，顺手统计一下集中度即可，预算 **1 小时**，产出一张表进 `evalset/reports/`。不为此单独安排工作项。

**重启判据**（在 Phase B 门禁通过时评估，只看一个数）：

> 公开数据集 Protocol III 的 100 题中，**排名前 20 的域名覆盖的题目占比**
>
> - **≥ 40%** → 站点池确实集中，值得投入
> - **< 40%** → 直接放弃，不再评估

**若重启，硬约束三条**：

1. 总时间盒 **8 小时**，超时即停，不追加
2. 最多覆盖 **15 个站点**，按题目覆盖数降序取
3. 格式与通用操作文档完全相同，**不引入任何新机制**——同一套 markdown、同一套召回路径、同一套注入检查

这三条是为了保证即使这条路走不通，沉没成本也被封在 8 小时内，且不会在代码里留下任何需要维护的东西。

### 9.8 三种模式与准入

| 模式 | 行为 | 使用时机 |
| --- | --- | --- |
| `off` | 不召回不写入 | 默认；正式评测基线；A/B 对照组 |
| `shadow` | 召回但不注入模型，只记录命中 | 本地迭代第一阶段，验证召回质量 |
| `assist` | 经策略过滤后注入 Volatile Segment | A/B 证明正收益后才开 |

`shadow` 必须**逐字节等价**于 `off`：相同 seed 下模型输入完全一致。这是一个契约测试。

进入正式路径需同时满足：Null 与 shadow 等价性通过；scope、脱敏、outbox 契约测试通过；held-out 上 A/B 有可辨正收益；负迁移在阈值内；一键关闭可用。

**默认假设是评测期用 `off`。** 这里说的是 EverOS 记忆（`agent_case` / episodes / 站点叙事），它们的收益来自跨题复用，而 100 题跨约 100 站点，复用近零。

**通用操作文档不走这条准入链。** 它已决定进评测期（§9.7），且默认载体是 `knowledge/` 目录而非 EverOS，用独立的 `[knowledge]` 配置开关，与 `memory.mode` 正交。即便 `memory.mode = off`，`knowledge.enabled` 也可以是 `true`。这是刻意的解耦：不想让操作手册的命运绑在 EverOS 服务的可用性上。

### 9.9 Reflection 的正确用法

只在开发期，且不要频繁。EverOS 文档明确警告：每次是有损 LLM 合并，反复合并会让叙事变差，默认每周一次。

**它是开发迭代期的经验蒸馏工具，不是运行时组件。** 每周跑一次，把散落在几十轮本地评测里的碎片合并成连贯的站点叙事与通用模式。正式评测期完全不需要。

审计：每次运行写一条 `reflection_report`（cluster_id / mode / source_count / merged_entry_id / deprecated_fact_count），可直接 sqlite3 查。软归档不删除，原件永远在 markdown 里可追溯。

### 9.10 运行成本与依赖

EverOS 需要四类 provider：LLM、multimodal、embedding、rerank（默认 OpenRouter + DeepInfra，multimodal 默认 `google/gemini-3-flash-preview`）。Office 文档解析需系统装 LibreOffice。

每存一个 case 至少 1–2 次 LLM 调用（boundary detection + extraction），每次 search 要 embedding。

**这些 provider 不受 §8.2 厂商隔离约束**——EverOS 在评分路径之外，不构成两臂之间的混淆变量。

开发期完全可接受，但这是评测期额外的故障面、延迟与依赖，强化了「评测期默认 off、只读、fail-open」的结论。

### 9.11 借鉴但不接入的三样

**md-first 的原子写纪律**：tmp + fsync + rename，写成功即返回，派生索引异步且可重建。我们的 `result.json` 与 `trace.jsonl` 就该这么写。

**import-linter 的分层契约**：见 §2.1。

**软归档而非删除**：`deprecated_by` 语义——原件永远保留、默认搜索排除、随时可追溯。证据账本与失败记录用这个语义，不覆盖不删除。

---

## 10. 评测与测试

### 10.1 本地评测集（四层）

1. 官方 3 个 example tasks（冒烟）
2. 公开数据集 Protocol III 的 100 题里挑 25–30 题作为**开发集**（比赛题与之不重叠但同分布）
3. 按五个任务族自建的确定性 fixture（回归）
4. 剩余的公开 Protocol III 题作为 **held-out**，只在 release gate 用

需 Hugging Face 登录并同意条款才能下载。拿到后保存许可记录、digest 与本地只读快照，**不提交受限数据，CI 不依赖在线下载**。

### 10.2 AnswerEval

按答案类型分派：

| 类型 | 判定 |
| --- | --- |
| scalar | 归一化精确匹配 + 语义容错 |
| date/time | 统一时区格式 |
| number | 单位转换加容差 |
| list/set | precision / recall / F1，完整集合要求 recall = 1 |
| table | 行键对齐后逐字段比 |
| comparison | 校验对象、维度、排序、结论 |
| free text | 先规则抽取再 LLM 判定 |
| document | 额外校验页码与来源约束 |

### 10.3 指标

| 分类 | 指标 |
| --- | --- |
| 最终 | `end_to_end_success_rate` |
| 分解 | `navigation_success_rate`、`extraction_success_given_navigation` |
| 完整性 | `field_coverage`、`complete_set_recall` |
| 可信性 | **`false_success_rate`**、`unsupported_claim_rate` |
| 证据 | `operation_requirement_satisfied_rate`、`final_screenshot_informative_rate` |
| 感知 | **`visual_only_fallback_count`**（见 §4.6） |
| 效率 | `steps_p50/p95`、`wall_clock_p50/p95`、`model_calls`、`cost_per_success` |
| 稳定 | `crash_rate`、`output_valid_rate`、`loop_rate`、`recovery_success_rate` |

`false_success_rate`（系统判成功但 ground truth 判错）是最重要的内部指标，它比表面 SUCCESS 数更能说明系统是否在自欺。

### 10.4 录制回放

录制器在真实站点跑的时候把每步的 AX 快照、DOM 片段、网络响应、截图存成 fixture；回放时 FakeBrowser 从 fixture 返回。每次线上失败一键压成确定性回归用例。

先做 6–8 个场景覆盖五个任务族加两个典型失败模式（无进展循环、无证据答案被拒），其余靠失败驱动增长。**不手写 20 个想象出来的场景。**

### 10.5 A/B 方法学

每次只改一个变量：model profile、prompt 版本、AX-only vs AX+vision、memory off/shadow/assist、verifier 开关。固定 corpus、seed、配置。

对 live 站点的 A/B 必须记录时间戳，因为页面变化是混杂因子。**固定 fixture 做主判据，live 只做验证。**

RunManifest 记录 `git_commit / corpus_digest / config_digest / policy_digest / model_route_digest / seed / started_at / environment`。**没有 RunManifest 的分数不参与版本比较。**

---

## 11. 配置与可观测性

### 11.1 default.toml

```toml
[runtime]
max_steps_hard = 100
use_reference_length = true      # 若任务文件带 reference_length
soft_wall_clock_s = 720
hard_wall_clock_s = 1080
max_workers = 8
model_timeout_s = 165

[perceive]
ax_enabled = true
dom_supplement = true
snapshot_diff = true
max_interactive_targets = 60

[capture]
max_requests = 800
max_body_bytes = 32768
drop_polling_duplicates = true

[finalize]
compose_final_view = true
verify_operation_requirements = true

[memory]
backend = "null"                 # null | everos
mode = "off"                     # off | shadow | assist
timeout_ms = 2000
visibility_overlay_ttl_s = 15

[knowledge]
enabled = false                  # Phase A/B 关闭；第 3 周撰写、第 4 周 A/B 后置 true
source = "local"                 # local(knowledge/ 目录) | everos
top_k = 3
timeout_ms = 1500

[policy]
block_search_engines = true
allow_arbitrary_http = false
persist_raw_reasoning = false

[model]
profile = "deepseek"             # deepseek | kimi | mixed(Phase C)
allow_cross_vendor = false       # 仅 mixed 可置 true
```

注意 `vision_enabled` 已移除——视觉能力由 profile 的 vision 角色决定（`provider="none"` 即无视觉），不再是独立开关。

### 11.2 环境变量

`DEEPSEEK_API_KEY` `MOONSHOT_API_KEY` `EVERWEB_CONFIG` `EVERWEB_LOG_LEVEL` `EVEROS_BASE_URL`

密钥禁止写进 TOML、result、capture、RunManifest。

### 11.3 doctor

启动前检查：

- Python 与依赖版本
- 配置可解析，**且通过厂商隔离校验（INV-10）**
- 各 provider 最小请求可通，**返回的 model 字段字面等于配置值**
- CDP 可连接且能 `new_context()`
- 输出目录可写且支持原子替换
- 磁盘余量、时钟
- 搜索引擎 denylist 生效
- 官方入口参数兼容

### 11.4 单题诊断第一页

```
Task / Terminal State / Answer
Contract Coverage / NavigationGate / AnswerGate
Operation Requirements（逐条 satisfied 状态）★
Final Screenshot 预览 ★
Evidence Gap（含 visual_only 标记）★
First Divergent Event / Last Stable Page
Recent Actions / Verifier Failures
Steps / Wall Clock / Model Calls / Cost
Artifacts / Config & Route Digests
```

打星项对应评分器的证据通道与感知层缺口，是「为什么这题没过」的最常见答案。

---

## 12. 实施路线

冻结日 7/28，模板未发布，提交期 8 月底。

### 12.1 阶段门禁

| 阶段 | 内容 | 通过判据 |
| --- | --- | --- |
| **A** | 主链路 + `profile.deepseek` 单臂（纯文本） | 本地评测集 E2E 达基线；p95 墙钟在预算内；零崩溃；**NullVision 契约测试通过** |
| **B** | `profile.kimi` 单臂（多模态） | 同上；产出纯文本 vs 多模态的第一份对比 |
| **C** | `profile.mixed` | **仅在 A、B 都达标后启动** |

**Phase A 的唯一目标是跑起来。** 任何不属于「从任务描述走到合法输出目录并拿到有证据支撑的答案」这条主链路的工作，一律后移——包括通用操作文档（第 3 周）、站点 playbook（默认不做，见 §9.7）、EverOS 召回（第 3 周 shadow）、自部署 VLM 评估（Phase B 之后）。

A 与 B 不完全串行：Moonshot adapter 兼容 OpenAI 格式、工作量很小，可在 Phase A 期间顺手写完并做连通性验证，但**不跑完整评测**。这样 Phase B 启动时没有工程债，只是切个 profile 重跑。

若 Phase A 结束时纯文本臂在图表类任务上系统性崩掉，那就提前拿到了强信号：视觉是刚需，Phase C 必须保留 K2.6 的视觉角色，且那时引入跨厂商路由是有明确理由的。

### 12.2 周计划

**第 0 周（7/28–7/31）：事实基线**

- 完成 Octo 报名与组队，**提交所有成员 GitHub 账号**（08/07 截止，卡私有仓库创建，最高优先级）
- 申请 Hugging Face 数据集访问
- 本地 Chrome CDP 跑通官方 3 个 example tasks，保存 baseline 输出作为对照
- 建仓库、依赖、CI；先写**输出一致性测试**
- 建 domain types、trace 写入、CompetitionAdapter v0、FakeBrowser 骨架

DoD：无 API key 也能跑确定性场景；单题能从 entry 走到合法输出目录；CI 10 分钟内结束。

**第 1 周（8/1–8/7）：纵向切片（Phase A 开始）**

- AX 快照 + DOM 补充 + snapshot diff
- 语义定位动作 + 效果校验
- DeepSeek adapter + profile 机制 + **厂商隔离校验**
- Moonshot adapter（写完但不跑评测）
- TaskAnalyzer + AnswerContract（含 `operation_requirements`）
- EvidenceLedger + Extractor + V0–V2 验证
- 双门禁 + **Finalize 终态取景**
- **证据阶梯 + NullVision 契约 + `visual_only_fallback_count` 埋点**
- 自建 25 题开发集 + AnswerEval（建集时顺手统计站点集中度，1 小时副产品，见 §9.7）

不做：通用操作文档、站点 playbook、EverOS 召回。主链路优先。

DoD：一道真实题能从自然语言走到有证据支撑的 `agent_answer`；终态截图里能看见答案；失败能看到 first divergence；**NullVision 下全流程不崩**。

**第 2 周（8/8–8/14）：抽取能力（Phase A 收尾 → Phase B）**

- 五个任务族的抽取路径：文档、表单、多源比较、完整集合、图表
- StopProof、多源版本表、图表取数链（严格按证据阶梯）
- V3 反例审查（从原始证据重新推导）
- **Phase A 门禁评估** → 通过则切 `profile.kimi` 进入 Phase B
- EverOS 本地启用（只写 `agent_case`，不召回）

DoD：五类任务各有确定性 fixture；缺一项的集合答案必然失败；单位与日期归一化测试通过；有第一个可信的本地 E2E 数字；拿到 `visual_only_fallback_count` 实测值。

**第 3 周（8/15–8/21）：稳定性与迁移**

- NoProgressRecovery、模态框 / 新标签页 / 下载恢复
- 双预算与三条触发线
- 8 并发压测、context 隔离验证、backpressure
- **比赛模板迁移**（此时应已发布）+ 模板一致性测试
- **Phase B 门禁评估**；若 A、B 均达标，启动 Phase C
- **撰写 `knowledge/` 通用操作文档 + 召回注入通路**（依据前两周实测失败分布反推内容，§9.7）
- **站点 playbook 重启判据评估**（看 top-20 域名覆盖率是否 ≥ 40%；不达标直接放弃）
- **自部署 VLM 决策点**（前提：Kimi 流程已跑通且拿到 `visual_only_fallback_count` 实测值，§15.3）
- EverOS shadow 模式等价性验证（并行轨道，不阻塞）
- 故障注入套件

DoD：8 个 worker 无串任务与 context 泄漏；单任务崩溃不影响其他 worker；`output_valid_rate = 100%`；memory 故障不影响无记忆基线；secret leak = 0；`knowledge/` 文档成稿且能在 `enabled=true` 下正常注入。

**第 4 周（8/22–月底）：冻结与提交**

- **通用操作文档 A/B**（held-out 上 `knowledge.enabled` 开关对比）；无可测量负收益即置 `true` 进评测期
- 若站点 playbook 判据达标：8 小时时间盒内完成 ≤ 15 站，随通用文档同批 A/B
- 冒烟环境通过、云沙箱网络与下载能力验证
- 冻结 prompt / config / policy / route / knowledge，生成 digest
- held-out 全量跑，无 P0/P1 回归
- rollback tag、提交 Runbook、多次提交对比

禁止：临时启用未经 held-out 验证的改动；更换主模型后不跑全量回归；在 main 做大重构；为个别题改坏通用路径。

### 12.3 工作项切分

| # | 标题 | 风险 |
| ---: | --- | --- |
| 01 | docs: 冻结比赛事实、评分器行为与架构不变量 | 低 |
| 02 | build: Python 包、CI、依赖方向门禁 | 低 |
| 03 | domain: task / contract / evidence / decision / trace 类型 | 低 |
| 04 | competition: 官方输入输出适配 + 一致性测试 | 中 |
| 05 | browser: Playwright over CDP + 动作执行 + 效果校验 | 高 |
| 06 | perceive: AX 快照 + DOM 补充 + snapshot diff | 高 |
| 07 | perceive: 网络捕获与 capture.json 策略 | 中 |
| 08 | model: ModelPort + 双 provider adapter + profile 路由 + **厂商隔离校验** | 中 |
| 09 | answer: TaskAnalyzer + AnswerContract + operation_requirements | 中 |
| 10 | answer: EvidenceLedger + Extractor + V0–V2 | 中 |
| 11 | report: **Finalize 终态取景 + 输出写入** | 中 |
| 12 | answer: 双门禁 + V3 + StopProof | 高 |
| 13 | perceive: **证据阶梯 + 文档 / 图表路径 + VisionPort/NullVision** | 中 |
| 14 | harness: fixture 录制回放 + AnswerEval + A/B runner | 中 |

并行轨道（不阻塞主线）：

- `memory: MemoryPort + EverOS adapter + shadow 等价性`
- `recovery: 无进展与页面恢复`
- `ops: 8 并发压测与故障注入`
- `knowledge: 通用操作文档撰写 + 注入通路`（**第 3 周才启动**，不在第 1 周）

---

## 13. 风险登记

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 模板未发布，接口未知 | 迁移返工 | CompetitionAdapter 保持薄层，差异全收口 |
| 比赛版评分器与开源 NavEval 不同 | 证据层优化落空 | 证据设计本身也提升真实正确率，不是纯博弈 |
| 云沙箱网络出口受限 | 部分站点/下载不可达 | 冒烟期专项验证，文档类任务准备降级路径 |
| 墙钟耗尽而非步数 | 未验证就终止 | 双预算、三条触发线、Flash 承担高频角色 |
| **纯文本臂视觉缺口过大** | Phase A 数字失真 | `visual_only_fallback_count` 埋点提前量化；证据阶梯前五档做扎实 |
| 多语言站点 | AX name 与答案语言错配 | `answer_language` 显式建模，实体保原文 |
| 跨域数据 API | 操作证据对评分器隐形 | 识别后优先选会改 URL 的交互，靠终态截图兜底 |
| 完整集合漏项 | 整题失败 | StopProof 硬要求 |
| capture 超 120k 被截断 | 早期筛选证据丢失 | 噪音剔除 + 体积上限 |
| status 写 `"FAIL"` | 被评分器跳过 | INV-7 + 输出一致性测试 |
| **误用 kimi-k2.7 / k3** | 成绩无效 | 硬编码字面量、直连官方端点、doctor 校验返回 model |
| 8 并发 context 污染 | 答案与轨迹交叉污染 | 每任务新 context，一 CDP 一任务 |
| A/B 结论被站点变化混杂 | 选错模型 | 固定 fixture 做主判据，live 只做验证 |
| **跨厂商路由污染 A/B** | 结论不可信 | INV-10 机器强制，配置校验失败即启动失败 |
| EverOS 负迁移 | 旧经验误导 | 默认 off，shadow 等价性测试，A/B 才准开 |
| **通用文档后移到第 3 周，来不及 A/B** | 已决定进评测期却无验证 | 第 3 周成稿即锁定，第 4 周只跑开关对比；若第 3 周未成稿则整条放弃，不带半成品进评测 |
| **站点 playbook 判据踩线时反复权衡** | 挤占冻结周 | 判据是单一数字且阈值写死，达标则 8 小时时间盒，超时即停，不追加 |

关于目标：论文里最强基线是 21%，用的是 2025 年的模型与纯视觉感知。我们有更强的模型选择、结构化感知与专门的抽取验证层，往上推有现实空间。但这是一个刻意设计成「反搜索引擎、反浅层匹配」的基准，**不承诺具体数字**——用 held-out 的 E2E 数据说话，每一步改动都要能归因。

---

## 14. 与 v1.0 的差异对照

| 维度 | v1.0 | v2.0 | 理由 |
| --- | --- | --- | --- |
| 输出层 | 兼容官方格式 | **对齐评分器三个证据通道 + Finalize 取景** | 逆向 `naveval.py` |
| 感知 | 混合感知，DOM 优先 | AX 为主 + DOM 补充 + snapshot diff | 行业收敛做法，token 与可靠性双赢 |
| 视觉 | 独立 VisionProvider，始终可用 | **证据阶梯末档 + NullVision 契约** | 强制把前五档做扎实；使视觉价值可测量 |
| 并发 | asyncio + async Playwright | 同步 Playwright + 进程隔离 | 对齐官方 runner，无并行度损失 |
| 状态 | SQLite 事件溯源 + projection + outbox | JSONL trace + run.json | 单进程单任务，无恢复需求 |
| 预算 | 步数四分区（55/22/13/10） | 双预算 + 三条触发线 | 墙钟先耗尽；`reference_length` 可能收紧步数 |
| 契约 | 无操作要求字段 | **`operation_requirements`** | 评分器要求筛选/排序精确匹配 |
| 语言 | 写死 zh-CN | `answer_language` 跟随任务 | 站点覆盖中英西法 |
| 模型 | 定死 DeepSeek | **厂商隔离的三阶段 A/B** | 主模型选择应由数据决定，且变量不能污染 |
| 第二模型 | （无） | Kimi K2.6 | 用户决策；原生多模态，CharXiv 与 Gemini 3.1 持平 |
| 记忆定位 | 第一阶段接入 EverOS | 并行轨道，服务开发迭代，评测默认 off | 100 题跨约 100 站点，评测期复用近零 |
| 记忆接口 | `submit_verified_case` | `submit_run`（trace → messages） | EverOS 摄入的是对话形状 |
| 记忆 scope | `everweb:<role>:<version>` | `everweb_navigator_v1` | 冒号非法，会 422 / 路径错误 |
| 记忆 API | `/api/v1` | `/api/v2` | v2 是 canonical |
| 一致性窗口 | 「短时间」 | 15 秒 overlay | 官方文档：负载下 10–15 秒 |
| 操作文档 | （未提及） | **自建通用手册进评测期，第 3 周排期** | Protocol II 消融 +8.3/+8.4；但让位于主链路 |
| 站点 playbook | （未提及） | **默认不做**，判据 + 8 小时时间盒 | 收益是推测，主链路优先 |
| 测试 | 20 个手写场景 + 7 层 | 6–8 个录制场景，失败驱动增长 | 手写只能覆盖想得到的 |
| 不变量 | 15 条 | 11 条 | 每条对应真实失败模式 |
| PR | 26 个 | 14 个主线 + 4 条并行轨道 | 五周窗口 |

---

## 15. 冻结清单与待决事项

### 15.1 本次冻结的决定

1. 三阶段模型路线：DeepSeek 单臂 → Kimi 单臂 → 混合，且混合需前两阶段达标
2. 厂商隔离由配置校验机器强制（INV-10）
3. `profile.deepseek` 无视觉；视觉是证据阶梯末档（INV-11）
4. EverOS 定位为并行轨道，评测期默认 `off`
5. EverOS 接入按 `/api/v2` + 对话形状摄入 + 可读 `project_id`
6. 通用操作文档**目标进评测期**，但排期后移：第 3 周撰写、第 4 周 A/B，Phase A/B 期间 `knowledge.enabled = false`
7. 站点专属 playbook **默认不做**；仅保留 1 小时统计副产品，重启判据为 top-20 域名覆盖率 ≥ 40%，若重启则硬时间盒 8 小时 / ≤ 15 站 / 不引入新机制
8. 自部署 VLM 的评估推迟到 Kimi 流程跑通之后（第 3 周），Phase A 不讨论
9. 输出层以 Finalize 终态取景为核心

### 15.2 模板发布后必须复核

- 标准入口脚本的准确文件名与参数形式
- `agent_answer` 的字符、语言与 JSON 结构限制
- 「一步」的精确定义
- 每题总墙钟超时
- 是否允许同一任务内对失败动作做有限纠错
- 是否允许下载文件后解析
- `capture.json` 的脱敏与大小限制
- 可安装的系统包、wheel、磁盘与内存配额
- 正式评分是否同时使用 NavEval、规则与 LLM judge
- `thoughts` 是否允许只存决策摘要
- 模型服务的公网连通检查方式

这些差异统一收口在 `CompetitionAdapter`，**不允许扩散到 core**。

### 15.3 待决事项

| # | 事项 | 决策时点 | 依据 |
| ---: | --- | --- | --- |
| 1 | 站点专属 playbook 是否重启 | 第 3 周（Phase B 门禁时） | top-20 域名题目覆盖率 ≥ 40%；否则永久放弃 |
| 2 | Phase C 的具体角色配置 | Phase A、B 门禁后 | 两臂实测 + `visual_only_fallback_count` |
| 3 | 纯文本臂是否需要厂商中立的自部署 VLM | 第 3 周，**Kimi 流程跑通之后** | 视觉缺口大小；**需先回查规则原文关于自部署模型的条款** |

已从待决转为已决：通用操作文档进评测期（§15.1 第 6 条），第 4 周 A/B 仅保留否决权。

---

## 附录 A：EverOS 调研纪要

调研范围：`README.md`、`docs/api.md`、`docs/architecture.md`、`docs/reflection.md`、`docs/prompt_slots.md`、完整仓库树。

**存储三件套**

```
Markdown (truth)  →  SQLite (state)     →  LanceDB (index)
entries+frontmatter   变更队列+LSN+审计     向量ANN+BM25+标量过滤
Git 友好、Obsidian 可读  系统数据            可从 md 完全重建
```

**Markdown 布局**

```
~/.everos/
└── <app_id>/<project_id>/
    ├── users/<user_id>/
    │   ├── user.md
    │   ├── episodes/episode-<YYYY-MM-DD>.md
    │   ├── .atomic_facts/…
    │   └── .foresights/…
    ├── agents/<agent_id>/
    │   ├── .cases/agent_case-<YYYY-MM-DD>.md
    │   └── skills/skill_<name>/SKILL.md
    └── knowledge/
```

**关键 API**

| 端点 | 说明 |
| --- | --- |
| `POST /api/v2/memory/add` | `messages[]`，OpenAI Chat Completions 形状，timestamp 为毫秒 |
| `POST /api/v2/memory/flush` | 强制抽取；返回 `extracted` / `no_extraction` |
| `POST /api/v2/memory/search` | `user_id` XOR `agent_id`；method / top_k / radius / min_score / filters |
| `POST /api/v2/memory/get` | 分页列举，无排序打分 |
| `POST /api/v2/ome/trigger` | 手动触发策略，如 `reflect_episodes` |
| `/api/v2/knowledge/*` | 文档 CRUD + 主题混合搜索 + 分类法 |

**SearchMethod**

| 值 | 行为 |
| --- | --- |
| `keyword` | BM25，无 embedding 成本 |
| `vector` | 稠密向量 ANN |
| `hybrid`（默认） | RRF 融合 BM25 + 向量 + 标量过滤，一次 LanceDB roundtrip |
| `agentic` | 迭代 cluster-path + cross-encoder rerank 循环；**官方建议仅离线/后台使用** |

**约束速查**

- ScopeId charset：`^[a-zA-Z0-9_.-]+$`，1–128 字符，拒绝 `.` 与 `..`
- Filter DSL 可用字段仅：`session_id` `parent_type` `parent_id` `timestamp` `sender_id`
- Filter DSL 保留字（出现即 422）：`owner_id` `owner_type` `app_id` `project_id`
- `top_k = -1` 会自动套用服务端默认 radius；`1..100` 则不会
- `enable_llm_rerank` 仅对 `agent_case` / `agent_skill` 融合生效
- 索引最终一致：典型亚秒，**负载下 10–15 秒**
- 无内置鉴权，默认只绑 `127.0.0.1`

---

## 附录 B：Kimi K2.6 核对纪要

| 项 | 值 |
| --- | --- |
| 架构 | MoE，1T 总参 / 32B 激活，384 experts 选 8，61 层，MLA，SwiGLU |
| 上下文 | 262,144 |
| 视觉编码器 | MoonViT 400M |
| 模态 | 文本 + 图像 + 视频 |
| 接口 | `https://api.moonshot.ai/v1`，OpenAI 全兼容 |
| 支持 | tool calls、JSON mode、streaming、thinking / non-thinking、partial mode |
| 图像输入 | **仅 base64 data URI 或 file ID，不支持远程 URL** |
| 请求体上限 | 100MB |
| 价格 | 命中 $0.16 / 未命中 $0.95 / 输出 $4.00（每 1M） |
| 缓存 | 自动，无需配置，约省 80–85% |
| 权重 | Modified MIT |

**Benchmark**

| 类别 | 指标 | K2.6 |
| --- | --- | ---: |
| Agentic | BrowseComp | 83.2% |
| Agentic | BrowseComp Agent Swarm | 86.3% |
| Agentic | OSWorld-Verified | 73.1% |
| Agentic | HLE-Full w/ tools | 54.0% |
| Agentic | SWE-Bench Pro | 58.6% |
| Agentic | Terminal-Bench 2.0 | 66.7% |
| Coding | LiveCodeBench v6 | 89.6% |
| Vision | MMMU-Pro | 79.4% |
| Vision | CharXiv (RQ) | 80.4% |
| Vision | MathVision | 87.4% |
| Reasoning | AIME 2026 | 96.4% |
| Reasoning | GPQA Diamond | 90.5% |

**禁用的同厂更高版本**：`kimi-k2.7-code`、`kimi-k2.7-code-highspeed`、`kimi-k3`。

---

*本文档为 Phase A 起的执行基线。任何偏离需在 PR 描述中显式说明并更新本文对应章节。*
