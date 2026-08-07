# EverWeb 架构对齐执行计划 v1.0

> 本文把 [`EverWeb_Architecture_v2.2_Kimi_First.md`](../architecture/EverWeb_Architecture_v2.2_Kimi_First.md) 转换为严格线性的工程执行账本。  
> **一条执行步骤对应一个 Git commit；每个 commit 必须单一目标、可独立验证、可独立回滚、禁止 WIP。**

## 1. 文档元数据

- 执行计划版本：v1.0.0
- 对齐架构版本：v2.2.0（Kimi First）
- 目标语言与运行时：Python 3.12
- 目标赛道：WebRetriever Challenge 2026 · Protocol III
- 当前状态：待执行
- 计划规模：88 个 commits（文档治理 2 + 工程基座 3 + Week 0～4 共 83）
- 正式模板状态：`PendingTemplate`
- 权威优先级：架构 v2.2 > 本执行计划 > 历史架构 > 本地 diagrams

## 2. 执行纪律

### 2.1 一步一 commit

每一步必须满足：

1. 只有一个可陈述的逻辑目标。
2. 测试和实现包含在同一个 commit 中；工作区内可执行 TDD，但不得提交红灯状态。
3. commit 完成后，所有当时已存在的必需 CI 检查保持通过。
4. 不依赖未来未提交代码才能导入、运行或通过测试。
5. 不混入重命名、格式化、依赖升级或相邻功能。
6. 能通过单独 `git revert` 撤销，不破坏更早步骤。
7. commit 标题使用本文给出的 Conventional Commit，不得临时改写语义。

### 2.2 禁止跳步

- 默认严格按 ID 顺序执行。
- 只有标记为 `⏸ PendingTemplate` 的步骤可以暂停；暂停期间只能执行明确不依赖正式模板的后续步骤。
- 若发现步骤过大或依赖错误，先提交独立的 `docs(plan)` 修订，再继续编码。
- 不得为适配已有实现而降低 `INV-*`、Gate、Proof、测试或安全要求。

### 2.3 每步开始条件

- 前置 commit 已完成且验证通过。
- 已阅读对应架构章节和适用 `INV-*`。
- 不存在未解释的代码、测试与架构冲突。
- 所需 Provider、CDP、正式模板或 sealed 权限已具备；否则保持暂停。

### 2.4 每步完成条件

- 目标范围内实现和测试完成。
- 对应 Unit、Contract、Scenario、Fault、Live 或 Release Gate 检查通过。
- 无反向依赖、直接目标站 HTTP、Serializer 副作用、证据旁路和秘密泄漏。
- `git diff` 仅包含本步骤相关修改。
- 执行记录填写 commit hash、验证结果和偏差。

## 3. 测试层级

- `U` — Unit：schema、Policy、StepMeter、Budget、Evidence、Proof、Gate、Serializer、Redaction。
- `C` — Contract：Ports、Null adapters、CompetitionAdapter、OutputContract、Provider Manifest。
- `S` — Scenario：`state + TypedAction → next state + Receipt`。
- `F` — Fault：timeout、429/5xx、malformed、disconnect、crash、SIGKILL、OOM、disk、JSONL half-line。
- `L` — Live：真实 CDP、真实 Provider、并发、延迟、配对 A/B；允许统计波动。
- `G` — Release Gate：冻结前全量门禁。

Replay 只对规范化后的 Harness 行为要求确定性；真实 Provider 和真实网站不得断言逐字节 Trace 相同，对齐 `INV-13`。

## 4. PendingTemplate 冻结清单

正式模板发布前不得实现或猜测：

1. `official_status_values`
2. `official_output_schema`
3. `official_step_semantics`
4. `downloads_parseable`
5. `task_wall_clock_s`
6. `StatusMappingPolicy(template_digest)`
7. 正式 OutputMapper JSON 与目录结构
8. Contract Reconciliation 最终差异
9. `competition_contract_digest`
10. 正式 ScorerCompatibility 行为
11. EmergencyEmitter 正式目录映射
12. sealed 正式评分接入
13. rollback tag 与 submission runbook 终版
14. `reconcile_template.py` 的正式覆盖层

Week 0～3 只允许使用内部终态、`OfficialOutputDraft`、显式 `None/PendingTemplate` 和本地计步模式。

## 5. Commit 状态记录格式

每步在执行对应 `git commit` 前，将状态从 `未开始` 或 `⏸ PendingTemplate` 更新为 `完成`，并填写：

```text
状态：
验证命令：
验证结果：
偏差/未验证项：
```

状态和验证证据必须与实现进入同一个 commit。commit hash 不能写入自身内容，否则会形成无法收敛的自引用；实际 hash 以 `git log` 为权威，可在外部报告中引用。

提交前门禁必须确认：

1. 执行计划已暂存。
2. 恰好一个步骤从未完成状态变为 `完成`。
3. 所有更早的非 Pending 步骤已经完成。
4. 使用该步骤预定义的 Commit 标题。

---

## 6. 文档与治理基线

### DOC-001 — 建立架构与 Agent 治理基线

- 状态：完成（历史补记）
- Commit：`docs: establish architecture and agent governance baseline`
- 已提交：`961756c73913de2187dff7ea6fdf07d217f6299e`
- 单一目标：提交当前架构谱系、文档导航、执行计划、`.cursor` 治理和 `.gitignore`，建立实现前的唯一基线。
- 架构对齐：§0、§1、§3、§31、§36。
- 不变量：为 `INV-1`～`INV-16` 提供治理入口，不实现运行时代码。
- 前置：无。
- 范围：`.cursor/`、`.gitignore`、`docs/README.md`、`docs/architecture/`、`docs/archive/`、`docs/execution/`；排除 `docs/diagrams/`。
- 验收：
  - [x] v2.2 明确为唯一当前架构。
  - [x] v1.0、v2.0、v2.1 明确标为历史参考。
  - [x] Rules、Skills、Verifier 和安全可用的 Hooks 可被 Cursor 发现。
  - [x] Git 不包含 diagrams 生成物和秘密文件。
  - [x] 本计划中的 commit 数量、依赖和 PendingTemplate 标记自洽。
- 测试层级：文档链接检查、Cursor 配置语法检查、`git status` 审计。
- 回滚边界：仅移除治理与文档基线，不涉及生产代码。
- 偏差：首条 commit 未同步步骤状态；由 DOC-002 补记并增加提交前硬门禁。

### DOC-002 — 强制执行账本随 commit 更新

- 状态：完成
- Commit：`fix(governance): enforce execution ledger updates before commits`
- 单一目标：增加 Cursor Rule 与提交前 Hook，阻止未同步本执行计划的后续 commit。
- 架构对齐：§31、§36、本计划 §2 与 §5。
- 前置：DOC-001。
- 范围：`.cursor/rules/`、`.cursor/hooks.json`、`.cursor/hooks/`、本执行计划。
- 验收：
  - [x] `git commit` 前必须暂存本执行计划。
  - [x] 每次只能完成一个步骤。
  - [x] 更早的非 Pending 步骤不能保持未完成。
  - [x] Hook 传输解析异常不会锁死工作区。
  - [x] Rules 明确要求使用步骤预定义的 commit 标题。
- 测试层级：Hook 单元式输入测试与实际暂存区检查。
- 回滚边界：只移除治理门禁，不影响架构与生产代码。
- 偏差：实际 commit hash 由 Git 历史提供，不写入 commit 自身。

### DOC-003 — 禁止未经明确要求的 commit/push

- 状态：完成
- Commit：`fix(governance): require explicit user approval for commits`
- 单一目标：将 Git 提交流程规则改为始终生效，并明确禁止在未获用户当前轮次明确授权时执行 `git commit` / `git push`。
- 架构对齐：§31、§36、本计划 §2 与 §5。
- 前置：DOC-002。
- 范围：`.cursor/rules/00-project-contract.mdc`、`.cursor/rules/60-git-workflow.mdc`、本执行计划。
- 验收：
  - [x] `60-git-workflow` 设为 `alwaysApply: true`。
  - [x] 明确计划/todo deliver、“执行完毕”、账本标完成、本地测试通过均不构成提交授权。
  - [x] 项目契约增加禁止擅自 commit/push 的硬约束。
- 测试层级：规则文件审阅与暂存区审计。
- 回滚边界：只回滚治理规则措辞，不影响生产代码与既有账本门禁。

### DOC-004 — 对齐 competition→domain 与 supervisor/core→report 依赖

- 状态：完成
- Commit：`fix(governance): align competition domain and report dependencies`
- 单一目标：纠正 BL-003 过窄的 import 门禁，使正式契约映射可依赖 domain，并使运行时能诚实调用 report Writers/Serializer，同时继续隔离 answer/adapters/harness。
- 架构对齐：§4.3、§4.4、INV-2、INV-3。
- 前置：DOC-003、BL-003、W0-012。
- 范围：`docs/architecture/EverWeb_Architecture_v2.2_Kimi_First.md`、`pyproject.toml`、`.cursor/rules/10-architecture-boundaries.mdc`、`tests/contract/test_import_boundaries.py`、本执行计划。
- 验收：
  - [x] 架构 §4.3/§4.4 明确允许 `competition → domain` 与 `supervisor/core → report`。
  - [x] `competition-public-entry` 不再禁止 `everweb.domain`；仍禁止 report/answer/adapters/supervisor 私有子模块。
  - [x] `runtime-side-boundaries` 不再禁止 `everweb.report`；仍禁止 adapters/answer/perceive/harness。
  - [x] import 契约测试与 canary 覆盖允许边与违规边。
- 测试层级：Contract（import-linter）。
- 回滚边界：只回滚依赖门禁与文档表述，不影响业务实现。
- 偏差记录：这是对 BL-003 过窄门禁的纠正，不是放宽 answer/adapters 隔离。
- 验证证据：`pytest tests/contract/test_import_boundaries.py` 16 passed；`lint-imports --no-cache` 10 kept。

### DOC-005 — 修复 Fake adapters 相关 mypy 门禁

- 状态：完成
- Commit：`fix(harness): satisfy mypy for fake adapter contracts`
- 单一目标：修复 W0-015 推送后 CI Type check 失败，使 `mypy src tests` 在严格模式下通过。
- 架构对齐：§31、本计划 §2.1。
- 前置：DOC-004、W0-015。
- 范围：`tests/contract/test_fake_browser_model.py`、`tests/fault/test_emergency_emit_on_kill.py`、本执行计划。
- 验收：
  - [x] `module.__file__` 经显式非空断言后再构造 `Path`。
  - [x] `signal.SIGKILL` 经 `getattr` 取得，避免 Windows typeshed 缺属性导致本地/交叉检查失败。
  - [x] `python -m mypy src tests` 通过。
- 测试层级：Type check（mypy）+ 既有 Contract/Fault 回归。
- 回滚边界：只回滚测试侧类型收窄，不影响 Fake Port 行为。

### DOC-006 — 排除本地 verify 脚本的 ruff 范围

- 状态：完成
- Commit：`build: exclude verify scripts from ruff`
- 单一目标：修复 W1-001 推送后 CI Lint 因本地 `verify/` CDP 探针脚本失败的问题。
- 架构对齐：§31、BL-002（非产品路径不进入质量门禁）。
- 前置：W1-001。
- 范围：`pyproject.toml` ruff `exclude`、本执行计划。
- 验收：
  - [x] `verify/` 与 `.cursor/` 一并排除出 `ruff check .`。
  - [x] 产品 `src/` / `tests/` lint 仍覆盖；`python -m ruff check .` 全绿。
- 测试层级：Lint（ruff）+ 既有 CI 契约回归。
- 回滚边界：只调整 lint 排除列表，不改 BrowserPort / adapter 行为。

### DOC-007 — 修复 PageView 模块导入顺序

- 状态：完成
- Commit：`fix(perceive): restore page_view future import order`
- 单一目标：修复 W1-003 推送后 CI Lint/`from __future__` 语法失败。
- 架构对齐：§31、本计划 §2.1。
- 前置：W1-003。
- 范围：`perceive/page_view.py`、本执行计划。
- 验收：
  - [x] 移除误插在文件顶部的重复 `PageIdentity` 导入。
  - [x] `from __future__ import annotations` 位于文件合法位置；`ruff check .` 与 perceive 测试通过。
- 测试层级：Lint（ruff）+ perceive Unit 回归。
- 回滚边界：只修正导入顺序，不改 PageView 组装语义。

### DOC-008 — 补齐 W1-004 验收清单

- 状态：完成
- Commit：`docs(plan): clarify W1-004 acceptance criteria`
- 单一目标：将已完成的 W1-004 口号式验收补齐为可勾选范围/验收/明确不做/验证证据，对齐 W1-001～003 账本粒度。
- 架构对齐：本计划 §2.1、W1-004。
- 前置：W1-004。
- 范围：仅本执行计划 W1-004 条目文案；不改产品代码。
- 验收：
  - [x] W1-004 含范围、可勾验收、测试层级、明确不做、验证证据。
  - [x] 不改变 W1-004 状态（保持完成）；不夹带其它步骤状态迁移。
- 测试层级：文档一致性（对照已落地实现与既有测试）。
- 回滚边界：只回退账本文案，不影响 `5021cd6` 实现。

---

## 7. Baseline — 工程基座

### BL-001 — 初始化 Python 工程骨架

- 状态：完成
- Commit：`chore: initialize everweb python project skeleton`
- 目标：创建 §5 目录树、`pyproject.toml`、Python 3.12 包和运行目录占位。
- 对齐：§0、§5。
- 前置：DOC-001。
- 验收：包可安装、`import everweb` 成功、目录所有权与 §5 一致。
- 测试：`U` import smoke。
- 回滚：不影响文档基线。
- 验证命令：`python -m venv .venv`；`.venv\Scripts\python.exe -m pip install -e ".[dev]"`；`.venv\Scripts\python.exe -m pytest -q`；`.venv\Scripts\python.exe -c "import everweb"`；PowerShell `Test-Path` 目录审计。
- 验证结果：Python 3.12.10 可编辑安装成功；2 个 import smoke 测试通过；`import everweb` 成功；§5 的 32 个仓库拥有目录均存在。
- 偏差/未验证项：`evalset/sealed/` 按安全 Hook 保持只读且由外部挂载或创建，不提交占位内容；未来步骤拥有的模块文件未提前创建。

### BL-002 — 建立无密钥 CI

- 状态：完成
- Commit：`build: add ci pipeline without api keys`
- 目标：建立 lint、type、test CI，默认不读取 Moonshot/DeepSeek 密钥。
- 对齐：§31 Week 0 DoD。
- 前置：BL-001。
- 验收：干净环境 CI 全绿且 10 分钟内结束；无 Provider 与 CDP 依赖。
- 测试：`U`。
- 验证命令：`.venv\Scripts\python.exe -m pip install -e ".[dev]"`；`.venv\Scripts\python.exe -m ruff check .`；`.venv\Scripts\python.exe -m mypy src tests`；`.venv\Scripts\python.exe -m pytest -q`；`git diff --check`。
- 验证结果：Ruff 全绿；mypy strict 检查 20 个源文件无问题；4 个 Unit 测试通过；CI 契约确认 Python 3.12、只读权限、10 分钟超时，且无密钥、Provider、Playwright/CDP 或 sealed 数据依赖。
- 偏差/未验证项：依赖安装首次受 PyPI 下载超时中断，重试后成功；`.cursor/` 治理脚本不属于产品 CI lint 范围并由 Ruff 排除；GitHub Actions 干净 runner 的 run URL、结论与耗时在本 commit 推送后作为外部验收证据记录。

### BL-003 — 强制分层导入边界

- 状态：完成
- Commit：`build: enforce layered import boundaries with import-linter`
- 目标：实现 §4.4 六条 import-linter 门禁。
- 对齐：§4.3、§4.4。
- 前置：BL-001。
- 验收：覆盖 layered contract、domain 隔离、adapter 独立、competition 入口、生产代码禁止导入 harness。
- 测试：`U/C` 架构测试。
- 验证命令：`.venv\Scripts\python.exe -m ruff check .`；`.venv\Scripts\python.exe -m mypy src tests`；`.venv\Scripts\lint-imports.exe --no-cache`；`.venv\Scripts\python.exe -m pytest -q`；`git diff --check`。
- 验证结果：Ruff 全绿；mypy strict 检查 21 个源文件无问题；import-linter 分析 18 个包文件并保持 10 个契约、0 个破坏（§4.4 六项加 application、adapter-runtime、根包 harness、runtime-side 四项 §4.3 闭环）；16 个 Unit/Contract 测试通过，其中 10 个负向 canary 分别证明对应契约拒绝违规 import。
- 偏差/未验证项：Provider SDK 包名未确定，因此 domain 外部隔离仅门禁架构已明确的 `playwright` 与 `httpx`，内部 Adapter 隔离已覆盖；GitHub Actions run 在本 commit 推送后作为外部验收证据。

---

## 8. Week 0 — 契约与骨架

目标：无模型、无真实网站也能生成合法内部运行目录。

### W0-001 — TaskIdentity 与基础错误类型

- 状态：完成
- Commit：`feat(domain): add task identity and error types`
- 目标：增加 `TaskIdentity`、基础 Error 与 Receipt 类型。
- 对齐：§5 `domain/`。
- 前置：BL-003。
- 验收：类型不可变、可序列化、错误码不包含正式 status。
- 测试：`U` schema。
- 验证命令：`.venv\Scripts\python.exe -m pytest tests/unit/domain -q`；`.venv\Scripts\python.exe -m ruff check .`；`.venv\Scripts\python.exe -m mypy src tests`；`.venv\Scripts\lint-imports.exe --no-cache`；`.venv\Scripts\python.exe -m pytest -q`；`git diff --check`。
- 验证结果：Pydantic 2.13.4 安装成功；16 个定向 domain 测试通过；Ruff 全绿；mypy strict 检查 27 个源文件无问题；import-linter 分析 23 个包文件与 8 条依赖，10 个契约全部保持；全量 32 个测试通过。
- 偏差/未验证项：Canonical 未定义完整 `FailureRecord` 与通用 Receipt 字段，本步骤仅实现内部 namespaced `ErrorCode`、最小 `FailureRecord(code, message)` 和无业务字段的冻结 Receipt 基类；按用户要求未提交，因此未触发 GitHub Actions。

### W0-002 — 内部终态枚举

- 状态：完成
- Commit：`feat(domain): add internal terminal state enum`
- 目标：实现 `InternalTerminalState`。
- 对齐：§6.2。
- 不变量：`INV-2`。
- 前置：W0-001。
- 验收：core/domain 不出现正式 `SUCCESS/FAIL` 语义映射。
- 测试：`U` enum + architecture assertion。
- 验证命令：`.venv\Scripts\python.exe -m pytest tests/unit/domain/test_terminal.py -q`；`.venv\Scripts\python.exe -m ruff check .`；`.venv\Scripts\python.exe -m mypy src tests`；`.venv\Scripts\lint-imports.exe --no-cache`；`.venv\Scripts\python.exe -m pytest -q`；`git diff --check`。
- 验证结果：4 个定向 enum/architecture 测试通过（含正式 status mapping 负向 canary）；Ruff 全绿；mypy strict 检查 29 个源文件无问题；import-linter 分析 25 个包文件与 10 条依赖，10 个契约全部保持；全量 36 个测试通过。
- 偏差/未验证项：仅实现 canonical 九值内部终态；`StatusMappingPolicy`、正式 status 与终止判定未实现；GitHub Actions run 在本 commit 推送后作为外部验收证据。

### W0-003 — CompetitionCapabilities 占位契约

- 状态：完成
- Commit：`feat(competition): add capabilities with pending placeholders`
- 目标：实现能力结构，未知正式字段保持 `None/PendingTemplate`。
- 对齐：§2.2、§6.1。
- 不变量：`INV-2`。
- 前置：W0-002。
- 验收：P1～P5 无猜测默认值；已公开并发、步骤、模型超时和搜索限制可表达。
- 测试：`U`。
- 验证命令：`.venv\Scripts\python.exe -m pytest tests/unit/competition/test_capabilities.py -q`；`.venv\Scripts\python.exe -m ruff check .`；`.venv\Scripts\python.exe -m mypy src tests`；`.venv\Scripts\lint-imports.exe --no-cache`；`.venv\Scripts\python.exe -m pytest -q`；`git diff --check`。
- 验证结果：22 个定向 capabilities 测试通过；Ruff 全绿；mypy strict 检查 31 个源文件无问题；import-linter 分析 26 个包文件与 13 条依赖，10 个契约全部保持；全量 58 个测试通过。
- 偏差/未验证项：`task_wall_clock_s`、`official_status_values`、`official_output_schema`、`official_step_semantics`、`downloads_parseable` 默认均为 `None`；未实现正式 status 映射、OutputMapper、competition digest 或模板覆盖层；GitHub Actions run 在本 commit 推送后作为外部验收证据。

### W0-004 — Action、Evidence 与 Trace 基础类型

- 状态：完成
- Commit：`feat(domain): add action evidence and trace envelope types`
- 目标：增加 `TypedAction`、`EvidenceAtom` 骨架和 `TraceEnvelope`。
- 对齐：§13.1、§15.1、§19.3。
- 不变量：`INV-6`。
- 前置：W0-001。
- 验收：Trace 有 seq、schema version、execution ID、event type、timestamp、checksum。
- 测试：`U` schema。
- 验证命令：`.venv\Scripts\python.exe -m pytest tests/unit/domain/test_action.py tests/unit/domain/test_evidence.py tests/unit/domain/test_trace.py -q`；`.venv\Scripts\python.exe -m ruff check .`；`.venv\Scripts\python.exe -m mypy src tests`；`.venv\Scripts\lint-imports.exe --no-cache`；`.venv\Scripts\python.exe -m pytest -q`；`git diff --check`。
- 验证结果：25 个定向 schema 测试通过；Ruff 全绿；mypy strict 检查 37 个源文件无问题；import-linter 分析 30 个包文件与 24 条依赖，10 个契约全部保持；全量 83 个测试通过。
- 偏差/未验证项：§13.1 未定义 `TypedAction` 类体，经确认仅实现 `action_id + kind` 最小骨架；checksum 算法、JSONL Writer 和序列化值门禁延后至 W0-006/W0-007；canonical `list`/`dict` 字段仅具 Pydantic 顶层冻结，深冻结在 Writer 落盘边界重新评估；GitHub Actions run 在本 commit 推送后作为外部验收证据。

### W0-005 — 定义核心 Ports

- 状态：完成
- Commit：`feat(ports): define browser model artifact and clock ports`
- 目标：定义 Browser、Model、Vision、Memory、Artifact、Clock Port。
- 对齐：§5、§9.1、§20.1、附录 A。
- 不变量：`INV-1`、`INV-11`。
- 前置：W0-004。
- 验收：Port 仅依赖 domain；无 Adapter 或 SDK 类型泄漏。
- 测试：`C` stub conformance。
- 验证命令：`.venv\Scripts\python.exe -m pytest tests/contract/test_port_conformance.py -q`；`.venv\Scripts\python.exe -m ruff check .`；`.venv\Scripts\python.exe -m mypy src tests`；`.venv\Scripts\lint-imports.exe --no-cache`；`.venv\Scripts\python.exe -m pytest -q`；`git diff --check`。
- 验证结果：5 个定向 Port contract 测试通过；Ruff 全绿；mypy strict 检查 45 个源文件无问题；import-linter 分析 37 个包文件与 45 条依赖，10 个契约全部保持；全量 88 个测试通过。
- 偏差/未验证项：canonical 仅完整定义 `BrowserCapabilities`，其余 Port DTO/Receipt 仅建立无猜测字段的严格冻结占位，留待所属后续步骤扩展；canonical 未定义 `ClockPort` 签名，经确认采用 `now() -> datetime` 与 `monotonic() -> float`，不含 sleep/推进时间；未接入 Adapter、SDK、真实 I/O 或 Null/Fake 行为；GitHub Actions run 在本 commit 推送后作为外部验收证据。

### W0-006 — Append-only Trace Writer

- 状态：完成
- Commit：`feat(report): implement append-only trace jsonl writer`
- 目标：实现单 Writer、checksum、关键阶段 flush/fsync 和 schema version。
- 对齐：§19.3。
- 不变量：`INV-6`。
- 前置：W0-004。
- 验收：按 seq 追加；尾部半行读取时忽略并产生 recovery warning。
- 测试：`U/F` 写入读回与 half-line。
- 验证命令：`.venv\Scripts\python.exe -m pytest tests/unit/report/test_trace_writer.py tests/fault/test_trace_jsonl_recovery.py -q`；`.venv\Scripts\python.exe -m ruff check .`；`.venv\Scripts\python.exe -m mypy src tests`；`.venv\Scripts\lint-imports.exe --no-cache`；`.venv\Scripts\python.exe -m pytest -q`；`git diff --check`。
- 验证结果：20 个定向 Trace Writer/Reader 与 fault 测试通过；Ruff 全绿；mypy strict 检查 48 个源文件无问题；import-linter 分析 46 个包文件与 59 条依赖，10 个契约全部保持；全量 108 个测试通过。
- 偏差/未验证项：canonical 未定义 checksum、seq 起点、事件大小数值与 Writer API，经确认采用 seq 从 1 自动连续分配、排除 checksum 字段的规范 JSON SHA-256、调用方显式提供 schema version/max event bytes、buffered/flush/fsync 三级 durability；Reader 使用同一显式上限并只忽略无 LF 尾部片段，完整坏行、乱序、非规范 JSON 或 checksum 篡改均 fail-closed；未增加 TracePort 或接入 core，运行时注入留 W0-016；未声明单测可证明操作系统断电后的物理持久性；GitHub Actions run 在本 commit 推送后作为外部验收证据。

### W0-007 — Evidence Writer 与 ArtifactRef

- 状态：完成
- Commit：`feat(report): implement evidence writer and artifact refs`
- 目标：实现 `evidence.jsonl`、`ArtifactRef` 和原子 Artifact 写入。
- 对齐：§19.1、§19.2、§23.4。
- 不变量：`INV-6`、`INV-14`。
- 前置：W0-006。
- 验收：digest/size/path 一致；敏感字段不写入共享 Artifact。
- 测试：`U/F`。
- 验证结果：Evidence/Artifact/Trace 定向与回归测试通过；Ruff 全绿；mypy strict 检查 56 个源文件无问题；import-linter 分析 57 个包文件与 93 条依赖，10 个契约全部保持；全量 164 个测试通过，4 个依赖平台符号链接权限的安全测试跳过；`git diff --check` 通过。
- 偏差/未验证项：canonical 未定义 `ArtifactWrite` 字段和 `evidence.jsonl` envelope，经确认采用 `artifact_id/kind/relative_path/content/mime_type` 与每行直接一个 `EvidenceAtom`；Reader 只忽略无 LF 尾部片段，完整坏行、重复 ID、execution 不一致和敏感内容均 fail-closed；Artifact 仅允许五类共享目录，内容与可共享元数据落盘前执行 secret/reasoning reject，并通过同文件系统 hard-link 原子发布、读回校验和 pending/committed 身份记录恢复来禁止覆盖及跨 Store ID 复用；POSIX 执行父目录 fsync，Windows stdlib 无等价目录 fsync 时明确降级，单测不声明可证明断电后的物理持久性；`computed`/ConflictSet/Candidate 活跃性留待 W1-010 及后续步骤；GitHub Actions run 在本 commit 推送后作为外部验收证据。

### W0-008 — Budget 与 StepMeter 骨架

- 状态：完成
- Commit：`feat(core): add budget and step meter skeleton`
- 目标：建立 Budget 三线和唯一 StepMeter 记录入口。
- 对齐：§6.3、§11。
- 不变量：`INV-8`。
- 前置：W0-005。
- 验收：官方步骤不能在其他模块直接递增；正式语义仍 Pending。
- 测试：`U`。
- 验证结果：40 个 Budget/StepMeter 定向 Unit 测试通过；Ruff 全绿；mypy strict 检查 60 个源文件无问题；import-linter 分析 59 个包文件与 104 条依赖，10 个契约全部保持；全量 204 个测试通过，4 个依赖平台符号链接权限的既有安全测试跳过；`git diff --check` 通过。
- 偏差/未验证项：canonical 未定义 Budget 评估 API、StepReceipt schema 及本地 iteration 计数语义，经确认采用纯 `BudgetAssessment`、最小 `StepReceipt(action_id/mode/step_delta/recorded_total)` 与 Policy 注入；`action_based` 本地默认每次 `record()` 计 1，`iteration_based`/`official_adapter` 未注入 Policy 时明确拒绝；封盘墙钟线使用 serialize+emergency reserve，模型调用耗尽单独报告而不擅自触发全局硬停；未接线 Browser/CompetitionAdapter、未切换运行时阶段，正式 `official_step_semantics` 继续保持 PendingTemplate，留 W1-005/W4-004；GitHub Actions run 在本 commit 推送后作为外部验收证据。

### W0-009 — Spawn Worker 骨架

- 状态：完成
- Commit：`feat(supervisor): add spawn-based worker process skeleton`
- 目标：实现 spawn 上下文、一 Worker 一题、一 CDP 一活跃 Worker。
- 对齐：§7.2、§7.3。
- 不变量：`INV-7`。
- 前置：W0-005。
- 验收：Playwright 初始化后无 fork；进程可启动并回收。
- 测试：`C`。
- 验证结果：18 个 Spawn Worker 定向 Contract 测试通过，1 个 POSIX SIGTERM escalation 测试因本机 Windows 跳过；Ruff 全绿；mypy strict 检查 62 个源文件无问题；import-linter 分析 61 个包文件与 114 条依赖，10 个契约全部保持；全量 222 个测试通过，5 个平台相关测试跳过；`git diff --check` 通过。
- 偏差/未验证项：canonical 未定义 Worker Process API、Assignment/Handle/WorkerExitReceipt schema，经确认采用最小冻结契约与 Parent 生成的 `execution_id/task_id/pid/exit_code` Receipt；Pool 始终使用显式 spawn context，Parent 在进程启动前独占 execution/task/CDP 租约，确认 join/reap 后才释放，启动失败回滚租约；shutdown 使用有界 terminate/join 并在 POSIX 语义下升级 kill，无法停止时保留租约并 fail-closed；默认 Worker 为可替换的顶层 no-op 入口；未引入 Playwright、Heartbeat/IPC、EmergencySnapshot、EmergencyEmitter、Scheduler 或 runtime loop，分别留 W0-010/W0-011/W0-014/W2-009/W0-016；GitHub Actions run 在本 commit 推送后作为 POSIX 与外部验收证据。

### W0-010 — WorkerHeartbeat

- 状态：完成
- Commit：`feat(supervisor): implement worker heartbeat protocol`
- 目标：实现 Heartbeat IPC 和 2～5 秒心跳契约。
- 对齐：§7.4。
- 不变量：`INV-7`。
- 前置：W0-009。
- 验收：Parent 能识别存活、过期和退出；Heartbeat 不进入模型上下文。
- 测试：`C/F` fake clock。
- 验证结果：定向 Heartbeat Unit/Fault/Contract 测试通过（含 fail-closed 保留 heartbeat 注册回归），1 个 POSIX SIGTERM escalation 因本机 Windows 跳过；Ruff 全绿；mypy strict 检查 66 个源文件无问题；import-linter 分析 65 个文件与 133 条依赖，10 个契约全部保持；全量 248 个测试通过，5 个平台相关测试跳过；`git diff --check` 通过。
- 偏差/未验证项：canonical 未定义 Heartbeat IPC、Policy/Status 或 Parent Monitor API，经确认采用每 Worker 单向 Queue + 内部 bootstrap 周期发送（保持现有 entrypoint 签名）、JSON-native wire dict、注入 `ClockPort` 的 Parent `HeartbeatMonitor`，以及 `alive/expired/exited` 三态；默认 `interval_s=3.0`、`stale_after_s=6.0`、`startup_grace_s=6.0`，interval 约束在 2～5 秒；`RuntimePhase` 落在 domain，`WorkerHeartbeat` 留在 supervisor 且不进入 `ModelRequest`；`start()` 无法安全终止时 fail-closed 保留 slot 同时保留/补齐 heartbeat 注册；未引入 EmergencySnapshot、EmergencyEmitter、Scheduler、runtime loop 相位推进或模型上下文装配，分别留 W0-011/W0-014/W2-009/W0-016；Windows 非 venv 下 import-linter 契约测试改为解析 `Scripts/lint-imports.exe`；GitHub Actions run 在本 commit 推送后作为外部验收证据。

### W0-011 — EmergencySnapshot 检查点

- 状态：完成
- Commit：`feat(supervisor): persist emergency snapshot checkpoints`
- 目标：在架构规定的关键时点持久化 EmergencySnapshot。
- 对齐：§7.5。
- 不变量：`INV-7`。
- 前置：W0-010。
- 验收：ANALYZE、成功动作、Ledger/Candidate 更新、PREPARE 前、Decision 后均可更新。
- 测试：`U/C`。
- 验证结果：定向 EmergencySnapshot Unit/Contract 33 通过、1 个 symlink run_directory 测试因环境跳过；Ruff 全绿；mypy strict 检查 72 个源文件无问题；import-linter 分析 68 个文件与 153 条依赖，10 个契约全部保持；全量 281 个测试通过，6 个平台相关测试跳过；`git diff --check` 通过。
- 偏差/未验证项：canonical 未定义 `GateReceipt` 字段，经确认采用最小冻结占位仅含 `accepted: bool`；本步提供 Supervisor `EmergencySnapshotStore` 原子写/读 `run/<execution_id>/emergency_snapshot.json` 与六值 `CheckpointReason`，用 U/C 覆盖六类时点，不接 Queue IPC、runtime loop、Evidence Ledger/Candidate/Gate 真实逻辑或 EmergencyEmitter（W0-014）；`updated_at` 由注入 `ClockPort.now()` 覆盖；损坏/截断 JSON 以 corruption 失败关闭；Windows 上目录 fsync 为 no-op（与 ArtifactStore 一致）；GitHub Actions run 在本 commit 推送后作为外部验收证据。

### W0-012 — 纯 Serializer v0

- 状态：完成
- Commit：`feat(report): add pure serializer v0 without side effects`
- 目标：从持久化事实生成 `OfficialOutputDraft`。
- 对齐：§6.4、§18.4。
- 不变量：`INV-3`、`INV-6`。
- 前置：W0-007。
- 验收：运行时无法访问 Browser、Model、Vision、Memory、网络或目录发现。
- 测试：`U/C` purity spy。
- 验证结果：定向 OfficialOutputDraft/Serializer Unit+Contract 15 通过；Ruff 全绿；mypy strict 检查 77 个源文件无问题；import-linter 分析 70 个文件与 165 条依赖，10 个契约全部保持；全量 296 个测试通过，6 个平台相关测试跳过；`git diff --check` 通过。
- 偏差/未验证项：经确认采用选项 A——`SerializeRequest` 注入已投影事实，本步不解析 TraceEnvelope、不发明 event_type 投影表；`mapped_status` 固定为 `None`，正式 status 映射留 W0-013/CompetitionAdapter；序列字段以 tuple 固化防事后篡改；`internal_terminal_state` 仅存在于 Request 不写入 Draft；未实现 EMIT、OutputMapper、FrozenStructuredAnswer/BestCandidate 完整类型或 runtime 接线；按 DOC-003 未自动提交，待用户明确要求后以预定义 commit 主题提交并推送。

### W0-013 — Output Contract Draft Mapper

- 状态：完成
- Commit：`feat(competition): add output contract draft mapper`
- 目标：建立本地 OutputContract draft 映射，正式 status 保持空缺。
- 对齐：§6.4、§19.4/§19.5（§19.5 仅作“不猜正式 schema”约束）。
- 不变量：`INV-2`、`INV-3`。
- 前置：DOC-004、W0-012。
- 范围：`domain/trace_projection.py`、`competition/output_contract.py`、`competition/adapter.py`、`competition/errors.py`、相关导出与 Contract/Unit 测试。
- 验收：
  - [x] `TraceProjection` 承载已投影 urls/actions/capture/screenshot（及可选 artifact_refs）。
  - [x] `OutputContractDraftMapper.map_draft` 轨迹字段只来自 `TraceProjection`；`mapped_status` 恒为 `None`。
  - [x] `NullCompetitionAdapter.map_status` 恒为 `None`；`map_output` 显式 PendingTemplate，不发明 OfficialOutput。
  - [x] 不读取/填充 `official_output_schema`；不猜测正式 status 枚举（P2/P6）。
  - [x] `output_contract.py` 不 import report/answer/adapters。
- 测试：`C` + Unit。
- 明确不做：TraceEnvelope event_type 投影表、StatusMappingPolicy 非空映射、正式 OutputMapper JSON/目录、EmergencyEmitter、修改 W0-012 serialize 语义。
- 验证证据：`pytest` 定向 51 passed（含 import boundaries + output contract + adapter/projection unit）；`ruff`/`mypy` 通过；`lint-imports` 10 kept。

### W0-014 — Worker 死亡 EmergencyEmitter

- 状态：完成
- Commit：`feat(supervisor): implement emergency emitter on worker death`
- 目标：Parent 仅凭 Snapshot、Trace、Evidence 生成合法内部输出。
- 对齐：§7.6、§18.4/§18.5（内部 EMIT 原子写）。
- 不变量：`INV-7`。
- 前置：W0-011、W0-013、DOC-004。
- 范围：`supervisor/emergency_emitter.py`、导出、Unit/Contract/Fault 测试。
- 验收：
  - [x] 仅读 Snapshot/Trace/Evidence；无 Browser/Model/adapters 依赖。
  - [x] `serialize` 强制 `WORKER_CRASHED`；`mapped_status` 恒为 `None`。
  - [x] 经窄 `StatusMapper.map_status`（不 import competition、不调用 `map_output`）。
  - [x] 原子写入 `emergency_emit/{draft,report,receipt}.json`。
  - [x] Fault：Worker 强制终止后 Parent emit 成功（POSIX SIGKILL；Windows terminate/kill）。
- 测试：`U/C/F`。
- 明确不做：Trace event_type 投影表、正式 `official_output/` 目录映射（W4-010）、BestCandidate 完整类型。
- 验证证据：定向 supervisor/emergency 相关 86 passed（2 skipped 平台无关）；ruff/mypy 通过；`lint-imports` 10 kept。
- 偏差/未验证项：为遵守分层契约，supervisor 不直接依赖 competition，改注入 `StatusMapper`；轨迹 URL/Action 仅来自 Snapshot 字段（不发明 event_type 表）；按 DOC-003 未自动提交。

### W0-015 — FakeBrowser 与 FakeModel

- 状态：完成
- Commit：`feat(harness): add fake browser and fake model adapters`
- 目标：为无密钥、无网站执行提供确定性 Fakes。
- 对齐：§25.1、§31 Week 0。
- 不变量：`INV-11`、`INV-13`。
- 前置：W0-005。
- 范围：`harness/cassette.py`、`harness/fake_browser.py`、`harness/fake_model.py`、导出与 Contract 测试。
- 验收：
  - [x] `FakeBrowser` / `FakeModel` 实现公开 `BrowserPort` / `ModelPort`。
  - [x] 默认空占位 Receipt 确定性可复现；不扩展 Port DTO 字段。
  - [x] cassette dump/load/`from_cassette` 回放响应序列一致。
  - [x] 脚本耗尽 fail-closed；Fake 不依赖 playwright/httpx/provider adapters。
- 测试：`C`。
- 明确不做：W0-016 运行闭环接线、W0-017 NullVision/NullMemory、§25.2 完整交互状态机、丰富 DOM/AX/Model schema。
- 验证证据：`pytest tests/contract/test_fake_browser_model.py` 与相关 contract 通过；ruff/mypy 通过；`lint-imports` 10 kept。
- 偏差/未验证项：按 DOC-003 未自动提交。

### W0-016 — Fake 最小运行闭环

- 状态：完成
- Commit：`feat(core): wire minimal runtime loop with fakes`
- 目标：贯通 Task → Runtime → Trace → Serializer → 内部运行目录。
- 对齐：§10、§19.1、§18.4、§31 Week 0。
- 不变量：`INV-3`、`INV-6`、`INV-7`。
- 前置：W0-014、W0-015。
- 范围：`domain/run_manifest.py`、`core/runtime.py`、导出与 Scenario 测试。
- 验收：
  - [x] 进程内短相位路径 `ANALYZE→…→EMIT`；Scenario 注入 FakeBrowser/FakeModel。
  - [x] Trace 相位事件 + 最小 `run_manifest.json` / `run.json` + `emit/` 草稿原子落盘。
  - [x] SERIALIZE 无 Browser/Model 副作用；`mapped_status is None`；轨迹 urls/actions 为空。
  - [x] core 不 import harness；无 API key / 真实网站即可完成 run。
- 测试：`S`。
- 明确不做：SpawnWorker 接线、完整 §10.3 agent 循环、正式 §27.1 RunManifest digests、Vision/Memory、SIGKILL 复测。
- 验证证据：`pytest tests/scenario/test_minimal_fake_run.py` 2 passed；ruff/mypy 通过；`lint-imports` 10 kept。
- 偏差/未验证项：`InternalRunManifest` 为内部最小清单，非正式 competition RunManifest；按 DOC-003 未自动提交。

### W0-017 — Output 与 Null Adapter Contract Suite

- 状态：完成
- Commit：`test(contract): add output contract and null adapter suite`
- 目标：覆盖 OutputContract、NullVision、NullMemory 与关闭可选能力。
- 对齐：§30.2。
- 不变量：`INV-11`。
- 前置：W0-013、W0-015、W0-016。
- 范围：`adapters/null_vision`、`adapters/null_memory`、import-linter、Contract 套件。
- 验收：
  - [x] `NullVision.available() is False`；`analyze` 抛 `VisionUnavailableError`。
  - [x] `NullMemory` recall/submit_run/health 空占位不崩溃。
  - [x] OutputContract draft 在可选能力关闭语境下仍可生成；`mapped_status is None`。
  - [x] MinimalRuntime + FakeBrowser/FakeModel 在 NullVision/NullMemory 关闭时仍能内部 emit。
- 测试：`C`。
- 明确不做：Vision/Memory 富字段、shadow/assist、将 Vision/Memory 接入 MinimalRuntime 主循环、W3-003 全量 off/shadow 等价。
- 验证证据：`pytest tests/contract/test_null_adapters_and_output.py` 6 passed；相关 import/boundaries 通过；ruff/mypy 通过；`lint-imports` 10 kept。
- 偏差/未验证项：按 DOC-003 未自动提交。

### W0-018 — Week 0 故障验收

- 状态：完成
- Commit：`test(fault): verify jsonl tail recovery and emergency emit`
- 目标：集中验证 SIGKILL、JSONL half-line 和无密钥 CI DoD。
- 对齐：§30.4、§31 Week 0 DoD。
- 不变量：`INV-6`、`INV-7`。
- 前置：W0-016、W0-017。
- 范围：`tests/fault/test_week0_fault_acceptance.py`（胶合 + CI DoD 门闩）；回归既有 kill/jsonl/CI 契约。
- 验收：
  - [x] 截断 Trace/Evidence 尾行后 `EmergencyEmitter.emit` 成功；`WORKER_CRASHED`；`mapped_status is None`；report 含 recovery warning count。
  - [x] 既有 `test_emergency_emit_on_kill` / Trace·Evidence half-line 用例仍绿。
  - [x] CI 契约绑定 `timeout-minutes: 10` 且无 secrets/provider keys。
- 测试：`F`。
- 明确不做：正式 Emergency 目录映射（W4-010）、MinimalRuntime↔SpawnWorker 杀进程闭环、§30.4 全量故障目录、改写 Emitter/Writer 语义。
- 验证证据：`pytest tests/fault/test_week0_fault_acceptance.py tests/fault/test_emergency_emit_on_kill.py tests/fault/test_trace_jsonl_recovery.py tests/fault/test_evidence_jsonl_recovery.py tests/unit/test_ci_contract.py` 21 passed；ruff/mypy/`lint-imports` 通过。
- 偏差/未验证项：GHA 墙钟小于 10 分钟证据待提交推送后补记；按 DOC-003 未自动提交。

---

## 9. Week 1 — Kimi 主路径最小纵向切片

范围只包含 scalar 与简单 list；DeepSeek 不进入本周产品路径。

### W1-001 — Playwright CDP Browser Adapter

- 状态：完成
- Commit：`feat(adapters): add playwright cdp browser adapter`
- 目标：通过官方 CDP URL 建立 Playwright BrowserPort 实现。
- 对齐：§9.1、§9.2、附录 A、§23.3、§23.4。
- 不变量：`INV-1`、`INV-9`。
- 前置：W0-018。
- 范围：`adapters/playwright_browser`（connector/policy/`PlaywrightCdpBrowser`）、`optional-dependencies.browser`、CI `.[dev,browser]`、recorded CDP Contract 套件。
- 验收：
  - [x] `PlaywrightCdpBrowser` 实现 `BrowserPort`；默认经 `connect_over_cdp` 建隔离 context。
  - [x] 受控 `goto(url)` 执行 scheme + 搜索引擎 denylist；`execute(NAVIGATE)` fail-closed（TypedAction 尚无 URL）。
  - [x] adapter 包无 httpx/requests/`urllib.request` 旁路；CI 安装 playwright 包但不跑 `playwright install` / 无 secrets。
- 测试：`C` recorded CDP。
- 明确不做：W1-002 九项 Probe、W1-003 AX/DOM、W1-004 click/type/scroll、W1-006/W1-012 完整 Gate、§9.4 全量清理、扩 TypedAction/Task 字段、MinimalRuntime 改接真实 Playwright。
- 验证证据：`pytest tests/contract/test_playwright_cdp_browser.py tests/contract/test_port_conformance.py tests/contract/test_import_boundaries.py tests/unit/test_ci_contract.py` 通过；全量 pytest / ruff / mypy / `lint-imports` 10 kept。
- 偏差/未验证项：Live CDP 留后续；按 DOC-003 未自动提交。

### W1-002 — Browser Capability Probe

- 状态：完成
- Commit：`feat(perceive): add browser capability probe`
- 目标：运行时探测 BrowserCapabilities 并显式表达降级。
- 对齐：§9.2。
- 不变量：`INV-1`。
- 前置：W1-001。
- 范围：`domain/capability_probe.py`、`adapters/playwright_browser/capability_probe.py`、`perceive/browser_capability_probe.py`、U/C 测试。
- 验收：
  - [x] 建会话后 adapter try/fail 探测九项并缓存诚实 `BrowserCapabilities`。
  - [x] `BrowserCapabilityProbe` 物化恰好九份 `CapabilityAvailabilityReceipt`；False 不抬升为 True。
  - [x] 无会话报告全 False（显式降级）；不扩 BrowserPort。
- 测试：`U/C`。
- 明确不做：§9.3 ContextStrategy 降级链、§9.4 全量清理、W1-003 AX/DOM、Live CDP CI、MinimalRuntime 改接真实 Playwright。
- 验证证据：`pytest tests/unit/perceive/test_browser_capability_probe.py tests/contract/test_capability_probe.py tests/contract/test_playwright_cdp_browser.py tests/contract/test_port_conformance.py tests/contract/test_import_boundaries.py` 通过；ruff/mypy/`lint-imports` 10 kept。
- 偏差/未验证项：按 DOC-003 未自动提交。

### W1-003 — AX 与最小 DOM 感知

- 状态：完成
- Commit：`feat(perceive): add ax snapshot and minimal dom extract`
- 目标：构建 AX + 最小 DOM 的 PageView。
- 对齐：§12.2、§12.6、§9.5、§12.3。
- 前置：W1-002。
- 范围：`domain/page_view.py`、`perceive/ax_snapshot.py`、`perceive/dom_extract.py`、`perceive/page_view.py`、Unit fixtures。
- 验收：
  - [x] PageView 含 page/frame 身份、epoch refs、interactive targets、protected state。
  - [x] AX 折叠包装节点并分配 `epoch:local_id`；DOM 补充 AX 缺口且不覆盖同名 AX target。
  - [x] 不扩 `ObservationReceipt` / BrowserPort；fixtures 驱动 Unit 验收。
- 测试：`U` fixtures。
- 明确不做：observe 接线、snapshot diff、STALE_REF、click/type/scroll、完整 §12.5 未定义嵌套类型、Live CDP。
- 验证证据：`pytest tests/unit/perceive/test_ax_snapshot.py tests/unit/perceive/test_dom_extract.py tests/unit/perceive/test_page_view.py` 及相关回归通过；ruff/mypy/`lint-imports` 10 kept。
- 偏差/未验证项：按 DOC-003 未自动提交。

### W1-004 — Click/Type/Scroll TypedAction

- 状态：完成
- Commit：`feat(act): implement typed action executor for click type scroll`
- 目标：执行三类最小 TypedAction 并产生 ActionReceipt。
- 对齐：§13.1、§13.3。
- 不变量：`INV-10`。
- 前置：W1-003。
- 范围：`domain` TypedAction/`RoleNameLocator`/`ScrollMode`/`ActionReceipt` 审计字段；`act/locator`+`TypedActionExecutor`；`playwright_browser/action_dispatch`；FakeBrowser 审计回填；U/S/C。
- 验收：
  - [x] click/type/scroll：PageView ref → role+name locator → `BrowserPort.execute` → 可审计 `ActionReceipt`（strategy/role/name/ref）。
  - [x] adapter 仅 Locator API（`get_by_role` / `click` / `fill` / `scroll_into_view_if_needed`）；无 locator → `MISSING_LOCATOR`；源码无 `evaluate`；无 httpx/requests 旁路。
  - [x] 非三件套 fail-closed；轻量 epoch `STALE_REF`；`extra="forbid"` 拒绝自由 CSS/XPath/JS 字段。
- 测试：`U/S/C`。
- 明确不做：W1-005 StepMeter、W1-006 Policy、完整 §12.3 STALE_REF、NAVIGATE TypedAction、Live CDP、observe 接线。
- 验证证据：`pytest tests/unit/act tests/scenario/test_typed_action_click_type_scroll.py tests/unit/domain/test_action.py tests/contract/test_playwright_cdp_browser.py` 通过；全量 pytest / ruff / mypy / `lint-imports` 10 kept。
- 偏差/未验证项：Live CDP 留后续；按 DOC-003 未自动提交。

### W1-005 — StepMeter 接入执行边界

- 状态：未开始
- Commit：`feat(core): integrate step meter with browser execute boundary`
- 目标：所有 Browser execute 结果统一经过 StepMeter。
- 对齐：§6.3、§11。
- 不变量：`INV-8`。
- 前置：W0-008、W1-004。
- 验收：多处计数被架构测试拒绝；正式计步保持 Pending。
- 测试：`U/C`。

### W1-006 — 模型外 Policy Gate

- 状态：未开始
- Commit：`feat(core): add policy gate for typed actions`
- 目标：在模型外校验 action、URL、selector 和 side-effect risk。
- 对齐：§10.4、§13、§23。
- 不变量：`INV-9`、`INV-10`。
- 前置：W1-004。
- 验收：模型不能修改 Budget、判 status、绕过 Policy 或提出自由代码。
- 测试：`U` 越权拒绝。

### W1-007 — Moonshot/Kimi Adapter

- 状态：未开始
- Commit：`feat(adapters): add moonshot kimi model adapter`
- 目标：实现 Kimi ModelPort 和结构化响应边界。
- 对齐：§20.1、§20.6。
- 不变量：`INV-12`、`INV-14`。
- 前置：W0-005。
- 验收：SDK 类型不泄漏；模型身份固定；Receipt 脱敏。
- 测试：`C` recorded responses；Live 可选。

### W1-008 — Kimi Primary Profile

- 状态：未开始
- Commit：`feat(config): add kimi primary profile and provider manifest`
- 目标：增加 `kimi_primary` 与 ScoringPathProviderManifest。
- 对齐：§20.4、§20.6、§28。
- 不变量：`INV-12`。
- 前置：W1-007。
- 验收：所有影响正式上下文的调用有 manifest 条目。
- 测试：`C` manifest completeness。

### W1-009 — Scalar/List TaskAnalyzer

- 状态：未开始
- Commit：`feat(answer): add task analyzer v1 for scalar and list`
- 目标：首动作前构建 scalar/list AnswerContract。
- 对齐：§14.1～§14.4。
- 前置：W1-007。
- 验收：识别字段、年份、单位、来源、集合语义；不得因已有答案降低要求。
- 测试：`U`。

### W1-010 — EvidenceAtom v1

- 状态：未开始
- Commit：`feat(answer): implement evidence atom v1 with source digest`
- 目标：实现带 source digest、locator 和 normalization version 的 EvidenceAtom。
- 对齐：§15.1～§15.3。
- 不变量：`INV-4`、`INV-6`。
- 前置：W1-009。
- 验收：无 Evidence 的字段不能进入 Candidate；追加事实不可原地覆盖。
- 测试：`U`。

### W1-011 — AnswerCandidate 与 V0/V1

- 状态：未开始
- Commit：`feat(answer): add answer candidate and v0 v1 verifiers`
- 目标：实现候选答案、结构校验和证据绑定校验。
- 对齐：§16.1、§16.2。
- 不变量：`INV-4`。
- 前置：W1-010。
- 验收：V0/V1 确定性、失败有 Receipt。
- 测试：`U`。

### W1-012 — NavigationGate/AnswerGate v1

- 状态：未开始
- Commit：`feat(answer): add navigation and answer gates v1`
- 目标：实现双 Gate 基础判定。
- 对齐：§17。
- 不变量：`INV-4`、`INV-5`。
- 前置：W1-011。
- 验收：任一 Gate 失败不得进入 `VERIFIED_SUCCESS`。
- 测试：`U` gate matrix。

### W1-013 — PREPARE 与 SERIALIZE 分离

- 状态：未开始
- Commit：`feat(answer): split prepare final state from serialize`
- 目标：分离最后允许副作用的 PREPARE 和纯 SERIALIZE。
- 对齐：§18。
- 不变量：`INV-3`、`INV-6`。
- 前置：W1-012。
- 验收：Serializer 无任何 Port 调用；PREPARE 不重复写操作。
- 测试：`U/C` spy。

### W1-014 — Kimi 最小 VisionReceipt

- 状态：未开始
- Commit：`feat(perceive): add kimi image compression and vision receipt`
- 目标：增加截图压缩、视觉请求和结构化 VisionReceipt。
- 对齐：§12.9、§20.5。
- 不变量：`INV-12`。
- 前置：W1-007。
- 验收：视觉只提供 grounding；最终答案仍绑定可审计 Evidence。
- 测试：`C` recorded vision。

### W1-015 — 单任务纵向流水线

- 状态：未开始
- Commit：`feat(core): wire perceive act answer finalize pipeline`
- 目标：贯通 Perceive/Plan/Guard/Act/Verify/Evidence/Gates/Finalize。
- 对齐：§10、§17、§18。
- 不变量：`INV-1`、`INV-3`、`INV-4`、`INV-6`、`INV-8`、`INV-10`。
- 前置：W1-005～W1-014。
- 验收：Fake 场景完整运行，状态转移和事件顺序符合 §10。
- 测试：`S`。

### W1-016 — Kimi Admission 降级诊断

- 状态：未开始
- Commit：`feat(supervisor): add kimi admission degradation diagnostic`
- 目标：Kimi 不可用时在任务 admission 产生明确诊断。
- 对齐：§20.8、§20.9、§29。
- 前置：W1-008。
- 验收：auth/unavailable 可区分 BLOCKING/DEGRADED；不启动错误任务。
- 测试：`U/C`。

### W1-017 — Scalar Scenario Regression

- 状态：未开始
- Commit：`test(scenario): add scalar page text regression`
- 目标：覆盖 scalar 页面文本最小案例。
- 对齐：§30.3 #1、附录 B.1。
- 不变量：`INV-4`、`INV-6`。
- 前置：W1-015。
- 验收：TaskAnalyzer、Evidence、V0/V1、PREPARE、SERIALIZE 全链可断言。
- 测试：`S`。

### W1-018 — Simple List Regression

- 状态：未开始
- Commit：`test(scenario): add simple list pagination regression`
- 目标：覆盖简单 list 与分页。
- 对齐：§30.3 #2。
- 不变量：`INV-4`。
- 前置：W1-015。
- 验收：分页动作、去重、字段 Evidence 和答案渲染可断言；暂不声称 complete set。
- 测试：`S`。

### W1-019 — Kimi Live Scalar/List

- 状态：未开始
- Commit：`test(live): verify kimi scalar and list e2e on real sites`
- 目标：用真实 CDP 与 Kimi 验证 scalar/list 闭环。
- 对齐：§21.2、§31 Week 1 DoD。
- 不变量：`INV-1`、`INV-4`、`INV-6`、`INV-8`、`INV-12`。
- 前置：W1-017、W1-018；需要 API key 与 CDP。
- 验收：两类各至少一题成功；至少一题使用截图 grounding；记录 RunManifest。
- 测试：`L`。

### W1-020 — SIGKILL 保留最后 Candidate

- 状态：未开始
- Commit：`test(fault): verify emergency emit retains last candidate after sigkill`
- 目标：Worker 被杀后 EmergencyEmitter 使用最后持久化 Candidate。
- 对齐：附录 B.1、§31 Week 1。
- 不变量：`INV-7`。
- 前置：W1-019。
- 验收：无 Worker/Browser/Model 仍产生合法内部输出和审计链。
- 测试：`F`。

---

## 10. Week 2 — 抽取、恢复与 DeepSeek 备选

### W2-001 — V2 与 FrozenStructuredAnswer

- 状态：未开始
- Commit：`feat(answer): add v2 verifier and frozen structured answer`
- 目标：实现确定性语义校验 V2 和不可变答案冻结。
- 对齐：§16.2、§16.7。
- 不变量：`INV-4`。
- 前置：W1-020。
- 验收：冻结后不可原地修改；每个字段保留 Evidence 绑定。
- 测试：`U`。

### W2-002 — StopProof

- 状态：未开始
- Commit：`feat(answer): implement stop proof bound to filter digest`
- 目标：实现与 filter digest、dedupe key、分页事实绑定的 StopProof。
- 对齐：§16.5。
- 不变量：`INV-5`。
- 前置：W2-001。
- 验收：“连续两次无新增”不能作为唯一证明；无 StopProof 不得成功。
- 测试：`U` proof matrix。

### W2-003 — Complete Set 漏项失败

- 状态：未开始
- Commit：`test(scenario): add complete set missing item must fail`
- 目标：证明 complete set 少一项必然 AnswerGate FAIL。
- 对齐：§30.3 #3、附录 B.2。
- 不变量：`INV-5`。
- 前置：W2-002。
- 验收：filter readback、stable dedupe、StopProof digest 和缺项失败均有断言。
- 测试：`S`。

### W2-004 — Form/Filter OperationReceipt

- 状态：未开始
- Commit：`feat(answer): add operation receipt for form filter state`
- 目标：记录表单筛选操作及最终读回状态。
- 对齐：§14.2、§30.3 #4。
- 前置：W2-001。
- 验收：答案使用的筛选条件必须由页面状态读回，不仅来自动作意图。
- 测试：`S`。

### W2-005 — 文档下载与表格提取

- 状态：未开始
- Commit：`feat(perceive): add document download and table extract`
- 目标：经 Playwright 下载 PDF 并提取文本/表格。
- 对齐：§12.8、附录 B.3。
- 不变量：`INV-1`、`INV-9`。
- 前置：W1-001。
- 验收：保存 original digest、page/table path；大小、页数、超时、宏和外链限制生效。
- 测试：`S/F`。

### W2-006 — Network Capture 双视图

- 状态：未开始
- Commit：`feat(perceive): add network capture raw and official projection`
- 目标：分离内部 `capture_raw.jsonl` 与正式 capture 投影。
- 对齐：§12.7。
- 不变量：`INV-6`、`INV-14`。
- 前置：W1-001。
- 验收：正式视图脱敏；禁止复制、补写或伪造网络里程碑。
- 测试：`U/C`。

### W2-007 — EffectPredicate 与 Stale Ref

- 状态：未开始
- Commit：`feat(act): add effect predicate set and stale ref validation`
- 目标：实现动作预期效果和 epoch-based ref 失效检测。
- 对齐：§12.4、§13.4～§13.6。
- 前置：W1-004。
- 验收：ANY/ALL 组合确定；旧 epoch ref 返回 `STALE_REF`。
- 测试：`U/S`。

### W2-008 — Recovery 状态机

- 状态：未开始
- Commit：`feat(act): implement recovery paths for interactive scenarios`
- 目标：实现定位、popup/frame、刷新、回退和稳定页恢复路径。
- 对齐：§13.6。
- 前置：W2-007。
- 验收：恢复动作仍受 Policy、Budget 和 StepMeter 管理。
- 测试：`S`。

### W2-009 — Domain-aware Scheduler

- 状态：未开始
- Commit：`feat(supervisor): add domain aware scheduler`
- 目标：实现同域并发限制、cooldown 和 backpressure。
- 对齐：§8。
- 前置：W0-009。
- 验收：默认同域并发 1；429/403/验证码可触发 cooldown。
- 测试：`S` fake clock。

### W2-010 — Interactive Scenario Harness

- 状态：未开始
- Commit：`feat(harness): add interactive scenario test harness`
- 目标：建立 `state + TypedAction → next state + Receipt` 测试引擎。
- 对齐：§25.2、§30.3。
- 前置：W2-008。
- 验收：可表达 locator、popup/frame、pagination、effect 和 reconciliation 分支。
- 测试：`C` harness self-test。

### W2-011 — DeepSeek V4 Fallback Adapter

- 状态：未开始
- Commit：`feat(adapters): add deepseek v4 fallback adapter`
- 目标：实现独立 DeepSeek ModelPort。
- 对齐：§20.6、§21.3。
- 不变量：`INV-12`、`INV-16`。
- 前置：W1-007。
- 验收：不导入 Moonshot Adapter；不接收 Kimi 私有状态。
- 测试：`C` recorded responses。

### W2-012 — ModelRouteReceipt 与 Circuit Breaker

- 状态：未开始
- Commit：`feat(core): add model route receipt and circuit breaker`
- 目标：实现 Provider health、route generation、checkpoint 与 RouteReceipt。
- 对齐：§20.4、§20.8、§20.9。
- 不变量：`INV-16`。
- 前置：W2-011。
- 验收：auth 立即 OPEN；429/5xx 窗口计数；切换追加 Receipt。
- 测试：`U/F`。

### W2-013 — DeepSeek 强制 NullVision

- 状态：未开始
- Commit：`feat(adapters): force null vision on deepseek fallback profile`
- 目标：Fallback Profile 显式绑定 NullVision。
- 对齐：§20.5、§20.6。
- 不变量：`INV-11`、`INV-16`。
- 前置：W2-011。
- 验收：视觉不可用返回明确 Unavailable；不得伪装 Kimi Vision。
- 测试：`C`。

### W2-014 — Browser Disconnect 与 Model Timeout

- 状态：未开始
- Commit：`test(fault): add browser disconnect and model timeout output`
- 目标：验证 CDP 断连和模型超时仍产生合法输出。
- 对齐：§30.4、§31 Week 2 DoD。
- 不变量：`INV-7`。
- 前置：W2-010。
- 验收：失败码、最后稳定页、Snapshot 和内部终态一致。
- 测试：`F`。

### W2-015 — 首次副作用前 Failover

- 状态：未开始
- Commit：`test(fault): add failover before first browser side effect`
- 目标：Kimi admission 失败时由 DeepSeek 安全接管。
- 对齐：§20.8、§21.6、§31 Week 2。
- 不变量：`INV-16`。
- 前置：W2-012、W2-013。
- 验收：切换发生在浏览器副作用前；RouteReceipt 完整。
- 测试：`F`。

### W2-016 — Checkpoint 后 Failover

- 状态：未开始
- Commit：`test(fault): add failover from persisted checkpoint without reasoning leak`
- 目标：从 Harness 权威状态重建 DeepSeek 上下文。
- 对齐：§20.8、§21.6、附录 C。
- 不变量：`INV-14`、`INV-16`。
- 前置：W2-015。
- 验收：不读取或传递 Kimi reasoning/conversation state；不重复已完成副作用。
- 测试：`F`。

### W2-017 — PDF Table Regression

- 状态：未开始
- Commit：`test(scenario): add document pdf table extraction regression`
- 目标：完成附录 B.3 文档案例。
- 对齐：§30.3 #5、附录 B.3。
- 不变量：`INV-1`、`INV-4`、`INV-11`。
- 前置：W2-005。
- 验收：下载来源、digest、page/table path、parser timeout 可审计；NullVision 可 best-effort。
- 测试：`S/F`。

### W2-018 — No-progress 与 Reconciliation

- 状态：未开始
- Commit：`test(scenario): add no progress loop and reconciliation cases`
- 目标：覆盖无进展循环和潜在写操作超时后的 reconciliation。
- 对齐：§13.5、§30.3 #9～#10。
- 不变量：`INV-10`。
- 前置：W2-008、W2-010。
- 验收：达到阈值后收敛或终止；POTENTIAL/CONFIRMED_WRITE 不盲重试。
- 测试：`S`。

---

## 11. Week 3 — 五类任务、视觉消融与主备演练

### W3-001 — Comparison 与 V3 独立性

- 状态：未开始
- Commit：`feat(answer): add comparison task support and v3 independence`
- 目标：支持 comparison contract，并建立 V3 独立会话边界。
- 对齐：§16.3、§16.4。
- 不变量：`INV-4`。
- 前置：W2-018。
- 验收：V3 不读取 Planner reasoning；比较字段均有独立 Evidence。
- 测试：`U/S`。

### W3-002 — Chart Data Ladder

- 状态：未开始
- Commit：`feat(perceive): add chart data ladder extraction`
- 目标：按底层 JSON、DOM、文档、视觉阶梯提取图表数据。
- 对齐：§12、§30.3 #6。
- 不变量：`INV-4`、`INV-9`。
- 前置：W2-006。
- 验收：优先机器可读事实；视觉结果标记 source kind。
- 测试：`S`。

### W3-003 — VisionPort 与 NullVision

- 状态：未开始
- Commit：`feat(ports): formalize vision port and null vision adapter`
- 目标：把 VisionPort 与 NullVision 提升为一等可替换边界。
- 对齐：§12.9、附录 A。
- 不变量：`INV-11`。
- 前置：W1-014。
- 验收：关闭 Vision 后主链可落盘；Unavailable 不被解释为空结果。
- 测试：`C` off/shadow。

### W3-004 — Kimi Text Ablation Profile

- 状态：未开始
- Commit：`feat(config): add kimi text ablation experiment profile`
- 目标：增加只关闭视觉、保持同 Provider 的消融 Profile。
- 对齐：§21.5。
- 不变量：`INV-11`。
- 前置：W3-003。
- 验收：除视觉输入外，固定 prompt、fixture、配置和模型身份。
- 测试：`U/C` profile digest。

### W3-005 — Passive Replay

- 状态：未开始
- Commit：`feat(harness): add passive replay with normalized deterministic traces`
- 目标：回放 Observation/Model Receipt，确定性验证 Contract/Evidence/Gate/Serializer/Policy。
- 对齐：§25.1、§30。
- 不变量：`INV-13`。
- 前置：W2-010。
- 验收：固定 seed/clock/IDs 后 normalized trace 一致；可定位 first divergent event。
- 测试：`C`。

### W3-006 — Live Paired Statistics

- 状态：未开始
- Commit：`feat(harness): add live paired run statistics harness`
- 目标：建立真实 Provider 配对运行和统计报告。
- 对齐：§21.4、§21.7、§26。
- 不变量：`INV-13`。
- 前置：W3-005。
- 验收：不要求 Live trace byte-equal；报告 wins/losses/ties、置信区间与失败分类。
- 测试：`L`。

### W3-007 — 五类任务 Regression Suite

- 状态：未开始
- Commit：`test(regression): add five task family scenario suite`
- 目标：scalar、list/complete-set、document、comparison、chart 各有永久回归。
- 对齐：§21.2、§30.3、§31 Week 3 DoD。
- 不变量：`INV-4`、`INV-5`。
- 前置：W3-001、W3-002。
- 验收：每类均断言 Evidence、Gate、Terminal 和 Trace Projection。
- 测试：`S`。

### W3-008 — Kimi Vision Causal Ablation

- 状态：未开始
- Commit：`test(experiment): run kimi visual ablation paired report`
- 目标：运行 `kimi_primary` 与 `kimi_text_ablation` 配对实验。
- 对齐：§21.5、§31 Week 3。
- 不变量：`INV-11`、`INV-13`。
- 前置：W3-004、W3-006。
- 验收：生成可信视觉消融报告，区分 helped/harmed/neutral。
- 测试：`L`。

### W3-009 — Primary/Fallback Coverage Matrix

- 状态：未开始
- Commit：`test(experiment): run primary vs fallback profile delta matrix`
- 目标：比较 Kimi Primary 与 DeepSeek Fallback 的 whole-profile 差异。
- 对齐：§21.4、§31 Week 3。
- 不变量：`INV-16`。
- 前置：W3-006。
- 验收：生成能力覆盖矩阵；明确不得把差值解释为纯视觉因果。
- 测试：`L`。

### W3-010 — Deterministic Failover Drills

- 状态：未开始
- Commit：`test(fault): add deterministic failover drill suite`
- 目标：实现 §21.6 六类确定性故障演练。
- 对齐：§21.6、§30.4。
- 不变量：`INV-7`、`INV-16`。
- 前置：W2-016。
- 验收：admission、429、checkpoint outage、vision-only fail、ambiguous call、双 Provider fail 全覆盖。
- 测试：`F`。

### W3-011 — V3 Gate Integration

- 状态：未开始
- Commit：`feat(answer): add v3 verifier integration`
- 目标：在高风险条件触发 V3，并把 Receipt 纳入 AnswerGate。
- 对齐：§16.3、§16.4、§17。
- 不变量：`INV-4`。
- 前置：W3-001。
- 验收：V3 非确定性结论与 V0～V2 分层保存；不能绕过 Evidence。
- 测试：`U/C` recorded judge。

### W3-012 — Eight Worker Stress

- 状态：未开始
- Commit：`test(load): run eight worker concurrency stress test`
- 目标：验证最多 8 Worker、同域限制、Provider 与磁盘 backpressure。
- 对齐：§8.1～§8.3、§31 Week 3。
- 前置：W3-007。
- 验收：无共享 Browser/Page/Ledger；报告 p50/p95、429 与资源压力。
- 测试：`L`。

### W3-013 — Single Failover Enforcement

- 状态：未开始
- Commit：`test(integration): verify single failover and route receipt completeness`
- 目标：强制一题最多一次主备切换并验证 RouteReceipt 完整率。
- 对齐：§20.8、§21.6、§31 Week 3 DoD。
- 不变量：`INV-16`。
- 前置：W3-010。
- 验收：第二次切换被拒绝；每次允许切换都有可追踪 Receipt。
- 测试：`F/C`。

---

## 12. Week 4 — 模板迁移、验证与冻结

标记 `⏸ PendingTemplate` 的步骤只有在官方模板发布并保存权威来源后才能开始。

### W4-001 — Evalset Split Manifests

- 状态：未开始
- Commit：`feat(harness): add development validation sealed split manifests`
- 目标：建立 development、validation、sealed 三分与不可变 manifest。
- 对齐：§24、§36。
- 不变量：`INV-15`。
- 前置：W3-013。
- 验收：corpus digest、split policy 和访问纪律可审计。
- 测试：`U/C`。

### W4-002 — Doctor Blocking/Degraded Checks

- 状态：未开始
- Commit：`feat(scripts): add doctor blocking and degraded checks`
- 目标：实现启动前能力、密钥、磁盘、Provider、CDP、配置和安全检查。
- 对齐：§29。
- 不变量：`INV-14`。
- 前置：W1-016。
- 验收：BLOCKING/DEGRADED/WARNING 分类确定；Kimi-only 无 DeepSeek 时明确 DEGRADED。
- 测试：`U/C`。

### W4-003 — Contract Reconciliation Workflow

- 状态：⏸ PendingTemplate
- Commit：`feat(scripts): add reconcile template workflow`
- 目标：实现正式模板获取、digest、差异分类和覆盖生成流程。
- 对齐：§2.4、§35。
- 不变量：`INV-2`。
- 前置：W3-013；正式模板可用。
- 验收：P8/P14 有权威输入；任何未决字段保持 Pending。
- 测试：`C`。

### W4-004 — Official CompetitionCapabilities

- 状态：⏸ PendingTemplate
- Commit：`feat(competition): fill official capabilities from template`
- 目标：只根据模板填充 P1～P5。
- 对齐：§6.1、§35。
- 不变量：`INV-2`、`INV-8`。
- 前置：W4-003。
- 验收：status、schema、step、download、wall clock 均可追溯到模板 digest。
- 测试：`U/C`。

### W4-005 — StatusMappingPolicy

- 状态：⏸ PendingTemplate
- Commit：`feat(competition): implement status mapping policy with template digest`
- 目标：把 InternalTerminalState 映射到正式 status。
- 对齐：§6.2。
- 不变量：`INV-2`。
- 前置：W4-004。
- 验收：映射只存在于 competition；每个内部终态有明确结果。
- 测试：`C` mapping matrix。

### W4-006 — Official Output Mapper

- 状态：⏸ PendingTemplate
- Commit：`feat(competition): implement official output mapper and schema tests`
- 目标：实现正式 JSON、目录和原子输出。
- 对齐：§6.4、§18.5、§19.5。
- 不变量：`INV-2`、`INV-3`、`INV-14`。
- 前置：W4-005。
- 验收：output_valid_rate 100%；Serializer 仍纯；secret scan 0 命中。
- 测试：`C/G`。

### W4-007 — OpenNavEval Scorer Snapshot

- 状态：未开始
- Commit：`feat(harness): add scorer compatibility test snapshot`
- 目标：快照当前开源评分器实际读取和选择行为。
- 对齐：§2.1、§19.4。
- 前置：W3-013。
- 验收：明确标注只代表 OpenNavEval，不升级为正式规则。
- 测试：`C`。

### W4-008 — Competition Contract Digest

- 状态：⏸ PendingTemplate
- Commit：`feat(competition): freeze competition contract digest`
- 目标：冻结已对齐正式契约 digest 并写入 RunManifest。
- 对齐：§2.4、§27.1、§30.5。
- 不变量：`INV-2`。
- 前置：W4-006。
- 验收：同一发布候选使用相同 digest；变更必须触发重新对齐。
- 测试：`U/G`。

### W4-009 — Official Scorer Compatibility

- 状态：⏸ PendingTemplate
- Commit：`test(contract): rerun scorer compatibility against official template`
- 目标：对正式模板复测 capture、截图、actions 和输出读取规则。
- 对齐：§19.5、§35。
- 前置：W4-008。
- 验收：正式行为与 OpenNavEval 快照分离记录。
- 测试：`C`。

### W4-010 — Emergency Official Directory

- 状态：⏸ PendingTemplate
- Commit：`feat(supervisor): adapt emergency emitter to official result directory`
- 目标：让 EmergencyEmitter 输出正式目录和 Schema。
- 对齐：§7.6、§31 Week 4 DoD。
- 不变量：`INV-7`。
- 前置：W4-006。
- 验收：Worker SIGKILL 后 official output 合法率 100%。
- 测试：`F/G`。

### W4-011 — Knowledge Experiment Gate

- 状态：未开始
- Commit：`feat(harness): add validation paired ab knowledge experiment gate`
- 目标：只通过 validation 配对 A/B 决定 Knowledge 是否进入正式配置。
- 对齐：§22、§24、§31 Week 4。
- 不变量：`INV-11`、`INV-15`。
- 前置：W4-001。
- 验收：无统计正收益或有明显负迁移则保持 off。
- 测试：`L`。

### W4-012 — Sealed Suite

- 状态：⏸ PendingTemplate
- Commit：`test(sealed): run sealed suite without feedback loop`
- 目标：运行 sealed 评测并禁止逐题结果反馈实现。
- 对齐：§24、§30.5、§36。
- 不变量：`INV-15`。
- 前置：W4-010。
- 验收：无 P0/P1；结果只用于发布判断；打开逐题结果即降级为 validation。
- 测试：`G`。

### W4-013 — Release Digest Bundle

- 状态：未开始
- Commit：`feat(release): add provider config prompt policy digest bundle`
- 目标：冻结 Provider、Config、Prompt、Policy、Route 与 Knowledge digest。
- 对齐：§20.4、§27.1、§30.5。
- 不变量：`INV-12`。
- 前置：W4-008。
- 验收：无 RunManifest 的结果不能参与版本比较；Provider Manifest 完整。
- 测试：`U/C`。

### W4-014 — Rollback 与 Submission Runbook

- 状态：⏸ PendingTemplate
- Commit：`chore(release): cut rollback tag and submission runbook`
- 目标：建立 smoke environment、可重复提交、rollback tag 和最终运行手册。
- 对齐：§30.5、§31 Week 4 DoD。
- 前置：W4-012、W4-013。
- 验收：所有 Release Gate 通过；正式输出 100% 合法；可从 tag 重建并回滚。
- 测试：`G`。

---

## 13. 架构不变量覆盖

- `INV-1` Playwright-only：W0-005 定义边界；W1-001 强制；W1-019/W2-005 Live 与文档路径验证。
- `INV-2` core 无正式 status：W0-002；W0-003/W4-004～W4-006 持续验证。
- `INV-3` SERIALIZE 无副作用：W0-012；W1-013；W4-006。
- `INV-4` Evidence 绑定：W1-010；W1-011；W2-001；五类 regression。
- `INV-5` Complete Set 需要 StopProof：W2-002、W2-003、W3-007。
- `INV-6` 追加事实投影：W0-004、W0-006、W0-012、W2-006。
- `INV-7` Worker 死亡仍输出：W0-014、W0-018、W1-020、W3-010、W4-010。
- `INV-8` StepMeter 唯一入口：W0-008、W1-005、W4-004。
- `INV-9` 不可信数据：W1-001、W1-006、W2-005、W3-002。
- `INV-10` Policy 在模型外：W1-004、W1-006、W2-018。
- `INV-11` Optional 可关闭：W0-015、W0-017、W2-013、W3-003、W4-011。
- `INV-12` Provider Manifest：W1-007、W1-008、W4-013。
- `INV-13` Replay 确定、Live 统计：W0-015、W3-005、W3-006。
- `INV-14` Secret/Reasoning 隔离：W0-007、W1-007、W2-006、W2-016、W4-002。
- `INV-15` Sealed 无反馈：W4-001、W4-011、W4-012。
- `INV-16` 安全 Failover：W2-011～W2-016、W3-010、W3-013。

所有 INV 均必须同时具备实现归属和至少一个自动化验证；Rules 只能辅助 Agent，不能替代测试与 CI。

## 14. 附录 B 最小案例覆盖

### B.1 Scalar

- 主步骤：W1-009～W1-020。
- 必须证明：TaskAnalyzer、source digest、locator、Evidence binding、V0/V1、PREPARE、纯 SERIALIZE、SIGKILL Candidate。

### B.2 Complete Set

- 主步骤：W2-002～W2-004。
- 必须证明：filter readback、stable dedupe、StopProof/filter digest、少一项 Gate FAIL、禁止渲染“等 N 项”。

### B.3 Document

- 主步骤：W2-005、W2-017。
- 必须证明：Playwright download、original digest、page/table path、parser timeout、NullVision best-effort、视觉 source kind。

## 15. Release Gate 映射

- `output_valid_rate = 100%`：W4-006。
- `emergency_emit_success_rate = 100%`：W0-018、W4-010。
- `secret leak = 0`：W0-007、W2-006、W4-002、W4-006。
- `unsupported_claim_rate` 达标：W3-007、W4-012。
- `false_success_rate` 达标：W2-003、W3-007、W4-012。
- sealed 无 P0/P1：W4-012。
- Provider Manifest 完整：W1-008、W4-013。
- Kimi Primary 五类闭环和 p95：W3-007、W3-012。
- deterministic failover 100%：W3-010、W3-013。
- RouteReceipt 完整率 100%：W3-013。
- Kimi-only 无 DeepSeek 时明确 DEGRADED：W4-002。
- competition contract digest 固定：W4-008。
- rollback tag 可用：W4-014。

## 16. 计划变更协议

只有以下情况可以修改本计划：

1. 架构文档正式升级。
2. 官方比赛模板发布并完成初步差异分析。
3. 当前步骤无法在单一绿色 commit 内完成。
4. 新证据证明依赖顺序或验收条件错误。

修改方式：

1. 停止当前实现，不提交 WIP。
2. 使用独立 commit：`docs(plan): <reason>`。
3. 记录被替代步骤、原因、新依赖和 INV 影响。
4. 已执行步骤不得删除；标记 `已替代` 并链接替代步骤。
5. 重新检查 INV、Week DoD、附录 B 和 Release Gate 覆盖。

## 17. 每周封盘检查

每周最后一个 commit 完成后：

- [ ] 本周所有非 Pending 步骤已完成。
- [ ] 本周 DoD 有可重复验证证据。
- [ ] import-linter、lint、type、Unit、Contract、Scenario、Fault 均按当前能力通过。
- [ ] RunManifest/Trace/Evidence/Artifacts 能解释失败。
- [ ] 没有把 Live 波动误判为 Replay 不确定性。
- [ ] 没有把历史架构或 OpenNavEval 偶然行为升级为正式规则。
- [ ] 下一周前置条件成立。

## 18. 最终完成定义

只有满足以下条件，执行计划才可标记完成：

- 88 个步骤均为 `完成`，或 PendingTemplate 步骤在权威记录中被正式取消/替代。
- `INV-1`～`INV-16` 均有持续自动化门禁。
- Week 0～4 DoD 全部有 commit 与验证证据。
- 附录 B 三个最小案例全部通过。
- §30.5 Release Gate 全部通过。
- 正式 Competition Contract digest 固定。
- sealed 无 P0/P1 且未发生反馈泄漏。
- rollback tag 和 submission runbook 可重复执行。
