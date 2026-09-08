# Social Science Paper-Writing Workflow

一套面向经济学、管理学与政治学研究的开放、可审计论文工作流。项目将文献检索与 Zotero 归档、结构化综述、文献地图、创新点发现，以及 Python–Stata–R 实证分析连接成统一的数据契约，方便不同 agent 和人工环节可靠交接。

**当前开发版本：v0.5.0（2026-09-08）**

> 当前状态：可复用原型。文献综述与实证分析两个 skill 已完成；Python、Stata 16 与 R 4.6.1 的标准接口和跨引擎一致性测试已跑通，四项真实论文的局部复现可供审计。云备份与更多因果推断设计仍在路线图中。历次变化见 [CHANGELOG.md](CHANGELOG.md)。

第一次使用、不会代码？从 [零基础使用指南](docs/beginner-guide-zh.md) 开始。它包含数据怎么交、方法怎么说、六组可直接复制的提示词，以及结果表应该怎样阅读。

## 能做什么

| 模块 | 已实现能力 | 主要产物 |
| --- | --- | --- |
| 文献综述 | 七角色专家协议、中英文检索、全文核验、证据卡、引文审计 | 综述、证据矩阵、核验书目 |
| 文献管理 | Zotero 本地读取、RIS/BibTeX 导入、项目制分类、获取失败交接 | 导入计划、获取台账、审计记录 |
| 中文核心获取 | 专用 Chrome 会话访问知网、结构化检索、官方下载、PDF/CAJ 校验 | 下载核验 JSON、本地全文、Zotero 附件 |
| 外文全文获取 | DOI 核验、OpenAlex/Unpaywall 开放全文解析、授权出版社下载、版本记录 | 全文解析 JSON、PDF、哈希与 Zotero 附件 |
| 研究设计 | 概念—机制—结果梳理、文献地图、独立创新点组合 | JSON/SVG 地图、创新卡 |
| 实证分析 | CSV/XLSX/DTA 摄取、清洗审计、OLS/固定效应、稳健或聚类标准误 | 结果表、图、报告、哈希清单 |
| Stata 协作 | Stata 16 独立批处理、完成标记、Python–Stata 数值比对 | `.do`、结果 CSV、执行回执 |
| R 协作 | R 独立批处理、任意分析脚本桥、SVG/PNG 绘图、环境记录 | `.R`、图形、会话信息、执行回执 |
| 论文复现 | 公开材料下载说明、原始结果追踪、三引擎复核 | 复现报告与可复现代码 |

## 工作流

```text
研究请求
   ├─→ 文献专家面板 → 题录核验 → 合法全文 → Zotero 项目库
   │                         ↓
   │             证据卡 → 文献地图 → 文献综述
   │                              └→ 独立创新点报告
   └─→ 实证请求 → 数据摄取 → Python / Stata / R → 一致性审计
                                          ↓
                                 可验证结果包 → 论文写作
```

各阶段不依赖自由文本“口头交接”，而使用 `schemas/` 和 skill 内的 JSON Schema。无法取得的重要全文会形成明确的人类交接项，不会被静默遗漏。

## 仓库结构

```text
.
├─ skills/
│  ├─ social-science-literature-review/  # 文献综述专家 skill
│  ├─ cnki-literature-acquisition/        # 知网检索、下载核验与 Zotero 归档
│  ├─ international-literature-acquisition/ # 外文 DOI、开放全文、授权下载与归档
│  └─ economics-empirical-analysis/       # Python–Stata–R 实证 skill
├─ schemas/                               # 跨模块数据契约
├─ scripts/                               # 通用工作流与 Zotero 工具
├─ config/                                # 可公开配置模板
├─ examples/                              # 请求示例
├─ outputs/                               # 已脱敏的示范成果
└─ work/replications/                     # 可公开的复现代码与核验结果
```

## 快速开始

### 1. 获取代码并建立 Python 环境

```powershell
git clone https://github.com/Yunyun6677/paper-writing-workflow.git
cd paper-writing-workflow
py -m venv .venv-empirical
./.venv-empirical/Scripts/python.exe -m pip install -r skills/economics-empirical-analysis/requirements.txt
./.venv-empirical/Scripts/python.exe skills/economics-empirical-analysis/scripts/empirical.py doctor
```

运行实证模块测试：

```powershell
./.venv-empirical/Scripts/python.exe skills/economics-empirical-analysis/scripts/test_empirical.py
./.venv-empirical/Scripts/python.exe skills/economics-empirical-analysis/scripts/test_r_bridge.py
```

### 2. 创建本地研究画像

复制 `config/research-profile.example.json` 为 `config/research-profile.json`，再按自己的领域和偏好修改。后者已被 Git 忽略，适合保存个人化配置；仍不要在其中保存密码或 API Key。

研究任务使用 `examples/research-request.example.json` 或对应 schema 新建，不要覆盖既有项目记录。

### 3. 连接 Zotero

- 本地只读：保持 Zotero Desktop 运行并启用本地 API。
- 自动写入：只在需要时设置 `ZOTERO_USER_ID` 与 `ZOTERO_API_KEY` 环境变量。
- API Key 仅保存在操作系统的环境变量或安全凭据库；不要粘贴到对话、配置文件、日志或 Git。
- 付费数据库使用你自己的合法机构访问。工作流不绕过登录、付费墙或技术保护措施。

### 4. 连接中国知网

知网模块使用独立的 Chrome 研究配置，不接管日常 Chrome 标签页，也不导出 Cookie。用户在独立窗口中自行完成学校/知网登录；程序只使用页面上正式提供的检索、导出与 PDF/CAJ 下载功能。下载后必须经过文件签名、页数、标题匹配和 SHA-256 核验，才能进入项目目录和 Zotero。

环境配置、权限边界与验证步骤见 [CNKI Chrome 配置](skills/cnki-literature-acquisition/references/chrome-setup.md)；与外部方案的取舍见 [知网接入方案对比](skills/cnki-literature-acquisition/references/integration-landscape.md)。实际检索时可直接提出：

> 在知网中检索 2020—2026 年《中国行政管理》发表的乡村治理研究，筛选与村民参与或基层组织相关的论文；将能合法获得的全文下载、核验并归档到当前研究项目和 Zotero，无法取得的生成明确交接。

### 5. 获取外文全文

外文模块先核验 DOI 和题录，再按“现有附件 → OpenAlex/Unpaywall 开放版本 → 出版社或机构库 → 学校订阅 → 人工交接”的顺序寻找全文。Google Scholar 只作为低频发现入口；程序不接入 Sci-Hub，也不绕过付费墙、登录或验证码。

```powershell
python skills/international-literature-acquisition/scripts/resolve_open_access.py `
  --doi "10.1257/aer.103.6.2121" `
  --output work/fulltext-resolution.json
```

添加 `--download-dir work/downloads` 后，程序只尝试下载明确标为开放获取、且响应内容通过 PDF 结构检查的候选。可把联系邮箱设置为 `UNPAYWALL_EMAIL`，把 OpenAlex 密钥设置为 `OPENALEX_API_KEY`；这些值只进入系统环境变量，不写入仓库或结果文件。ScienceDirect 订阅全文通过专用研究浏览器和用户已有的学校访问下载，随后归档到 Zotero。

方案取舍与操作边界见 [GitHub 组件评估](skills/international-literature-acquisition/references/github-landscape.md)、[来源路由](skills/international-literature-acquisition/references/source-routing.md) 和 [授权浏览器步骤](skills/international-literature-acquisition/references/browser-procedure.md)。

> 围绕“数字贸易与劳动力市场”检索 30 篇外文文献，核验 DOI；优先取得开放全文，必要时使用我已登录的人大图书馆出版社页面。把核验成功的 PDF 归档到当前研究项目和 Zotero，逐篇记录版本与来源，无法取得的核心文献生成明确交接。

### 6. 连接 Stata

Stata 是专有软件，本仓库不包含安装程序或许可证。将 `STATA_EXE` 指向已授权的 Windows 可执行文件，或在命令中传入 `--stata-exe`：

```powershell
$env:STATA_EXE = "C:/Program Files/Stata18/StataSE-64.exe"
./.venv-empirical/Scripts/python.exe skills/economics-empirical-analysis/scripts/stata_bridge.py --smoke --output work/stata-smoke
```

Stata 16 使用可审计的批处理桥；Stata 17 及以上可在重新通过一致性测试后评估官方 PyStata。

### 7. 连接 R 与生成图形

安装 R 后，将 `R_SCRIPT` 指向 `Rscript.exe`。R 桥支持环境自检、结构化分析脚本和标准系数图；所有任务使用新输出目录并生成 `engine-execution/1.0` 回执：

```powershell
$env:R_SCRIPT = "C:/Program Files/R/R-4.6.1/bin/Rscript.exe"
./.venv-empirical/Scripts/python.exe skills/economics-empirical-analysis/scripts/r_bridge.py --smoke --output work/r-smoke
./.venv-empirical/Scripts/python.exe skills/economics-empirical-analysis/scripts/r_bridge.py --plot --input PATH_TO/coefficients.csv --output work/r-plot
```

任意 R 分析脚本还可通过 `--analysis --input ... --analysis-script ... --output ...` 运行。脚本必须写入完成标记、会话信息和至少一个 CSV/JSON 结果，桥接层负责日志、哈希与失败留痕。

## 已验证复现案例

项目现有两个真实数据案例：

1. Autor、Dorn 与 Hanson（2013）*The China Syndrome* 的 Table 3 第 1–6 列。Python 与 Stata 的最大系数绝对差为 `5.17e-13`，最大标准误绝对差为 `3.86e-09`，并与作者公布的舍入结果一致。

- [复现报告](work/replications/adh2013-china-syndrome/REPORT.md)
- [Stata 代码](work/replications/adh2013-china-syndrome/run/stata/replicate_table3.do)
- [Python 代码](work/replications/adh2013-china-syndrome/run/python/replicate_table3.py)
- [公开结果清单](work/replications/adh2013-china-syndrome/replication_bundle.public.json)

2. Card 与 Krueger（1994）*Minimum Wages and Employment* 的 Table 3 核心 DID 与 Table 4 第 1–5 列。Python、Stata 16 与 R 4.6.1 的最大跨引擎差低于 `1.21e-13`，并生成了 R 系数图。

- [复现报告](work/replications/card-krueger-1994/REPORT.md)
- [Python、Stata 与 R 代码](work/replications/card-krueger-1994/run/)
- [三引擎一致性回执](work/replications/card-krueger-1994/run/parity-v2.json)
- [公开结果清单](work/replications/card-krueger-1994/replication_bundle.public.json)
- [可继续执行的方法目录](skills/economics-empirical-analysis/references/replication-catalog.md)

3. 两项新增中国案例：Yang 等（2023）中国公民诚信现场实验已完成 Table 1、Figure 1 的 Python 重建，以及 Table 2 第 1–9 列的 Python–Stata 一致性核验；Wiebe（2020）中国官员晋升研究已完成 Table 1 与 Table 2 LPM 第 1–3 列，并发现、修复了高维固定效应单例样本差异。

- [中国相关三论文能力对比](docs/china-replication-benchmark.md)
- [机器可读对比结果](outputs/replication-benchmark/china-cases.json)
- [公民诚信案例报告](work/replications/civic-honesty-china/REPORT.md)
- [官员晋升案例报告](work/replications/meritocratic-promotion-china/REPORT.md)

论文 PDF、作者原始数据及压缩包没有在本仓库重新分发。公开结果清单保存来源 URL 和 SHA-256；下载作者材料后，可将数据路径显式传给脚本。每个案例只声称复现指定表格，不把数值一致误写为对识别假设的独立验证。

## 示例成果

- `outputs/v2/`：贸易开放与农村基层政治参与综述、文献地图及独立创新点报告。
- `outputs/ai-token-economics/`：人工智能经济学综述、证据卡、文献地图与研究入口。
- `outputs/literature-workflow-contract-v1.md`：文献模块的交接约定。

这些成果用于展示工作流结构，不替代研究者对原文、数据、识别策略和引用的再次核查。

## 数据、隐私与版权

- 不提交 API Key、账户、许可证序列号、个人 Zotero 快照或本机绝对路径。
- 不提交用户原始数据、受限全文或许可证不明确的第三方材料。
- 原始数据默认不可变；所有转换、筛选、合并和缺失值处理必须留痕。
- Zotero 云端同步成功与本地归档成功分别记录。
- 对无法合法自动取得的核心文献，记录题录、失败原因和用户下一步操作。
- 自动分析不以“得到显著结果”为优化目标，也不自动把相关性解释为因果性。

提交前请运行测试，并检查暂存文件中是否存在凭据、私人数据和大文件。更完整的协作规则见 [CONTRIBUTING.md](CONTRIBUTING.md)，安全问题见 [SECURITY.md](SECURITY.md)。

## 路线图

- 增加现代 DID、IV、RD、面板与调查抽样设计的独立审计门。
- 为 OSF、Zenodo 或机构存储增加显式授权的加密备份适配器。
- 增加可移植的项目初始化器、持续集成和跨版本 Stata 证书。
- 把 Zotero 获取台账、实证结果包和写作引用进一步统一为端到端项目 manifest。

## 版本规则

项目使用语义化版本：破坏兼容性的契约变更提升主版本，向后兼容的新功能提升次版本，修复与文档调整提升补丁版本。每个公开版本同时保留 Git tag、GitHub Release、发布日期和变更记录；日常开发以 `main` 分支最新提交为准。

## 致谢与许可

文献工作流的早期设计参考了 [fakerqwq/social-science-paper-writing-skill](https://github.com/fakerqwq/social-science-paper-writing-skill) 的模块化思路，并根据可核验全文、Zotero 项目制归档、七角色协议、强制文献地图和实证复现需求重新设计；没有照搬其内容。

知网模块参考了 [cookjohn/cnki-skills](https://github.com/cookjohn/cnki-skills) 通过 Chrome DevTools 进行直接导航、DOM 结构化提取与可见验证码检测的思路；本项目增加了专用浏览器配置、禁止 Cookie 导出、下载字节校验、项目台账和 Zotero 附件复核。

本仓库原创代码与文档采用 [MIT License](LICENSE)。第三方论文、数据和软件继续适用各自许可。
