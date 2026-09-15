# v0.11 十篇公开论文综合发布基准

> 核验日期：2026-09-15
> 综合发布门：**通过，但保留 6 项边界警告**。

## 结果摘要

| 指标 | 结果 | 可作何种解释 |
| --- | ---: | --- |
| 公开论文全文、数据与执行组合 | 10/10 | 十篇均有本地可读全文、公开数据、真实派生结果和执行回执 |
| 文件与回执哈希验证 | 10/10 | 当前本地文件与固定清单一致 |
| 严格作者表格匹配 | 4/10 | ADH、Card--Krueger、AJR、Broockman 的预声明目标通过 |
| 版本容差内的作者数值匹配 | 2/10 | Cheng--Hoekstra、Lee--Moretti--Butler；差值完整保留 |
| 仅核心系数通过 | 2/10 | Kessler--Roth、Manacorda--Miguel--Vigorito；不认证缺失的推断信息 |
| 方法路径认证 | 1/10 | Thornton 精简数据只支持未调整随机激励对比，不冒充原表 |
| 完成但有统计警告 | 1/10 | Yang 等的设计矩阵秩亏诊断尚未关闭 |
| 综合发布门 | PASS | 达到十篇、至少四个严格匹配、运行时证据和完整性要求 |

综合门通过不等于十篇论文的所有表格、机制、稳健性和因果假设全部通过。本基准的认证对象是：公开来源与全文真实性、原始输入哈希、受限规格的真实执行、数值核验、失败显式记录，以及运行时的恢复和人工门合同。

## 六篇新增案例

### Thornton（2008）：随机激励

- DOI：`10.1257/aer.98.5.1829`。
- 全文：[作者公开 PDF](https://www.rebeccathornton.net/wp-content/uploads/2019/08/Thornton-AER2008.pdf)。
- 公开精简数据：2,834 个有效结果观测，119 个村庄。
- 未调整激励差异：`0.450552`；村庄聚类标准误：`0.022760`。
- 边界：精简数据缺少原 Table 4 的性别、地区、模拟距离等控制变量，因此这里只认证随机激励对比与执行链，不声称复现论文调整后系数 `0.431`。

### Broockman（2013）：现场实验与交互 DID

- DOI：`10.1111/ajps.12018`。
- 全文：[Yale 作者学位论文中的完整文章章节](https://politicalscience.yale.edu/sites/default/files/files/Broockman_David.pdf)。
- Table 2 column 1：样本 `5,593`；外地区邮件系数 `-0.274507`（SE `0.013154`）；与黑人议员交互项 `0.128078`（SE `0.051568`）。
- 原文展示值为 `-0.275 (0.013)` 与 `0.128 (0.052)`，全部按三位小数严格对齐。

### Cheng 与 Hoekstra（2013）：加权 TWFE

- DOI：`10.3368/jhr.48.3.821`。
- 全文：[NBER 公开工作论文](https://www.nber.org/system/files/working_papers/w18134/w18134.pdf)。
- 550 个州年观测、50 个州；人口加权、州与年份固定效应、州聚类。
- 系数 `0.075533`，聚类标准误 `0.034817`；原文核心列为 `0.0801 (0.0342)`。
- 系数绝对差 `0.004567`，标准误绝对差 `0.000617`，在预声明 `0.005` 容差内；不隐藏公开教学版与发表版之间的差异。

### Kessler 与 Roth（2014）：器官捐献 DID

- DOI：`10.3386/w20378`。
- 全文：[NBER 公开工作论文](https://www.nber.org/system/files/working_papers/w20378/w20378.pdf)。
- 162 个州季度观测、27 个州；州和季度固定效应下 California × Post 系数为 `-0.022459`，与原文 `-0.022` 对齐。
- 边界：三列精简数据缺少登记决策数量，无法恢复原文权重及 `0.007` 标准误，故只认证系数，不认证推断。

### Manacorda、Miguel 与 Vigorito（2011）：RD 约化式

- DOI：`10.1257/app.3.3.1`。
- 全文：[NBER 公开工作论文](https://www.nber.org/system/files/working_papers/w14702/w14702.pdf)。
- 政府支持的非合格组均值 `0.727771`，资格约化式系数 `0.118280`；原文为 `0.729` 与 `0.116`。
- 边界：精简数据为 1,948 条，而发表表格报告 1,938 条，并缺少原始分数聚类标识；仅认证均值和系数在 `0.005` 容差内。

### Lee、Moretti 与 Butler（2004）：近票选举 RD

- DOI：`10.1162/0033553041502153`。
- 全文：[Princeton 作者公开 PDF](https://www.princeton.edu/~davidlee/wp/voterspolicies.pdf)。
- 严格限制上一期民主党得票率在 48%--52%，得到与原文一致的 915 个观测。
- 下一期 ADA 评分差 `21.283875`（原文 `21.2`）；下一期民主党胜选概率差 `0.484329`（原文 `0.48`）。
- 两项均在预声明显示精度容差内；尚未把完整多项式 RD 和全部敏感性表纳入本轮目标。

## 已覆盖的实证能力

十篇组合实际覆盖随机实验、现场实验、线性概率模型、HC1、传统 DID、交互 DID、人口加权 TWFE、近票选举 RD、资格阈值 RD、跨国 IV/2SLS、shift-share IV、聚类推断和图表生成。方法名称只表示本轮确实执行了相应受限规格，不自动证明对应识别假设成立。

## 机器复核入口

- 十篇固定清单：`tests/fixtures/public-replications/ten-paper-release-gate.json`
- 六篇执行器：`tests/fixtures/public-replications/additional_six_public_papers.py`
- 综合发布门验证器：`scripts/verify_ten_paper_release_gate.py`
- 综合回执：`tests/receipts/v011-ten-paper-release-gate.json`
- 叙述性 LaTeX 报告：`outputs/public-e2e-ten-paper/report.tex`

公开论文和原始数据仍保留在 Git 忽略的本地 `work/`，仓库只发布代码、来源 URL、固定版本、哈希、非原始结果和审计回执。
