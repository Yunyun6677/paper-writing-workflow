# Research OS：社会科学论文工作流

面向经济学、管理学和政治学研究的可审计工作流：获取并核验文献、归档 Zotero、撰写综述、处理数据，并用 Python、Stata、R 完成可复现实证分析。

**当前版本：v0.6.1（2026-09-08）**

**项目状态：可复用原型；不等同于无人监督的自动论文生成器。**

第一次使用可先阅读 [零基础使用指南](docs/beginner-guide-zh.md)；版本变化见 [CHANGELOG.md](CHANGELOG.md)。

## 核心原则

- 不虚构文献、全文、数据、代码运行或实证结果。
- “搜到题名”不等于“读过全文”；“模型运行成功”不等于“因果识别成立”。
- 原始输入保持不变；检索、清洗、建模、失败和人工决策均留痕。
- 最终论文、综述和分析报告以 UTF-8 LaTeX 交付；JSON/CSV 继续承担 agent 间的机器交接。
- 不绕过登录、付费墙、验证码或其他访问控制，不上传无授权的论文与受限数据。

## 四个 Skill

| Skill | 适合做什么 | 用户至少提供 | 主要输出 |
| --- | --- | --- | --- |
| `social-science-literature-review` | 系统综述、证据卡、文献地图、创新点 | 研究问题、范围、语言、时间范围、目标期刊或学科 | `main.tex`、`innovation-report.tex`、`references.bib`、证据矩阵与文献地图 |
| `cnki-literature-acquisition` | 知网与中文核心文献获取 | 主题/题名、期刊范围、年份、目标 Zotero 项目 | 核验全文、获取台账、Zotero 附件或人工交接 |
| `international-literature-acquisition` | DOI、Google Scholar、OpenAlex、Unpaywall、出版社全文 | 主题/题名/DOI、年份、来源偏好、目标 Zotero 项目 | 合法全文、版本与哈希、Zotero 附件或人工交接 |
| `economics-empirical-analysis` | CSV/XLSX/DTA 清洗，Python/Stata/R 分析与复现 | 研究问题、数据字典、观察单位、变量、模型和推断方式 | `report.tex`、LaTeX 表格、PDF/SVG 图、代码、结果包与运行回执 |

完整边界和执行规则以各目录中的 `SKILL.md` 为准。根目录 [AGENTS.md](AGENTS.md) 会在 Codex 打开本仓库后自动完成任务路由。

## 五分钟开始

### 1. 下载并打开项目

```powershell
git clone https://github.com/Yunyun6677/paper-writing-workflow.git
cd paper-writing-workflow
```

用 Codex 打开仓库根目录。你可以直接用自然语言描述任务，也可以明确写“使用 `skill-name`”。

### 2. 建立 Python 环境

```powershell
py -m venv .venv-empirical
./.venv-empirical/Scripts/python.exe -m pip install -r skills/economics-empirical-analysis/requirements.txt
./.venv-empirical/Scripts/python.exe skills/economics-empirical-analysis/scripts/empirical.py doctor
```

只做文献工作时，可以暂不安装 Stata 和 R。

### 3. 准备输入

- 文献任务：研究问题、概念同义词、时间范围、语言、来源和 Zotero 项目名。
- 数据任务：数据文件、每行代表什么、变量字典、缺失值编码、模型与标准误设定。
- 论文复现：论文全文、官方数据/代码来源、准备复现的具体表或图。

私人数据放在 `inputs/`；个人研究项目放在 `projects/`。二者默认不会上传 GitHub。

### 4. 调用 Skill

不需要执行特殊按钮。把下面对应提示词交给 Codex 即可。若任务同时涉及检索、Zotero 和实证分析，可以依次调用多个 skill；每一步通过 JSON/CSV schema 交接。

### 5. 编译成果

中文成果推荐 TeX Live 或 MiKTeX，并使用 XeLaTeX：

```powershell
xelatex main.tex
bibtex main
xelatex main.tex
xelatex main.tex
```

实证报告位于运行目录的 `results/report.tex`，进入该目录后执行 `xelatex report.tex`。详细规则见 [LaTeX 输出规范](docs/latex-output-standard.md)。

## 可直接复制的提示词

### A. 社会科学文献综述

```text
请使用 social-science-literature-review skill。
研究问题：[填写]
学科与目标期刊：[填写]
核心概念及同义词：[填写]
时间范围：[填写]
语言：中文/英文/两者
希望覆盖的理论、机制或争议：[填写]
Zotero 项目分类：[填写]

不得虚构文献。只有获得并阅读全文的论文才能支持实质性判断。
输出 main.tex、独立的 innovation-report.tex、references.bib、证据矩阵和一张文献地图；无法取得的重要全文必须明确交接。
```

### B. 中文全文与 Zotero

```text
请使用 cnki-literature-acquisition skill。
主题或论文题名：[填写]
期刊范围：[填写]
年份范围：[填写]
需要数量：[填写]
Zotero 项目分类：[填写]

使用我已有的合法知网/学校权限。逐篇核验题名、作者、期刊和年份；下载后检查文件真实性并导入 Zotero。遇到登录或验证码时让我处理；失败论文不得静默遗漏。
```

### C. 外文全文与 Zotero

```text
请使用 international-literature-acquisition skill。
主题、题名或 DOI：[填写]
时间范围：[填写]
来源偏好：OpenAlex、Unpaywall、Google Scholar、出版社、机构库
需要数量：[填写]
Zotero 项目分类：[填写]

先查重，再核验 DOI 和题录；优先开放版本，必要时使用我已授权的学校订阅浏览器。记录版本、来源、许可证和哈希。不要绕过付费墙；无法取得的核心论文生成明确交接。
```

### D. Python、Stata、R 实证分析

```text
请使用 economics-empirical-analysis skill。
研究问题：[填写]
数据文件：[填写路径或上传]
每行代表：[填写观察单位]
因变量：[变量名与含义]
核心解释变量：[变量名与含义]
控制变量：[填写]
固定效应：[填写]
标准误/聚类层级：[填写]
权重与缺失值编码：[填写]
希望使用：Python / Stata / R

先检查数据和识别条件，再执行模型；不要按显著性修改样本或设定。输出可重复代码、report.tex、LaTeX 表格、PDF/SVG 图、模型结果和机器可读运行回执。
```

如果方法尚未确定，请明确写：“先比较方法成立所需条件，只做诊断；得到我确认后再运行因果模型。”

## LaTeX 交付边界

最终给人阅读、修改或投稿的内容使用 LaTeX：

```text
outputs/<project>/
├─ main.tex 或 report.tex
├─ references.bib
├─ sections/*.tex
├─ tables/*.tex
├─ figures/*.{pdf,png}
└─ manifest.json
```

以下内容不应强行转换为 LaTeX：原始数据、CSV 系数表、JSON 证据卡、哈希清单、执行日志、Python/Stata/R 源代码。它们是复现和 agent 交接所需的原始证据；LaTeX 报告引用或概括它们。

## 软件与账号

- **Zotero**：本地读取需要 Zotero Desktop；自动分类需要个人库 API Key。密钥只放系统环境变量。
- **知网/出版社**：由用户在专用研究浏览器中登录并处理验证码，程序不读取密码或导出 Cookie。
- **OpenAlex/Unpaywall/Elsevier**：按提供方要求配置环境变量；是否能下载全文仍取决于开放许可或机构订阅。
- **Stata**：需要合法安装及 `STATA_EXE`；本项目不复制许可证。
- **R**：需要 `Rscript.exe`；额外包应使用项目级锁文件。

## 明确不做什么

- 不使用 Sci-Hub 或其他规避访问控制的来源。
- 不把摘要、搜索片段、预览页或 DOI 页面当作全文。
- 不把普通 OLS/固定效应自动描述为因果效应。
- 不根据显著性自动改变模型、样本、标准误或异常值规则。
- 不公开个人 Zotero 状态、受限全文、未经脱敏数据、API Key 或本机许可信息。
- 不保证所有论文都能自动取得；核心论文不可得时必须说明下一步。

## 项目结构

```text
skills/       四个工作流入口与执行脚本
schemas/      agent 间的机器可读契约
templates/    LaTeX 等可复用模板
scripts/      Zotero 与通用工具
docs/         新手指南和输出规范
examples/     可复制的请求示例
outputs/      可公开的脱敏成果
work/         默认不公开的运行与复现材料
projects/     默认不公开的个人研究项目
```

进一步说明见 [零基础使用指南](docs/beginner-guide-zh.md)、[贡献规范](CONTRIBUTING.md) 和 [安全说明](SECURITY.md)。

## 验证状态

- Python、Stata 16、R 4.6.1 的标准接口及跨引擎一致性测试已跑通。
- Autor–Dorn–Hanson、Card–Krueger 及两项中国相关论文已完成限定范围的公开复现。
- 知网官方全文下载、本地校验和 Zotero 附件归档已跑通。
- 外文 DOI → OpenAlex/Crossref → 合法 PDF 的真实下载测试已跑通。
- 实证执行器会生成 LaTeX 系数表、PDF 图和 `report.tex`；当前机器未安装 LaTeX，因此仍需在 TeX Live/MiKTeX 环境完成最终编译测试。

版本变更见 [CHANGELOG.md](CHANGELOG.md)。第三方论文、数据和软件继续适用各自许可；本仓库原创代码与文档使用 [MIT License](LICENSE)。
