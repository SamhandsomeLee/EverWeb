# EverWeb 文档中心

本目录保存 EverWeb 的架构基线、执行计划、历史设计与可视化材料。文档按“当前权威、执行控制、历史参考、生成物”分类；同一主题只有一份当前权威文档。

## 当前权威文档

- [EverWeb Harness 架构设计 v2.2（Kimi First）](./architecture/EverWeb_Architecture_v2.2_Kimi_First.md)
  - 当前可实施架构基线。
  - 定义 `INV-1`～`INV-16`、分层依赖、运行时生命周期、测试策略和 Week 0～4 路线。
  - 正式比赛模板相关内容仍属于待对齐契约。
- [EverWeb 架构对齐执行计划 v1.0](./execution/EverWeb_Execution_Plan_v1.0.md)
  - 将架构路线拆解为线性执行步骤。
  - 每个步骤严格对应一个可独立验证和回滚的 Git commit。

## 历史架构

以下文档只用于追溯决策，不作为新代码的实现依据：

- [EverWeb Harness 架构设计 v2.1](./archive/EverWeb_Architecture_v2.1_Reviewed.md)
- [EverWeb 架构方案 v2.0](./archive/WebRetriever_Challenge_Architecture_v2.0.md)
- [从 0 搭建参赛系统 v1.0](./archive/WebRetriever_Challenge_From_Zero_Architecture_and_Implementation_v1.0.md)

若历史文档与 v2.2 冲突，以 v2.2 为准。引用历史设计时必须明确标注版本和仅供参考。

## 架构图

- `diagrams/index.html`：v2.2 架构图入口。
- `diagrams/*.html`：交互式可视化。
- `diagrams/*.json`：图形源数据。

`diagrams/` 是可再生成的本地交付物，当前由 `.gitignore` 排除，不作为架构真相源。图与文字冲突时，以 v2.2 架构文档为准。

## 后续文档归类约定

新增文档按用途放置：

- `execution/`：实施计划、迁移计划和逐 commit 执行账本。
- `adr/`：新增或替代架构决策；不得静默改写已执行历史。
- `contracts/`：正式比赛模板、Contract Reconciliation 记录和 digest。
- `runbooks/`：提交、故障恢复、回滚和比赛运行手册。
- `reports/`：验证集 A/B、视觉消融、故障演练与发布报告。

不存在实际内容时不创建空目录。

## 维护规则

1. 架构变更先更新权威架构或新增 ADR，再修改执行计划和代码。
2. 执行步骤变化必须通过独立的 `docs(plan)` commit 记录。
3. 不在历史文档中反向修补当前结论。
4. 文档链接使用仓库相对路径。
5. 类名、枚举、配置字段、`INV-*` 和 commit 标题保留英文原文。
