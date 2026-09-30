"""Loopback-only, restartable HTTP entry point for a bounded literature demo.

The HTTP layer never changes task status itself. ResearchRuntime owns task
transitions; model observations remain proposals, and Zotero writes require a
separate recorded user action.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .adapters.langchain import LangChainSpecialistAdapter
from .executor import AgentExecutor
from .external_tools import _normalize_doi
from .runtime import ResearchRuntime
from .state_backends import open_state_backend
from .store import sha256_file
from .zotero_cloud import ZoteroCloud


_PROJECT = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_MAX_BODY = 15_000_000


def _crossref(doi: str) -> dict[str, Any]:
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    request = urllib.request.Request(url, headers={"Accept": "application/json",
                                                  "User-Agent": "ResearchOS-literature-demo/0.1"})
    with urllib.request.urlopen(request, timeout=25) as response:
        message = json.load(response)["message"]
    if _normalize_doi(message["DOI"]) != doi:
        raise ValueError("Crossref DOI identity mismatch")
    date = message.get("published-print") or message.get("published-online") or {}
    year = (date.get("date-parts") or [[""]])[0][0]
    return {"doi": doi, "title": (message.get("title") or [""])[0],
            "authors": [" ".join(filter(None, (person.get("given"), person.get("family"))))
                        for person in message.get("author", [])],
            "journal": (message.get("container-title") or [""])[0],
            "year": year, "url": message.get("URL", ""), "source": "Crossref"}


def _check_pdf(data: bytes, title: str) -> dict[str, Any]:
    if not data.startswith(b"%PDF-") or len(data) > _MAX_BODY:
        raise ValueError("Upload must be a PDF no larger than 15 MB")
    from io import BytesIO
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(data), strict=True)
    page_count = len(reader.pages)
    text = " ".join((page.extract_text() or "") for page in reader.pages)
    if page_count < 2 or len(text.strip()) < 1000:
        raise ValueError("PDF has insufficient readable full text; manual handoff required")
    normalized = re.sub(r"[^\w\u4e00-\u9fff]", "", text[:20000].lower())
    title_words = re.findall(r"[a-z0-9]{4,}|[\u4e00-\u9fff]{2,}", title.lower())
    if not title_words or sum(word in normalized for word in title_words) / len(title_words) < 0.6:
        raise ValueError("PDF title cannot be matched to Crossref; manual identity check required")
    return {"page_count": page_count, "text_chars": len(text), "title_match": True}


class DemoService:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.Lock] = {}
        self._jobs: dict[str, threading.Thread] = {}
        self._job_errors: dict[str, str] = {}
        self.token = secrets.token_urlsafe(32)

    def _paths(self, project_id: str) -> tuple[Path, Path]:
        if not _PROJECT.fullmatch(project_id):
            raise ValueError("Invalid project id")
        project = self.root / "projects" / project_id
        run_parent = self.root / "runs" / project_id
        return project, run_parent

    def _run_dir(self, project_id: str) -> Path:
        _, parent = self._paths(project_id)
        runs = [path for path in parent.iterdir() if path.is_dir()] if parent.is_dir() else []
        if len(runs) != 1:
            raise ValueError("Project must have exactly one demo run")
        return runs[0]

    def _runtime(self, project_id: str) -> ResearchRuntime:
        project, _ = self._paths(project_id)
        adapter = LangChainSpecialistAdapter(model_id="openai-compatible")
        executor = AgentExecutor(adapter)
        return ResearchRuntime(open_state_backend(self._run_dir(project_id)), project,
                               agent_executors={name: executor for name in (
                                   "research-director", "literature-agent", "writing-agent",
                                   "reviewer-verifier-agent")})

    def create(self, project_id: str, question: str) -> dict[str, Any]:
        project, _ = self._paths(project_id)
        if len(question.strip()) < 10 or project.exists():
            raise ValueError("Question must be at least 10 characters; project id must be new")
        project.mkdir(parents=True)
        manifest = {"schema_version": "economics-paper-project/1.0", "project_id": project_id,
                    "title_working": question.strip(), "paper_type": "review", "stage": "idea",
                    "research_question": question.strip(), "target_journals": [],
                    "contribution_claims": [], "data_sensitivity": "public",
                    "approvals": {"question_and_contribution": False, "research_design": False,
                                  "outline_and_journal": False}, "output_format": "latex"}
        path = project / "manifest.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        store = ResearchRuntime.initialize(path, self.root / "runs", state_backend="sqlite")
        # Personal Zotero state is excluded from the public external-model demo.
        state, version = store.load_with_version()
        for task in state["task_graph"]:
            if task["task_id"] == "literature":
                task["allowed_tools"] = [name for name in task["allowed_tools"] if name != "zotero_local_read"]
        store.save(state, "demo.public-tool-scope", {"excluded": ["zotero_local_read"]}, expected_version=version)
        return {"project_id": project_id, "run_id": store.load()["run_id"]}

    def status(self, project_id: str) -> dict[str, Any]:
        state = open_state_backend(self._run_dir(project_id)).load()
        return {"project_id": project_id, "run_id": state["run_id"],
                "lifecycle_status": state["lifecycle_status"], "current_stage": state["current_stage"],
                "tasks": [{"id": t["task_id"], "status": t["status"], "error": t.get("error")}
                          for t in state["task_graph"]],
                "pending_human_actions": state["pending_human_actions"],
                "artifacts": [{"path": a["path"], "sha256": a["sha256"]}
                              for a in state["artifacts"] if not a.get("external")],
                "model_configured": all(os.environ.get(name) for name in (
                    "RESEARCH_OS_MODEL_API_KEY", "RESEARCH_OS_MODEL_NAME", "RESEARCH_OS_MODEL_BASE_URL")),
                "zotero_configured": all(os.environ.get(name) for name in (
                    "ZOTERO_API_KEY", "ZOTERO_USER_ID")),
                "worker_error": self._job_errors.get(project_id)}

    def upload_source(self, project_id: str, doi: str, data: bytes, *, public_model_use_approved: bool = False) -> dict[str, Any]:
        if not public_model_use_approved:
            raise PermissionError("Explicit authorization to send this public PDF text to the configured model is required")
        if project_id in self._jobs and self._jobs[project_id].is_alive():
            raise RuntimeError("Wait until the current agent step stops before adding sources")
        project, _ = self._paths(project_id)
        self._run_dir(project_id)
        doi = _normalize_doi(doi)
        metadata = _crossref(doi)
        verification = _check_pdf(data, metadata["title"])
        digest = sha256_file_bytes(data)
        stem = digest[:20]
        relative_pdf = f"literature/inputs/{stem}.pdf"
        pdf = project / relative_pdf
        pdf.parent.mkdir(parents=True, exist_ok=True)
        if pdf.exists() and sha256_file(pdf) != digest:
            raise ValueError("Existing PDF hash differs")
        pdf.write_bytes(data)
        record = {"schema_version": "literature-source/1.0", "metadata": metadata,
                  "pdf": relative_pdf, "pdf_sha256": digest,
                  "fulltext_status": "FULL_TEXT_OBTAINED", "verification": verification,
                  "public_model_use_approved": True}
        relative_record = f"literature/inputs/{stem}.json"
        (project / relative_record).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        runtime = self._runtime(project_id)
        runtime.register_source(relative_pdf)
        runtime.register_source(relative_record)
        return {"doi": doi, "pdf_sha256": digest, "source_record": relative_record,
                "verification": verification}

    def start(self, project_id: str) -> dict[str, Any]:
        self._run_dir(project_id)
        missing = [name for name in ("RESEARCH_OS_MODEL_API_KEY", "RESEARCH_OS_MODEL_NAME",
                                     "RESEARCH_OS_MODEL_BASE_URL") if not os.environ.get(name)]
        if missing:
            raise ValueError("Model environment is incomplete: " + ", ".join(missing))
        lock = self._locks.setdefault(project_id, threading.Lock())
        if lock.locked() or (project_id in self._jobs and self._jobs[project_id].is_alive()):
            return {"status": "already-running"}
        self._job_errors.pop(project_id, None)
        def work() -> None:
            with lock:
                try:
                    self._runtime(project_id).resume()
                except Exception as exc:
                    # The persisted state and trace are authoritative; callers can
                    # inspect status and explicitly retry after a process restart.
                    self._job_errors[project_id] = f"{type(exc).__name__}: {str(exc)[:200]}"
        thread = threading.Thread(target=work, daemon=True, name=f"literature-demo-{project_id}")
        self._jobs[project_id] = thread
        thread.start()
        return {"status": "started"}

    def decide(self, project_id: str, action_id: str, approve: bool, rationale: str) -> dict[str, Any]:
        if project_id in self._jobs and self._jobs[project_id].is_alive():
            raise RuntimeError("Wait until the current agent step stops before deciding")
        state = self._runtime(project_id).decide(action_id, approve, rationale)
        return {"lifecycle_status": state["lifecycle_status"], "decision": "approved" if approve else "rejected"}

    def import_zotero(self, project_id: str, source_record: str, collection_key: str,
                      rationale: str) -> dict[str, Any]:
        if project_id in self._jobs and self._jobs[project_id].is_alive():
            raise RuntimeError("Wait until the current agent step stops before Zotero import")
        project, _ = self._paths(project_id)
        if not re.fullmatch(r"literature/inputs/[a-f0-9]{20}\.json", source_record):
            raise ValueError("Unknown source record path")
        record_path = project / source_record
        state = open_state_backend(self._run_dir(project_id)).load()
        if not any(a["path"] == source_record and a["sha256"] == sha256_file(record_path)
                   for a in state["artifacts"]):
            raise ValueError("Source metadata is not registered with matching hash")
        record = json.loads(record_path.read_text(encoding="utf-8"))
        pdf = project / record["pdf"]
        if record["fulltext_status"] != "FULL_TEXT_OBTAINED" or sha256_file(pdf) != record["pdf_sha256"]:
            raise ValueError("PDF verification or hash no longer matches")
        self._runtime(project_id).record_external_approval(
            operation="zotero-cloud-import", target_hash=record["pdf_sha256"], rationale=rationale)
        receipt = project / "literature" / "zotero-receipts" / (pdf.stem + ".json")
        return ZoteroCloud().import_pdf(doi=record["metadata"]["doi"], metadata=record["metadata"],
                                        pdf=pdf, collection_key=collection_key,
                                        receipt_path=receipt, approved=True)


def sha256_file_bytes(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


_HTML = """<!doctype html><html lang=zh><meta charset=utf-8><title>Research OS 文献演示</title>
<style>body{font:16px system-ui;max-width:850px;margin:2rem auto;line-height:1.6}input,button,textarea{font:inherit;margin:.3rem;padding:.35rem}textarea{width:95%;height:5rem}pre{white-space:pre-wrap;background:#f4f4f4;padding:1rem}</style>
<h1>Research OS · 文献综述演示</h1><p>仅本机访问。密钥从服务器环境变量读取，不在网页输入。</p>
<label>项目 ID <input id=pid value=demo-literature></label><br><label>研究问题</label><textarea id=question></textarea>
<button onclick=createProject()>创建项目</button> <button onclick=start()>运行 / 继续</button> <button onclick=status()>刷新状态</button>
<h2>导入已获授权的 PDF</h2><label>DOI <input id=doi></label><input id=pdf type=file accept=application/pdf><br><label><input id=publiccheck type=checkbox>我确认此全文可发送给我配置的外部模型处理</label><button onclick=upload()>验证并存入项目</button>
<h2>人工决策</h2><label>action_id <input id=action></label><label>理由 <input id=reason></label><button onclick=decide(true)>批准</button><button onclick=decide(false)>拒绝</button>
<h2>Zotero 云端归档</h2><p>先验证 PDF，随后填写已存在的个人文库分类 Key，并明确批准上传。此操作可能消耗 Zotero storage。</p>
<label>源记录路径 <input id=record size=45></label><button onclick=collections()>读取分类</button><select id=collection></select><br>
<label>上传理由 <input id=archiveReason size=55 placeholder="确认来源合法、题录匹配并同意云端上传"></label><button onclick=archive()>批准并上传全文</button>
<pre id=out>尚未开始</pre><script>
const id=()=>document.getElementById('pid').value;
async function call(path,body,method='POST'){let r=await fetch(path,{method,headers:{'Content-Type':'application/json','X-Research-Token':'__TOKEN__'},body:body?JSON.stringify(body):undefined});let x=await r.json();out.textContent=JSON.stringify(x,null,2);return x}
async function createProject(){await call('/api/projects',{project_id:id(),question:question.value})}
async function start(){await call('/api/projects/'+id()+'/run',{})}
async function status(){await call('/api/projects/'+id(),null,'GET')}
async function decide(approve){await call('/api/projects/'+id()+'/decide',{action_id:action.value,approve,rationale:reason.value})}
async function collections(){let x=await call('/api/zotero/collections',null,'GET');collection.replaceChildren();for(let c of x.collections||[]){let o=document.createElement('option');o.value=c.key;o.textContent=c.name+' ('+c.key+')';collection.append(o)}}
async function archive(){if(!archiveReason.value.trim()){alert('请填写上传理由');return};await call('/api/projects/'+id()+'/zotero',{source_record:record.value,collection_key:collection.value,rationale:archiveReason.value})}
async function upload(){let file=pdf.files[0];if(!file||!publiccheck.checked){alert('请选择 PDF 并确认外部模型处理授权');return};let r=await fetch('/api/projects/'+id()+'/sources?doi='+encodeURIComponent(doi.value),{method:'POST',headers:{'Content-Type':'application/pdf','X-Research-Token':'__TOKEN__','X-Source-Public':'true'},body:file});let x=await r.json();out.textContent=JSON.stringify(x,null,2);if(x.source_record)record.value=x.source_record}
</script></html>"""


def handler(service: DemoService) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, value: Any, kind: str = "application/json") -> None:
            raw = (value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", f"{kind}; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers(); self.wfile.write(raw)

        def _route(self, body: bytes | None = None) -> None:
            parsed = urllib.parse.urlparse(self.path)
            parts = parsed.path.strip("/").split("/")
            if self.command == "GET" and parsed.path == "/":
                return self._send(200, _HTML.replace("__TOKEN__", service.token), "text/html")
            if self.command == "GET" and parsed.path == "/api/zotero/collections":
                return self._send(200, {"collections": ZoteroCloud().collections()})
            if self.command == "POST" and parsed.path == "/api/projects":
                request = json.loads(body or b"{}")
                return self._send(201, service.create(request["project_id"], request["question"]))
            if len(parts) < 3 or parts[:2] != ["api", "projects"]:
                return self._send(404, {"error": "not-found"})
            project_id = parts[2]
            if self.command == "GET" and len(parts) == 3:
                return self._send(200, service.status(project_id))
            if self.command != "POST" or len(parts) != 4:
                return self._send(404, {"error": "not-found"})
            action = parts[3]
            if action == "run": return self._send(202, service.start(project_id))
            if action == "sources":
                doi = urllib.parse.parse_qs(parsed.query).get("doi", [""])[0]
                return self._send(201, service.upload_source(project_id, doi, body or b"",
                    public_model_use_approved=self.headers.get("X-Source-Public") == "true"))
            request = json.loads(body or b"{}")
            if action == "decide":
                return self._send(200, service.decide(project_id, request["action_id"],
                                                       request["approve"], request["rationale"]))
            if action == "zotero":
                return self._send(200, service.import_zotero(project_id, request["source_record"],
                                                               request["collection_key"], request["rationale"]))
            return self._send(404, {"error": "not-found"})

        def do_GET(self) -> None:
            if self.path != "/" and self.headers.get("X-Research-Token") != service.token:
                return self._send(403, {"error": "token-required"})
            try: self._route()
            except Exception as exc: self._send(400, {"error": type(exc).__name__, "detail": str(exc)[:300]})

        def do_POST(self) -> None:
            if self.headers.get("X-Research-Token") != service.token:
                return self._send(403, {"error": "token-required"})
            origin = self.headers.get("Origin", "")
            if origin and origin not in {"http://127.0.0.1:" + str(self.server.server_port),
                                         "http://localhost:" + str(self.server.server_port)}:
                return self._send(403, {"error": "origin-rejected"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 0 or size > _MAX_BODY: return self._send(413, {"error": "body-too-large"})
                self._route(self.rfile.read(size))
            except Exception as exc:
                self._send(400, {"error": type(exc).__name__, "detail": str(exc)[:300]})
    return Handler


def serve(root: str | Path, port: int = 8765) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", port), handler(DemoService(root)))
    server.serve_forever(poll_interval=0.5)
