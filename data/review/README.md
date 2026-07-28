# 知识复验数据目录

此目录由人工维护，不从 `base` 自动读取或同步。业务数据、复验数据库和导出文件均不提交到版本库。

## 必需结构

```text
data/review/
├── current/
│   ├── chunks/
│   ├── entity_nodes/
│   ├── raw_pdf/
│   └── graph_property_schema_v3_6.json
└── state/
    ├── review.sqlite3
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

`entity_nodes` 中的文件名必须以 `.entity_nodes.base.jsonl` 结尾。每行是一个 JSON 对象，至少包含 `entity_id`、`chunk_id`、`entity_type`、`name` 和 `evidence_text`。`chunk_id` 使用对应文档中的原始分块 ID，服务加载时会自动加上 `doc_id` 前缀。

`graph_property_schema_v3_6.json` 必须包含 `schema_version`、`entities` 和 `relationships` 定义。

`raw_pdf` 为可选目录。PDF 文件名（不含扩展名）应与 `source_title` 一致；系统会建立 `doc_id` 到 PDF 的映射。重复匹配会导致复验模块进入降级状态，防止打开错误文档。

## 替换数据

1. 停止后端，备份 `state/review.sqlite3`。
2. 完整替换 `current` 下的数据，不要在服务运行时逐个覆盖文件。
3. 如果新数据与旧数据不是同一批次，移走旧的 `state/review.sqlite3`，避免复验状态串批。
4. 重启后访问 `/api/review/health`，确认状态为 `ok`。

缺少数据时，统一后端仍可启动，诊断模块可正常工作；知识复验接口会返回 `503 TASK_UNAVAILABLE`。

严禁在此目录保存可识别患者身份的信息、数据库密码、访问令牌或其他敏感凭据。
