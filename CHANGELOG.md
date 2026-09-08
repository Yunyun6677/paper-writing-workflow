# Changelog

本项目从首个公开版本开始记录变更，版本号遵循 [Semantic Versioning](https://semver.org/)。日期采用 `YYYY-MM-DD`。

## [0.6.0] - 2026-09-08

### Added

- 根目录 `AGENTS.md`：Codex 打开仓库后可按自然语言请求路由四个 skill，并统一权限、证据与发布边界。
- 面向新手的四组完整提示词，明确每个 skill 的最小输入、执行范围和验收产物。
- LaTeX 输出规范及可编译中文报告模板。

### Changed

- README 重构为“能力—边界—安装—输入—调用—编译”的短路径。
- 文献综述的正式综述、创新点报告和实证分析报告以 UTF-8 LaTeX 为标准交付；JSON/CSV 继续作为机器交接格式。
- 实证执行器新增 `coefficients.tex`、`coefficients.pdf` 和 `results/report.tex`，保留原有 CSV/JSON/SVG 供审计。

### Verified

- 全部 16 项 Python 实证测试通过；新增 LaTeX 表格与报告进入哈希结果包。
- 新增和修改的 JSON Schema 均通过解析检查。当前机器没有 LaTeX 发行版，因此 `.tex` 的真实编译检查需在安装 TeX Live 或 MiKTeX 后完成。

## [0.5.0] - 2026-09-08

### Added

- `international-literature-acquisition` skill：以 DOI 为主键，通过 Crossref、OpenAlex 和可选的 Unpaywall 定位外文开放全文，并保留出版社/学校订阅浏览器交接。
- `fulltext-resolution/1.0` 数据契约和标准库实现的解析器，输出候选来源、开放状态、文献版本、许可证、下载状态、本地路径与 SHA-256。
- GitHub 组件评估和来源路由，覆盖 OpenAlex Official CLI、Unpaywall、Elsevier `elsapy`、Zotero Connector、`scholarly`、PaperQA2 与 `paperscraper`。

### Verified

- 使用 Autor、Dorn 与 Hanson（2013）的 DOI 完成联网测试：Crossref 和 OpenAlex 题录一致；出版社/机构库路线失败后，从 NBER 取得并验证 1.1 MB 的工作论文 PDF，全过程未记录密钥。
- OA 解析器的离线测试与 skill 结构校验通过。

### Security and access

- 不接入 Sci-Hub 或其他绕过付费墙、登录、验证码和技术保护措施的下载路线。
- Google Scholar 仅用于低频发现；ScienceDirect 全文限开放获取或用户已授权的机构订阅，浏览器凭据不进入脚本和日志。

## [0.4.1] - 2026-09-08

### Added

- Windows 下的“用户可见交接模式”：使用仅监听本机的调试端口和独立 Chrome 资料目录，让用户能够处理知网登录或可见拼图。
- 知网接入方案对比，明确 Chrome DevTools、Zotero translators 与人工下载/Jasminum 回退路线的用途和边界。

### Security and reliability

- 保持“专用浏览器配置、禁止 Cookie 导出、官方下载后独立校验、Zotero 附件复核”四层控制。
- 记录真实检索测试状态：人大机构访问与精确题名检索成功；遇到可见验证码时按协议暂停并交给用户处理。

## [0.4.0] - 2026-09-08

### Added

- `cnki-literature-acquisition` skill：通过独立 Chrome 配置完成知网结构化检索、官方 PDF/CAJ 下载、可见验证码交接和 Zotero 归档。
- `cnki-download-verification/1.0` 数据契约与下载校验工具，记录格式、文件大小、页数、标题相似度、SHA-256 和项目归档路径。
- 中文核心文献获取与七角色文献综述工作流的正式衔接。

### Security and provenance

- Chrome 调试限定在独立研究配置中，不连接日常浏览器配置，不导出 Cookie、密码、令牌或请求头。
- 固定使用经过验证的 Chrome DevTools MCP 版本，并关闭使用统计和 CrUX 性能数据。
- 实现思路参考 `cookjohn/cnki-skills`，新增本地全文真实性核验、获取台账、去重和 Zotero 附件复核。

## [0.3.0] - 2026-09-07

### Added

- 面向科研与代码零基础用户的中文使用指南，覆盖提示词、数据字典、方法选择、运行要求和结果阅读。
- Yang 等（2023）中国公民诚信论文的 Table 1、Table 2 第 1–9 列与 Figure 1 Python 重建。
- Wiebe（2020）中国官员晋升论文的 Table 1 与 Table 2 LPM 第 1–3 列 Python 重建。
- 三篇中国相关实证论文的完成/未完成能力矩阵，以及 He–Wang（2017）农村基层治理复制包的人类交接。
- 高维固定效应、迭代单例删除、跨软件聚类推断和无界面绘图的复现经验规范。

### Verified

- 公民诚信案例的 Table 1 和核心处理系数与论文显示值一致，9 个模型完成 Python–Stata 一致性核验。
- 官员晋升案例在复现 `reghdfe` 单例规则后，三列 N 精确匹配，点估计匹配论文三位小数。

### Known gaps

- 官员晋升案例的原始 Stata 执行仍待外部进程授权；状态明确保留为 pending。
- 官员晋升案例的聚类标准误尚未严格对齐，Logit、Ordered Logit 和规格曲线尚未执行。

## [0.2.0] - 2026-09-06

### Added

- R 4.6.1 批处理桥，支持环境自检、受约束的通用分析脚本、SVG/PNG 系数图、会话信息与结构化运行回执。
- 跨引擎 `engine-execution/1.0` schema，以及 Python、Stata、R 之间的结果一致性核验。
- Card 与 Krueger（1994）Table 3 核心 DID 和 Table 4 第 1–5 列的三引擎局部复现。
- 公开论文复现方法目录，区分“来源已核验”“等待访问审核”和“已经执行”。

### Verified

- 16 项核心实证测试和 4 项 R 桥测试通过。
- 三份 R 运行回执通过 JSON Schema 校验。
- Card–Krueger 五个模型的最大跨引擎系数差为 `1.21e-13`，最大标准误差为 `4.80e-14`。

### Security and distribution

- Card–Krueger 原始数据、论文 PDF、派生分析数据和调试运行继续保持本地，不在 GitHub 重新分发。
- 公开清单记录合法来源、文件哈希、执行范围和复现局限。

## [0.1.0] - 2026-09-06

首个公开版本。

### Added

- 七角色社会科学文献综述 skill：全文核验、证据卡、引用审计、文献地图与独立创新点报告。
- Zotero 本地读取、标准化导入和项目制分类工具，以及全文不可得时的人类交接规范。
- Python–Stata 实证分析 skill：CSV/XLSX/DTA 摄取、数据处理留痕、OLS/固定效应与稳健/聚类标准误。
- Stata 16 批处理桥、Python–Stata 一致性测试和结构化结果包。
- Autor、Dorn 与 Hanson（2013）Table 3 第 1–6 列的可公开复现代码、结果与哈希清单。
- 两组脱敏文献综述示例及机器可读 schema。

### Security and distribution

- 排除个人研究画像、Zotero 私人快照、API 凭据、本机路径、受限全文、原始数据和许可证不明确的第三方二进制材料。

[0.1.0]: https://github.com/Yunyun6677/paper-writing-workflow/releases/tag/v0.1.0
[0.2.0]: https://github.com/Yunyun6677/paper-writing-workflow/releases/tag/v0.2.0
[0.3.0]: https://github.com/Yunyun6677/paper-writing-workflow/releases/tag/v0.3.0
[0.4.0]: https://github.com/Yunyun6677/paper-writing-workflow/releases/tag/v0.4.0
[0.4.1]: https://github.com/Yunyun6677/paper-writing-workflow/releases/tag/v0.4.1
[0.5.0]: https://github.com/Yunyun6677/paper-writing-workflow/releases/tag/v0.5.0
[0.6.0]: https://github.com/Yunyun6677/paper-writing-workflow/releases/tag/v0.6.0
