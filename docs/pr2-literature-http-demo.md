# PR-2：本机文献综述演示入口（2026-09-30）

这是一个**受控演示切片**，不是自动完成任意题目综述的认证版本。它复用 PR-1 的 LangChain Specialist Adapter 和现有 ResearchRuntime、五个 Skill、Tool Registry、独立 Reviewer、SQLite 状态与人工门控；未引入 LangGraph、向量库或 Redis。

```text
本机浏览器 → loopback HTTP（随机页面令牌） → ResearchRuntime / SQLite
                                                 ↓
                                   LangChain Specialist Adapter
                                                 ↓
                  Research Director → Literature → Reviewer → Writing → final gate
                                           ↓
                        PDF page tool / Crossref DOI lookup / artifact writer

研究者明确批准 → Zotero Cloud 客户端 → DOI 查重 → 条目 → PDF 附件 → 上传回执
```

## 启动

在 Windows PowerShell 中：

```powershell
cd D:\AI\Codex\paper-writing-workflow
.\.venv-empirical\Scripts\python.exe -m pip install -r requirements-langchain.txt
.\.venv-empirical\Scripts\python.exe scripts\serve_literature_demo.py --port 8765
```

打开 `http://127.0.0.1:8765/`。服务器只监听 loopback；终端进程必须保持运行。关闭进程不会删除 SQLite 状态、源 PDF、哈希、工具记录或 LaTeX 文件；重启服务后可查看项目并点击“运行 / 继续”。**这不是 Windows 开机自启服务，也不保证任意时刻的进程故障都能无人工干预恢复**。

模型配置通过启动服务的进程环境变量提供，不要在网页或聊天中粘贴密钥：

```powershell
$env:RESEARCH_OS_MODEL_BASE_URL = 'https://api.deepseek.com'
$env:RESEARCH_OS_MODEL_NAME = '<提供商控制台确认的准确模型 ID>'
$env:RESEARCH_OS_MODEL_API_KEY = '<密钥>'
```

示例 URL 只是 OpenAI-compatible API 接口位置；“DeepSeek v4.1 flash”的准确模型 ID、结构化输出和工具调用兼容性尚须用你的账户实测，不在代码中虚构或锁定。还需预先配置 `ZOTERO_USER_ID`（数字）和 `ZOTERO_API_KEY`（个人文库读写）。所有密钥仅留在环境变量，仓库和回执不保存密钥。默认禁止 LangSmith 云端 tracing。

## 使用边界

1. 创建公开文献项目，输入研究问题。
2. 上传你有权处理的、带 DOI 的全文 PDF；页面要求明确确认可将文本发送到所配置的模型。入口用 Crossref 比对 DOI/标题、核验 PDF 可读页和 SHA-256。标题检验是初筛，**不等于逐项核验题录或文中主张**。中文无 Crossref DOI 的文献目前不能走这个入口。
3. 点击“运行 / 继续”。系统先经过研究问题 gate，不能靠模型自己批准。文献专家只能通过许可工具读取已注册 PDF 的有页码文本；它不能直接写 Zotero。正式综述必须经过证据审查、LaTeX 写作、独立复核及最终人工 gate。缺少证据时应阻断，不可编造。
4. 如需归档，在页面读取现有 Zotero 分类，选中分类并填写理由，再明确批准全文上传。条目与 PDF 附件是分别确认的；上传中断会留下 `literature/zotero-receipts/` 中的阶段回执，不得把“题录已创建”称为“PDF 已上传”。重复 DOI 会暂停归档并交人工核对。Zotero 存储额度不足、权限不足或网络失败同样会保留未完成状态。

本地数据默认位于 `.runtime/literature-demo/`（被 Git 忽略）。项目源文件和 Zotero 私有记录不得提交到 Git。服务没有公网认证、TLS 或多用户隔离，**绝不可绑定到 `0.0.0.0` 或直接暴露公网**。当前前端为单用户本机演示，不是生产 Web 服务。

## 验证状态

- 已运行：本机 HTTP 令牌/项目持久化测试、假传输的 Zotero 条目及 PDF 三步上传协议测试、环境端点校验、全仓库回归测试；此外用现有凭证完成了 Zotero 云 API **只读**分类连通性检查（46 个分类，不公开名称）。
- 已实例化但未真实请求：OpenAI-compatible `ChatOpenAI` 模型对象。
- 未运行：用户指定的 DeepSeek 模型真实推理、真实 Zotero 写入、公开 10 篇文献到 LaTeX 综述的端到端过程。缺少模型密钥且没有用户指定的公开全文与 Zotero 目标分类，不将这些标为 tested。
- 未实现：自动主题检索和合法全文下载、中文无 DOI 导入、跨进程任务队列/Windows 服务、生产级 PDF 身份核验、LaTeX 编译认证、自动 Zotero 云端分类创建。

状态语义：`ResearchState` 是唯一科学控制状态；HTTP 和 LangChain 都不能直接完成任务。`ZoteroCloud` 是明确批准后的独立外部写入，不是 Literature Agent 可以暗中调用的工具。
