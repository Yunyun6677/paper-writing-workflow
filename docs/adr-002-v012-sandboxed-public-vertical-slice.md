# ADR-002: v0.12 以受限本地后端完成首个公开数据纵向切片

- 状态：Accepted for development; not production-certified
- 日期：2026-09-18

## 背景

v0.11 已有持久状态、模型适配器、原生工具、EvidenceVerifier 与恢复机制，但缺少一条同时包含真实模型、真实公开数据、工具失败、自主修复、独立核验和最终报告的运行证据。当前开发机可用 Codex CLI 与 Python，但没有 Docker 和 TeX 引擎。

## 决策

1. 新增框架中立的 `SandboxBackend`，首个切片使用 `LocalRestrictedBackend`，同时实现 fail-closed 的 `DockerSandboxBackend` 接口。
2. 本地后端继续使用无 shell 的进程边界、工作目录约束、环境变量白名单、超时和 Windows Job Object；它不被描述为操作系统级网络或文件系统沙箱。
3. 使用公开 `mtcars` CSV，预先固定 URL 与 SHA-256；注入一个确定性的列名错误，要求真实 Codex-backed Empirical Agent 读取受控错误观察后修复代码。
4. Worker、分析 Reviewer、Writer、报告 Reviewer 分别运行；Reviewer 只接收制品与显式 verification inputs，不读取 Worker hidden reasoning。
5. Runtime 仍是 canonical state 的唯一修改者。模型只能提交结构化 observation/proposal。
6. 用 provenance graph 将报告数字反向连接至 Estimate、结果、ModelRun、代码和原始数据哈希。

## 结果

2026-09-18 的第二次真实运行完成了 `failed Python run -> autonomous repair -> successful run -> independent verification -> report -> report verification -> final audit`。第一次失败运行也被保留，并直接促成 verifier 输入契约与可恢复工具错误通道的修正。

该结果只证明这个公开描述性 OLS 切片在当前主机上可执行。由于 Docker 与 TeX 引擎缺失，以下能力仍未获生产认证：不可信代码的强隔离、强制断网、LaTeX 实际编译、因果识别与任意研究任务自主完成。

## 被拒绝的替代方案

- **把本地路径检查称为 sandbox**：无法提供操作系统级隔离，拒绝。
- **等待 Docker 后再做任何真实测试**：会延迟发现 Runtime/Verifier 合约缺陷，拒绝。
- **用 MockModelAdapter 代替真实模型作为发布证据**：只能验证控制流，不能证明真实模型工具循环，拒绝。
- **让模型直接写 ResearchState**：破坏 canonical state authority 与可审计性，拒绝。
