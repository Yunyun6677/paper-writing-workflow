# Literature Workflow Contract v1

本协议用于连接“选题、检索、筛选、去重、导入、全文处理、笔记、综述和写作”等程序阶段。

## 1. 稳定标识符

- `record_id`：优先使用规范化 DOI，例如 `doi:10.1016/j.chieco.2023.102085`；无 DOI 时依次使用 PMID、RePEc Handle、CNKI 标识符或来源 URL 的哈希。
- `zotero_item_key`：Zotero 内部条目标识，如 `NQNJKK75`。
- `bibtex_key`：写作引用键，如 `zhao_place-based_2024`。
- 三者不得混用。

## 2. 每次运行的顶层对象

```json
{
  "schema_version": "literature-workflow/1.0",
  "run_id": "unique-run-id",
  "request": {},
  "search_plan": {},
  "candidates": [],
  "decisions": [],
  "imports": [],
  "errors": [],
  "next_stage_input": {}
}
```

## 3. 文献记录的最小字段

```json
{
  "record_id": "doi:...",
  "zotero_item_key": null,
  "bibtex_key": null,
  "title": "",
  "authors": [],
  "year": null,
  "publication": "",
  "doi": "",
  "url": "",
  "abstract": "",
  "research_fields": [],
  "methods": [],
  "regions": [],
  "keywords": [],
  "evidence_type": "",
  "relevance_score": null,
  "quality_score": null,
  "duplicate_status": "unchecked",
  "screening_decision": "pending",
  "screening_reason": "",
  "target_collections": [],
  "import_status": "not-imported",
  "attachment_status": "unknown",
  "provenance": []
}
```

## 4. 推荐的写入安全规则

1. 检索结果先进入候选集，不直接写入正式分类。
2. 按 DOI、标题、作者与年份进行多重去重。
3. 达到相关性和质量阈值后才进入待导入队列。
4. 自动导入时记录来源、时间、目标分类与运行编号。
5. PDF 只从开放获取来源、机构订阅允许的合法入口或用户已有附件获取；元数据导入和 PDF 获取分开记录。
6. 批量写入应支持 `dry_run`，并输出将新增、跳过和报错的条目数量。

## 5. 状态枚举

- `screening_decision`: `pending | include | exclude | manual-review`
- `duplicate_status`: `unchecked | unique | probable-duplicate | duplicate`
- `import_status`: `not-imported | queued | created | updated | skipped | failed`
- `attachment_status`: `unknown | metadata-only | indexed-fulltext | unindexed-file | open-access-available | access-restricted`

## 6. 当前已验证的接口

- Zotero 本地 API：读取题录、分类、标签、附件与索引全文。
- Zotero Connector：将 BibTeX/RIS 导入当前选中的文库或分类。
- BibTeX 导出：为后续 Markdown、LaTeX 或其他写作程序同步引用键。

