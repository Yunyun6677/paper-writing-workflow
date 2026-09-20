# Research OS

**面向经济学、管理学、政治学与公共政策研究的 evidence-first Research Agent System。**

Research OS 不是“输入题目后自动生成一篇论文”的提示词集合。它把研究过程表示为可持久化的任务图和可核验的制品链，由 Research Director 调度真实模型、专业 Skill、确定性工具和独立 Reviewer，在明确权限与科研约束下推进研究。

项目最初是五个 academic skills；现在已经演化为具有状态、规划、执行、恢复、核验、溯源和人工门控的 Research Agent runtime。五个 Skill 仍然保留，但它们是领域操作规范，不是系统本身，也不能单独证明任务完成。

## 当前版本与阶段

- **稳定版本：v0.11.0**（2026-09-15）
- **当前开发阶段：v0.12 Production Runtime**
- **已经完成：v0.12 第一个真实公开数据纵向切片**
- **尚未发布：v0.12**
- **尚未达到：Autonomous Research Agent v1.0**

当前切片已经真实连通：

```text
ResearchRuntime
  → real Codex-backed Empirical Agent
  → restricted Python execution
  → injected failure
  → structured error observation
  → autonomous code repair and rerun
  → EvidenceVerifier
  → independent Reviewer
  → Writing Agent
  → report verification
  → final audit
```

公开测试中，Python 首次执行失败，Agent 自动修复后成功运行；报告数字可以反向追踪至估计量、结果文件、模型运行、代码和原始数据哈希。详细边界见 [v0.12 能力矩阵](docs/v0.12-capability-matrix.md) 和 [公开运行凭证](tests/receipts/v012-public-sandbox-vertical-slice.json)。

> 当前状态应理解为“可运行且可验证的 Research Agent kernel 正在升级为 Production Runtime”，而不是“已经可以无人监督完成任意论文”。

## 为什么需要 Research OS

普通论文 Agent 往往把检索、分析和写作放进一次模型对话，容易出现四类问题：

1. 模型说“完成了”，但没有真实运行或制品；
2. 引用、数字和结论无法追溯；
3. 失败后依赖聊天历史，不能可靠恢复；
4. 为了得到满意结果而无记录地改变样本、模型或统计口径。

Research OS 将模型视为提出行动和解释证据的执行者，而不是科学事实的最终裁决者。canonical state 只由 Runtime 修改；工具结果、artifact hash、verification receipt 和 human decision 共同决定任务能否进入下一阶段。

## 科研完整性原则

- 不虚构文献、全文、数据、代码执行和实证结果。
- “检索到题名”不等于“阅读全文”；metadata-only 文献不能支持全文 claim。
- “模型运行成功”不等于“识别成立”；因果语言必须通过 identification evidence。
- 数字必须来自实际生成、保存并通过哈希核验的模型产物。
- 不得根据显著性、系数大小或符号修改样本、带宽、控制变量、固定效应、标准误或异常值规则。
- 原始输入不可静默修改；失败结果、运行记录、revision history 和 provenance 必须保留。
- 不绕过登录、验证码、付费墙或数据访问权限。
- credential、受限数据、伦理审查、外部写入、投稿和最终发布保留 human gate。
- 模型 observation 不能直接修改 canonical `ResearchState`。

## 总体架构

```text
Human / CLI / API
        │
        ▼
Research Director ─────────────── Human Gates
        │                         credential / ethics / restricted data
        │                         external write / submission / release
        ▼
Bounded Planner
  typed dynamic Task DAG
  cycle / permission / budget / sensitivity validation
        │
        ├──────── Literature Agent ── literature/acquisition Skills
        ├──────── Empirical Agent ─── empirical Skill
        ├──────── Writing Agent ───── paper workflow Skill
        └──────── Reviewer Agent ──── artifact-only verification context
                        │
                        ▼
                Unified Tool Registry
        metadata │ PDF │ Python │ Stata │ R │ LaTeX │ Zotero │ Git
                        │
                        ▼
                   SandboxBackend
          LocalRestricted / future Docker production boundary
                        │
                        ▼
                   EvidenceVerifier
        citation │ full text │ numeric │ causal │ specification
                        │
                        ▼
ResearchState + Checkpoints + Event Trace + ScientificMemoryStore
                        │
                        ▼
Artifact Registry + Provenance Graph + Reproducible Output
```

运行循环：

```text
GOAL → LOAD STATE → PLAN → SELECT → EXECUTE → OBSERVE
     → VERIFY → CRITIQUE → UPDATE STATE → REPLAN / NEXT TASK
     → FINAL AUDIT → HUMAN RELEASE GATE
```

任务结果只能进入明确状态：

- `PASS`：满足 success contract，进入后续任务；
- `FAIL_TRANSIENT`：在预算内重试；
- `FAIL_STRATEGY`：产生经过校验的重规划建议；
- `BLOCKED`：证据或外部条件不足；
- `HIGH_RISK_DECISION`：暂停并请求人工判断；
- `GOAL_COMPLETE`：进入 final audit，而不是直接宣布完成。

每个任务都有依赖、允许的 Agent/Tool、最大尝试次数、超时、输出 schema、停止条件、成功契约和核验规则。全局 step/task/replan budget 防止无限循环。

## Agent、Skill 与 Tool 的边界

| 层 | 职责 | 能否证明完成 |
| --- | --- | --- |
| Research Director | 管理目标、任务 DAG、路由、预算、状态和人工门控 | 不能；必须等待制品与 verifier |
| Specialist Agent | 针对一个有判断空间的专业目标规划并调用工具 | 不能；只能提交 observation/proposal |
| Skill | 领域政策、SOP、约束和交接格式 | 不能；Skill 是操作规范 |
| Tool | 执行一个窄而明确的动作 | 只能证明该动作的执行结果 |
| Verifier | 重新核验 claim、artifact、hash、设计或数字 | 在声明范围内提供 verification receipt |
| Runtime | 唯一 canonical state transition authority | 依据契约决定任务状态 |

系统只保留少量 Specialist：

- **Literature Agent**：检索计划、全文获取、证据卡、引用 claim 与证据缺口；
- **Empirical Agent**：数据检查、代码生成、模型执行、诊断和结果制品；
- **Writing Agent**：只使用已批准 artifact 和 claim；
- **Reviewer/Verifier Agent**：读取 artifact-only context，独立检查科学契约。

Research Director 不把 Zotero、PDF parser、Python 或 Git 伪装成 Agent；这些能力属于 Tool。

## 五个领域 Skill

| Skill | 范围 | 主要输入 | 主要输出 |
| --- | --- | --- | --- |
| `social-science-literature-review` | 系统综述、证据地图、研究空白与创新判断 | 研究问题、范围、学科、语言、年份 | `main.tex`、证据矩阵、文献地图、`references.bib` |
| `cnki-literature-acquisition` | 合法知网/中文核心全文获取与归档 | 题名/主题、期刊、年份、Zotero 分类 | 核验全文、下载台账、Zotero 记录或人工交接 |
| `international-literature-acquisition` | DOI、OpenAlex、Unpaywall、出版社与机构库 | 题名/DOI、范围、来源偏好 | 题录核验、合法全文、版本/许可证/哈希 |
| `economics-empirical-analysis` | CSV/XLSX/DTA、Python/Stata/R、计量与复现 | 数据字典、观察单位、变量、模型、推断设定 | 代码、表图、`report.tex`、运行回执和结果包 |
| `economics-paper-workflow` | 论文设计、写作、审计、修订与投稿包 | 研究问题、论文类型、目标期刊、设计和数据边界 | LaTeX 论文树、design register、audit 和 revision log |

完整规则以各目录中的 `SKILL.md` 为准。跨阶段任务由 Runtime 调度 Skill；单阶段任务仍可直接使用相应 Skill。

## 已实现的系统能力

### 1. 持久状态与动态任务图

- 统一 `ResearchState`；
- typed dynamic DAG，而不是固定的“文献 → 实证 → 写作”直线；
- Reviewer 可合法触发补证据、稳健性或修订分支；
- File 与 SQLite 两种 `StateBackend`；
- checkpoint、pause、resume、reconstruct 和 recover；
- SQLite optimistic concurrency、run lock 和事件排序。

### 2. 真实模型执行

- framework-neutral `ModelAdapter`；
- deterministic `MockModelAdapter`；
- 可执行 `CodexCLIAdapter`；
- 可选 OpenAI Agents SDK adapter；
- 模型只能返回符合 `research-agent-observation.schema.json` 的 observation；
- Runtime 保持 provider-independent，不在 canonical schema 中引用 OpenAI 类型。

### 3. 有边界的工具执行

- hash-approved Python、Stata 和 R 脚本；
- page-addressable PDF extraction；
- read-only Git inspection；
- artifact write；
- citation/full-text/numeric/causal/specification verification；
- Crossref/OpenAlex/Unpaywall 题录接口；
- Zotero Desktop local read 与批准后的 collection write；
- LaTeX adapter 已实现，但本机没有 TeX 引擎，仍是 staged。

### 4. Sandbox 与错误恢复

- `SandboxBackend` 与 `LocalRestrictedBackend`；
- 工作目录、绝对路径、环境变量、进程超时和进程树控制；
- 普通代码错误可作为结构化 observation 返回 Agent 修复；
- PermissionError、安全边界和敏感数据错误不可被模型自行绕过；
- `DockerSandboxBackend` 已定义并 fail closed，但尚未完成真实容器认证。

### 5. Evidence verification

- Citation：题录身份、locator、原文内容与 claim entailment；
- Full text：禁止 metadata-only 状态冒充全文阅读；
- Numeric：核对 artifact、hash、value、model/sample/table ID；
- Causal：核对 estimand、design approval、identification 和 inference；
- Specification：比较冻结设计与实际执行，阻止无记录规格漂移；
- model-assisted 判断记录模型、输入哈希、输出、置信度和时间。

### 6. Scientific memory 与最小上下文

- JSON artifact 是可移植证据载体；
- SQLite `ScientificMemoryStore` 是索引和查询层；
- Project、Question、Decision、Claim、Evidence、Source、Artifact、Dataset、ModelRun、Task 和 Revision 实体；
- `ContextPacker` 按任务、角色、依赖、相关性、token budget 和安全策略选择上下文；
- Reviewer 看不到 producer hidden reasoning；Literature Agent 不接触无关受限数据。

### 7. Provenance 与可观测性

- artifact SHA-256、execution receipt 和 idempotency；
- 当前纵向切片已支持 `ManuscriptClaim → Estimate → Result → ModelRun → Code → RawDataset`；
- 本地 `traces.jsonl` 记录任务、模型、工具、制品哈希、耗时、token、错误和重试；
- 默认不记录 prompt、全文、数据行、密钥和私人研究内容；
- 第三方 tracing 默认关闭。

### 8. 测试与公开基准

- synthetic failure injection；
- 三类 E2E 项目；
- 十篇公开论文综合发布门；
- 公开数据真实 Codex vertical slice；
- 当前全仓 **135 个测试入口通过**。

公开纵向切片的核验值为 `N=32`、描述性 OLS 斜率 `-5.344471572722676`。该结果只认证一条受控执行链，不认证因果解释或任意生成代码。

## 当前没有实现或没有认证的能力

以下内容属于后续路线，不能从 README 推断为已完成：

- 从一句自然语言 idea 自动生成完整 typed `ResearchSpec`；
- Novelty、Feasibility、Data Availability、Identification 四个自动 gate；
- DataScout 自动发现、授权检查、下载和合并数据；
- SocialScienceExperimentTree 与 confirmatory/exploratory firewall；
- 全论文所有数字的完整 backward data chaining；
- 独立的多角色 Scientific Review Board；
- Docker 生产隔离和强制断网；
- 自动完成任意因果识别；
- 无人监管投稿、外部上传或 release；
- 高级计量方法的全面 estimator certification。

高级方法目前多数处于“设计准入已整合、估计器待认证”，包括 modern DID、event study、IV、RD、synthetic control、SDID、DML、复杂抽样、空间/网络模型和动态面板。详情见 [计量方法指南](docs/econometric-methods-guide.tex)。

## 接口划分

### A. Human interface

当前支持两种入口：

1. 在 Codex 中用自然语言提出单阶段任务，由根目录 `AGENTS.md` 路由到 Skill；
2. 对跨阶段、长周期任务提交 project manifest，启动 Research Runtime。

当前还不能只凭一句 idea 自动完成 ResearchSpec；这是 v0.13 Research Compiler 的目标。

### B. Command-line interface

主入口：

```powershell
python scripts/research_agent.py --help
```

| 命令 | 用途 |
| --- | --- |
| `init` | 从经过 schema 验证的 manifest 创建 run |
| `run` | 使用 manual 或 Codex adapter 推进任务 |
| `status` | 查看当前阶段、active/blocked task 和 human action |
| `pause` / `resume` | 显式暂停和恢复 |
| `reconstruct` | 新会话中从 state、event 和 artifact 重建现场 |
| `recover` | canonical state 损坏时从有效 checkpoint 恢复 |
| `verify` | 检查状态与 artifact integrity |
| `evaluate` | 生成运行和科研指标 |
| `observe` | 兼容外部/manual adapter 的结构化 observation |
| `decide` | 处理 human gate |

### C. Canonical state interface

- Python：`research_os.runtime.ResearchRuntime`
- Schema：`schemas/research-state.schema.json`
- Backend：`FileStateBackend` / `SQLiteStateBackend`
- 规则：只有 Runtime 可以提交 canonical state transition。

### D. Model interface

- Contract：`research_os.adapters.base.ModelAdapter`
- 方法：`run_agent()`、`resume_agent()`、`stream_events()`、`cancel()`、`usage()`
- 输出：`schemas/research-agent-observation.schema.json`
- 实现：Mock、Codex CLI、可选 OpenAI Agents SDK。

模型不能直接写 state、绕过 verifier 或扩张 tool permission。

### E. Planning interface

- Deterministic baseline：`default_graph()`；
- Adaptive interface：`PlanningAdapter`；
- Proposal：`schemas/task-graph-proposal.schema.json`；
- Merge 前检查：schema、cycle、role、tool permission、data sensitivity、task budget、human gate 和 final-audit dependency。

### F. Specialist interface

每个 Agent 配置位于 `config/agents/`，声明 identity、allowed skills、allowed tools、input/output contract、context policy 和 verifier relationship。

Specialist 输出 proposal/observation，不拥有 canonical state。

### G. Tool interface

统一清单位于 `config/tool-registry.json`。每个 Tool 声明：

- `name`、`description`；
- input/output schema；
- side effect 与 permission level；
- retry policy 与 timeout；
- credential requirement；
- data sensitivity；
- deterministic/nondeterministic；
- verifier 与 implementation status。

MCP 在有利于互操作时优先使用；Python、Stata、R 等本地引擎保留 native adapter。

### H. Sandbox interface

- Contract：`research_os.sandbox.SandboxBackend`
- Implementations：`LocalRestrictedBackend`、`DockerSandboxBackend`
- Receipt：`schemas/sandbox-execution.schema.json`

本地后端是开发期受限执行器，不是生产安全边界。Docker adapter 当前没有真实认证，不应通过修改状态字段宣称 available。

### I. Verification interface

- Implementation：`research_os.evidence_verifier.EvidenceVerifier`
- Receipt：`schemas/evidence-verification-receipt.schema.json`
- Analysis chain：`schemas/provenance-chain.schema.json`

Verifier 必须重新读取 artifact 和 hash；不能接受上游的 `passed=true` 作为事实证明。

### J. Artifact and memory interface

- 文件系统保存不可变输入、代码、结果、报告和 receipt；
- SQLite 保存索引、关系和控制状态；
- provenance graph 不替代原始 artifact；
- restricted raw rows、secret 和 credential 不进入 long-term memory。

## 快速开始

### 1. 克隆与环境

```powershell
git clone https://github.com/Yunyun6677/paper-writing-workflow.git
cd paper-writing-workflow
py -m venv .venv-empirical
.\.venv-empirical\Scripts\python.exe -m pip install -r skills/economics-empirical-analysis/requirements.txt
```

只进行文献工作时不需要安装 Stata 或 R。真实 LaTeX 构建需要 TeX Live 或 MiKTeX。

### 2. 运行全部测试

```powershell
.\.venv-empirical\Scripts\python.exe scripts/run_tests.py
```

### 3. 初始化长周期项目

```powershell
.\.venv-empirical\Scripts\python.exe scripts/research_agent.py init `
  --manifest path\to\project.json `
  --run-root .runtime\research-runs `
  --state-backend sqlite
```

### 4. 使用 Codex adapter 推进

```powershell
.\.venv-empirical\Scripts\python.exe scripts/research_agent.py run `
  --run-dir .runtime\research-runs\RUN_ID `
  --project-dir path\to\project `
  --model-adapter codex
```

只有在研究内容允许发送给外部模型时才使用 `--allow-external-model-content`。该参数不是对受限数据的自动授权。

### 5. 中断后恢复

```powershell
.\.venv-empirical\Scripts\python.exe scripts/research_agent.py reconstruct `
  --run-dir .runtime\research-runs\RUN_ID `
  --project-dir path\to\project

.\.venv-empirical\Scripts\python.exe scripts/research_agent.py resume `
  --run-dir .runtime\research-runs\RUN_ID `
  --project-dir path\to\project
```

### 6. 复现 v0.12 公开切片

```powershell
.\.venv-empirical\Scripts\python.exe scripts/run_v012_vertical_slice.py `
  --run-root work\my-v012-run
```

该命令需要可用的 Codex CLI。它会使用公开数据，不会把用户私人数据作为默认 benchmark。

## 典型用户请求

单阶段文献任务：

```text
请使用 social-science-literature-review skill。
研究问题：[填写]
学科、时间范围和语言：[填写]
不得虚构文献；只有核验全文可以支持实质性 claim。
输出 LaTeX 综述、证据矩阵、文献地图和 references.bib。
```

实证任务：

```text
请使用 economics-empirical-analysis skill。
研究问题：[填写]
数据与每行观察单位：[填写]
处理变量、结果变量、控制变量与推断方式：[填写]
保留原始数据，输出代码、运行回执、表图、report.tex 和 numeric claims。
任何规格修改必须记录原因，不得根据显著性选择结果。
```

跨阶段项目：

```text
请使用 Research OS runtime 管理这个项目。
目标：[填写]
当前可用文献、数据和权限：[填写]
数据敏感级别：[public/synthetic/personal/restricted/confidential]
需要保留的人工门控：[填写]
先建立 typed task graph；每个完成声明必须绑定 artifact 和 verification receipt。
```

更多面向非技术用户的示例见 [零基础使用指南](docs/beginner-guide-zh.md)。

## 仓库结构

```text
research_os/     Agent runtime、planner、adapters、tools、sandbox、verifier
config/          Agent、provider、observability 与 tool registry 配置
schemas/         canonical state、task、observation、receipt 与交接契约
skills/          五个领域 SOP 及其脚本和参考资料
scripts/         CLI、测试、迁移、Zotero 与 benchmark 入口
tests/           unit、E2E、fault injection、agent eval 和公开凭证
docs/            架构、ADR、能力矩阵、方法指南与版本路线
outputs/         可以公开的报告制品
projects/        本地私人研究项目，默认不提交
work/            下载、运行和复现工作区，默认不提交
```

严禁提交 API key、私人 Zotero 状态、受版权保护 PDF、受限数据或未经授权的 `projects/` 内容。

## 路线图

| 版本 | 目标 | 当前状态 |
| --- | --- | --- |
| v0.12 | Production Runtime：真实模型、sandbox、恢复、核验和长运行 | 第一个 vertical slice 已通过；Docker/LaTeX 等发布门未完成 |
| v0.13 | Research Compiler：IdeaCompiler、ResearchSpec、四个 validation gates | 尚未开始实现 |
| v0.14 | Scientific Experiment Manager：研究树、规格注册、证伪和稳健性循环 | 架构设计阶段 |
| v0.15 | Autonomous Manuscript：完整 data chaining、ClaimGraph、独立审稿和修改 | 架构设计阶段 |
| v1.0 | 公开 idea-to-paper benchmark 下的 Autonomous Research Agent | 长期目标 |

完整路线见 [v1 Roadmap](docs/v1-roadmap.md)，目标架构见 [v1 Autonomous Research Architecture](docs/v1-autonomous-research-architecture.md)，当前缺口见 [v0.12 Gap Analysis](docs/v0.12-gap-analysis.md)。

## 发布与能力声明规则

任何能力都必须区分：

```text
documented → implemented → tested → production-certified
```

新增 prompt、Agent 名称、空 adapter、mock test 或 README 描述都不能单独提升能力等级。每项能力必须回答：

> What real artifact proves this works?

版本历史见 [CHANGELOG](CHANGELOG.md)，v0.11 发布说明见 [docs/releases/v0.11.0.md](docs/releases/v0.11.0.md)。

## License 与贡献

贡献应保持 schema 向后兼容、补充 deterministic tests 与 failure tests，并在 capability matrix 中明确认证范围。涉及外部写入、受限数据或凭据的功能必须保留人工审批和最小权限原则。
