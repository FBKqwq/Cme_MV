# 知识复验数据目录

此目录由人工维护，不从 `base` 自动读取或同步。业务数据、复验结果集和导出文件均不提交到版本库。

## 必需结构

```text
data/review/
├── current/
│   ├── chunks/
│   ├── entity_nodes/
│   ├── raw_pdf/
│   └── graph_property_schema_v3_6.json
└── state/
    ├── results/
    │   └── <PDF文件名>.review.json
    └── exports/
```

`chunks` 中每个文件名应以 `_chunk.json` 或 `chunk.json` 结尾，内容至少包含：

```json
{
  "doc_id": "稳定且唯一的文档ID",
  "source_title": "文档标题",
  "chunks": [
    {
      "chunk_id": "文档内唯一的分块ID",
      "section_title": "章节标题",
      "page_start": 1,
      "page_end": 1,
      "text": "原文"
    }
  ]
}
```

`entity_nodes` 优先读取以 `.entity_label_result.jsonl` 结尾的完整分类结果，
以保留 `accepted`、`review` 和 `rejected` 状态。同一文档没有完整结果时，
回退读取 `.entity_nodes.base.jsonl`。每行是一个 JSON 对象，至少包含
`entity_id`、`chunk_id`、`entity_type`、`name` 和 `evidence_text`。
`chunk_id` 使用对应文档中的原始分块 ID，服务加载时会自动加上 `doc_id` 前缀。

`graph_property_schema_v3_6.json` 必须包含 `schema_version`、`entities` 和 `relationships` 定义。

`raw_pdf` 为可选目录。PDF 文件名（不含扩展名）应与 `source_title` 一致；系统会建立 `doc_id` 到 PDF 的映射。重复匹配会导致复验模块进入降级状态，防止打开错误文档。

## 复验结果格式

后端启动后会为每个 PDF 初始化一个
`state/results/<PDF文件名>.review.json`。其中 `entities` 包含该 PDF
的全部实体。实体的原始字段和值始终保留；人工修改只写入
`corrected_values`，不覆盖原字段。

```json
{
  "entity_id": "E02",
  "name": "口腔溃疡",
  "entity_type": "symptoms",
  "review_flag": "modified",
  "corrected_values": {
    "name": "复发性口腔溃疡"
  }
}
```

`review_flag` 可为 `pending`、`approved`、`modified`、`added` 或
`deleted`。服务返回页面数据时会应用 `corrected_values`；结果文件本身
仍同时保留原始值和修正值，便于审计、比对和下游转换。

## 替换数据

1. 停止后端，备份 `state/results`。
2. 完整替换 `current` 下的数据，不要在服务运行时逐个覆盖文件。
3. 如果新数据与旧数据不是同一批次，移走旧的 `state/results`，避免复验状态串批。
4. 重启后访问 `/api/review/health`，确认状态为 `ok`。

缺少数据时，统一后端仍可启动，诊断模块可正常工作；知识复验接口会返回 `503 TASK_UNAVAILABLE`。

严禁在此目录保存可识别患者身份的信息、数据库密码、访问令牌或其他敏感凭据。
