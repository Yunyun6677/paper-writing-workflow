# 四篇公开实证论文复现基准

> 运行日期：2026-09-14；仓库记录日期：2026-09-15
> 状态：4 组材料完整性通过，3 项指定数值目标干净通过，1 项完成但保留统计警告。

这项基准用于回答一个具体问题：Research OS 能否从合法公开来源取得论文与数据，保留来源和哈希，真实执行不同实证方法，并把“运行完成”“数值对齐”“方法认证”严格区分？

## 一、总体结果

| 指标 | 结果 | 含义 |
| --- | ---: | --- |
| 公开论文与数据组合 | 4/4 | 每篇均具有公开全文或机器可读全文，以及公开数据或复现包 |
| 输入和输出哈希验证 | 4/4 | 清单中的全文、数据、结果和回执均存在且 SHA-256 一致 |
| 执行回执状态匹配 | 4/4 | 每次运行均产生可解析回执，且状态与基准清单一致 |
| 干净通过的指定复现目标 | 3/4 | ADH、Card--Krueger、AJR 的指定表格结果达到预设容差 |
| 带警告完成 | 1/4 | Yang 等的表格与图已生成，但设计矩阵秩亏仍待专项诊断 |
| 全仓库自动化测试 | 124/124 | runtime、工具、证据验证、恢复、评测和历史 Skill 测试全部通过 |

这里不能把 `3/4` 解释成“论文结果只有 75% 准确”，也不能把 `4/4` 解释成“所有结论 100% 正确”。前者是四个预先限定复现案例中的干净通过比例；后者只表示纳入清单的文件和回执通过完整性验证。

## 二、逐篇成果与数值精度

### 1. Autor、Dorn 与 Hanson（2013）

- 论文：*The China Syndrome: Local Labor Market Effects of Import Competition in the United States*。
- 公开来源：[MIT 作者全文](https://economics.mit.edu/sites/default/files/publications/the%20china%20syndrome%202013.pdf)、[David Dorn 数据与代码档案](https://www.ddorn.net/data/Autor-Dorn-Hanson-ChinaSyndrome-FileArchive.zip)。
- 方法：加权 2SLS、shift-share 进口冲击、地区聚类推断。
- 复现目标：Table 3 第 1--6 列。
- 样本与聚类：六个规格均为 1,444 个观测、48 个聚类，与目标一致。
- Python 与原 Stata 结果的最大系数绝对差：`5.17e-13`。
- Python 与原 Stata 结果的最大标准误绝对差：`3.86e-9`。
- 与论文展示的四舍五入系数最大差：`0.000462`；标准误最大差：`0.000260`。
- 评估：**干净通过**。这表明系统能够处理作者复现包、2SLS、权重和聚类推断，并进行跨引擎数值核验。

### 2. Card 与 Krueger（1994）

- 论文：*Minimum Wages and Employment: A Case Study of the Fast-Food Industry in New Jersey and Pennsylvania*。
- 公开来源：[作者论文](https://davidcard.berkeley.edu/papers/min-wage-ff-nj.pdf)、[作者数据](https://davidcard.berkeley.edu/data_sets/njmin.zip)。
- 方法：双重差分与回归调整。
- 复现目标：Table 3 核心 DID、Table 4 第 1--5 列。
- 原始记录：410；唯一门店编号：409；明确记录重复门店记录 2 条；回归分析样本：357。
- 核心 DID：`2.753606`，论文表格对应四舍五入值为 `2.75`。
- 指定作者表格值的最大四舍五入绝对差：`0.004665`。
- 评估：**干净通过**。本轮重新连接作者服务器曾超时，因此使用此前从完全相同作者地址获得且哈希核验一致的本地副本；该事实已写入清单，没有静默替换来源。

### 3. Acemoglu、Johnson 与 Robinson（2001）

- 论文：*The Colonial Origins of Comparative Development: An Empirical Investigation*。
- 公开来源：[AEA 文章页](https://www.aeaweb.org/articles?id=10.1257%2Faer.91.5.1369)、[MIT 作者数据档案](https://economics.mit.edu/people/faculty/daron-acemoglu/data-archive)。
- 方法：跨国 2SLS 工具变量。
- 复现目标：Table 4 Panel A 第 1--2 列。
- 第 1 列：系数 `0.944279`，标准误 `0.156525`，样本量 64；对应论文展示值 `0.94 (0.16)`。
- 第 2 列：系数 `0.995704`，标准误 `0.221682`，样本量 64；对应论文展示值 `1.00 (0.22)`。
- 两列系数、标准误和样本量均通过预设四舍五入规则。
- 评估：**干净通过**。这验证了公开 Stata 数据读取和 IV/2SLS 数值重建；它不单独证明排除性约束成立。

### 4. Yang 等（2023）

- 论文：*Unraveling Controversies over Civic Honesty Measurement: A Large-Scale Experiment in China*。
- 公开来源：[PubMed Central 全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC10629568/)、[作者公开数据仓库](https://github.com/Science-replication-group/Unraveling_Controversies_over_Civic_Honesty_Measurement)，数据仓库固定到提交 `5d7c9eeba928ba101252f221d114f05d64f116fc`。
- 方法：现场实验、组间比较、协变量调整 OLS、HC1 稳健标准误和绘图。
- 复现目标：Table 1、Table 2 第 1--9 个模型和 Figure 1。
- 数据规模：实验样本 496，调查样本 2,310；五项结果文件均已生成并通过哈希校验。
- 代表性结果：邮件联系处理效应在三个规格中约为 `10.21`、`12.14`、`12.17`；总归还结果约为 `-9.59`、`-10.07`、`-10.28`。
- 诊断：运行时出现 `design matrix is rank-deficient` 警告。现有回执证明结果确实生成，但尚未形成独立的秩、共线性和变量编码诊断回执。
- 评估：**完成但有警告**。在完成专项诊断前，不计入干净通过，也不报告未经验证的“作者数值最大误差”。

## 三、这个基准展示的系统能力

1. **合法来源获取**：能够记录作者主页、期刊页、PubMed Central、公开 GitHub 和作者数据档案，并保留失败或超时路线。
2. **多格式输入**：已实际处理 PDF、BioC JSON、ZIP、文本数据和 Stata DTA；原始输入不被静默修改。
3. **多类实证方法**：覆盖 DID、回归调整、实验 OLS、HC1、IV/2SLS、shift-share、权重和聚类推断。
4. **数值证据链**：结果不仅出现在文字里，还能追溯到输入文件、执行脚本、CSV 结果、运行回执和 SHA-256。
5. **跨引擎核验**：ADH 案例已量化 Python--Stata 系数和标准误差异，而不是只比较显著性符号。
6. **失败诚实性**：服务器超时、未完成下载和秩亏警告都进入记录；运行结束不自动等于验证通过。
7. **防篡改复核**：`scripts/verify_public_replication_benchmark.py` 会重新计算文件哈希并读取真实回执；测试证明修改结果文件后基准会失败。
8. **隐私与许可边界**：论文 PDF、ZIP 和原始数据位于 Git 忽略的本地 `work/`，GitHub 只发布代码、清单、非原始数据回执和报告。

## 四、可复核入口

- 来源、文件和预期哈希：`tests/fixtures/public-replications/four-paper-benchmark.json`
- 聚合验证回执：`tests/receipts/v011-four-public-paper-benchmark.json`
- 统一验证器：`scripts/verify_public_replication_benchmark.py`
- AJR 指定表格执行器：`tests/fixtures/public-replications/ajr2001_table4.py`
- LaTeX 报告：`outputs/public-e2e-four-paper/report.tex`
- LaTeX 产物清单：`outputs/public-e2e-four-paper/manifest.json`

在本地已存在公开材料时，可运行：

```powershell
.\.venv-empirical\Scripts\python.exe scripts/verify_public_replication_benchmark.py `
  --manifest tests/fixtures/public-replications/four-paper-benchmark.json `
  --repository-root . `
  --output tests/receipts/v011-four-public-paper-benchmark.local.json
```

## 五、尚未覆盖的边界

- 四篇测试均为预先指定表格或图的复现，不是四篇论文全部附表、机制和稳健性结果的完整重跑。
- 数值对齐不能代替因果识别审查，特别是工具变量排除性约束、shift-share 识别假设和实验外部有效性。
- Yang 等案例仍需秩亏专项诊断；因此当前不能宣称四篇全部无警告通过。
- 当前机器缺少 XeLaTeX，`report.tex` 尚未在本机完成编译。
- 该基准尚未达到 v0.11 Definition of Done 规定的十篇论文综合项目门槛，因此 v0.11 仍是开发版本，不是生产认证版本。
