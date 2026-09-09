# ResearchState Schema Migration Strategy

## 原则

`research-state/1.0` 是运行控制平面，不取代已有专业事实 schema。迁移采用 **reference-only / copy-never**：读取旧文件、记录路径和 SHA-256、建立 artifact reference、写新的 state 与 migration receipt；绝不静默改写旧项目、原始数据、全文、模型结果或审计文件。

## 复用映射

| 既有 schema | ResearchState 中的位置 | 权威内容 |
| --- | --- | --- |
| `economics-paper-project/1.0` | 顶层 project/question/goal/paper type + artifact ref | 项目定义与人工批准 |
| `workflow-run/1.0` | literature state / evidence registry artifact ref | 候选、筛选、导入与来源 |
| `design-register/1.0` | artifact ref；DAG 的 design gate 读取 | estimand、识别设计和变更审批 |
| `evidence-card/1.0` | evidence registry artifact refs | 全文 claim、locator、方法与发现 |
| `engine-execution/1.0` | empirical state / tool run refs | 软件、退出状态和产物 hash |
| `numeric-claims/1.0` | empirical/manuscript audit refs | 正文数字到实际 artifact 的绑定 |
| `paper-audit/1.0` | audit state refs | 论文结构和防火墙检查 |

ResearchState 只保存这些对象的 `artifact_id/path/hash/schema_ref/status`，不复制其正文。这样可避免同一题录、数字或设计在两个 schema 中漂移。

## 版本规则

- schema 名称使用 `name/major.minor`；minor 只增加可选字段，major 才允许不兼容变更。
- 状态文件必须通过当前 schema 后才 transition；未知 major 版本立即阻塞。
- 每个 migration 生成 `migration-receipt.json`，列出 source path、source hash、迁移器版本、时间与保证。
- migration 创建新 run，不覆盖旧 run；`parent_run_id` 连接谱系。
- 旧 artifact 状态不自动推断为 complete。迁移后由 verifier 重新核对文件、hash 和必要的外部状态。

## 当前迁移命令

```powershell
python scripts/research_agent.py migrate `
  --project-dir projects/<project-id> `
  --run-root .runtime/research-runs
```

`.runtime/` 默认不进入 Git。迁移结果包含 `state.json`、`events.jsonl`、`checkpoints/` 和 `migration-receipt.json`。

## 后续 migration registry

下一 major 版本增加 `research_os/migration_registry.py`，每个迁移函数满足纯函数式输入、不可变 source、可重复 hash、dry-run diff 和反向兼容读取。删除字段必须先经历一个 major 版本的 deprecated 状态；涉及人工批准、证据或数值 lineage 的字段禁止自动降级。
