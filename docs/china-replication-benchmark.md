# 中国相关实证论文复现能力对比

更新日期：2026-09-07。这里的“完成”仅指列明范围内的计算结果，不代表整篇论文、识别策略或外部有效性已经被验证。

## 三篇主测试论文

| 论文 | 设计与软件 | 已完成 | 尚未完成 | 当前状态 |
| --- | --- | --- | --- | --- |
| Autor, Dorn & Hanson (2013), *The China Syndrome* | 贸易冲击、shift-share IV、加权 2SLS、聚类标准误；Python/Stata | 作者公开数据下载与哈希；Table 3 第1–6列；Python–Stata 系数和标准误比对；论文舍入核验 | 其余表图；对 shift-share 识别的现代诊断；R 实现 | 指定范围完成 |
| Yang et al. (2023), *Unraveling Controversies over Civic Honesty Measurement* | 中国现场实验与调查；固定效应 OLS、HC1、卡方检验；Python/Stata 16 | 数据读取；0/100 编码处理；Table 1；Table 2 第1–9列 Python/Stata 复现与一致性回执；Figure 1 PNG/SVG；论文关键数字核验 | 补充材料；跨国分析；多重检验与测量有效性审计 | 指定范围完成，整篇部分完成 |
| Wiebe (2020), *Does Meritocratic Promotion Explain China's Growth?* | 市长晋升；高维固定效应 LPM、条件 Logit、Ordered Logit、聚类标准误；Stata 16 | Table 1；单例组迭代删除；Table 2 LPM 第1–3列；样本量与系数核验；PNG/SVG 图 | 原始 Stata；标准误严格对齐；Logit/Ordered Logit；规格曲线和全部稳健性 | 部分完成，需要复核标准误 |

## 我们已经证明的能力

- 从 DTA/CSV 读取公开复制数据，不修改原始文件，并记录 SHA-256。
- 复现二元结果的组均值、标准差、Pearson 卡方检验和稳健 OLS。
- 复现加权 2SLS、固定效应和聚类标准误的指定结果。
- 发现并复现 `reghdfe` 的迭代单例组删除，使三列样本量精确匹配。
- 在没有桌面图形环境时使用 headless 后端，输出 PNG 和 SVG 并人工查看。
- 把“代码运行”“数值与论文一致”“识别策略成立”分成不同验收层。
- 对无法启动的外部软件保留授权交接，不把计划运行写成完成；获准后再更新真实状态。

## 仍需补齐的工作流能力

| 缺口 | 为什么重要 | 下一步验收任务 |
| --- | --- | --- |
| Stata 外部进程授权稳定性 | 原作者代码往往依赖特定 Stata/ado 版本 | 重新授权后运行两份作者档案，保存日志和完成标记 |
| 高维 FE 的自由度与聚类修正 | 点估计相同不保证标准误相同 | 逐项比较 Stata `reghdfe` 与 Python 的吸收自由度和小样本因子 |
| 条件 Logit 与 Ordered Logit | 官员晋升论文的 6 个核心模型尚未覆盖 | 在 Stata 先建立基准，再增加 Python/R 的数值证书 |
| 现代错位 DID | 乡村政策常见分期实施，普通 TWFE 可能有负权重问题 | 获取 He–Wang 村官数据后运行处理时点诊断、事件研究与现代 DID |
| RCT 审计 | 回归一致不等于随机化、失访和多重检验可靠 | 为公民诚信案例加入随机化平衡、缺失机制和多结果校正 |
| 自动表图对照 | 目前目标值仍需人工从论文登记 | 增加 exhibit registry：论文表/图—脚本—数据—输出一一对应 |
| 许可机器可读化 | “公开可下载”不等于允许再分发 | 在每个结果包记录许可证、再分发决定和来源提交版本 |

## 额外重要候选：农村基层治理

He 与 Wang（2017）*Do College Graduates Serving as Village Officials Help Rural China?* 的 AEA/openICPSR 复制包已经核验，包含村—年数据、主表、附录、图形和 wild bootstrap 代码。自动下载目前被 openICPSR 的浏览器/Cloudflare 验证拦截，状态是 `blocked`，不是“数据不存在”。

用户醒来后的最小交接：在已登录浏览器打开 DOI `10.3886/E113682V1`，下载整个项目或至少 `workfile_AEJ.dta` 与四个 `.do` 文件，放入项目的 `inputs/he-wang-cgvo/`。之后工作流可以测试 TWFE DID、事件研究、村级聚类、wild bootstrap，以及现代 DID 敏感性分析。
