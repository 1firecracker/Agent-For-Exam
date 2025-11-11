# API 接口文档

## 📋 目录

- [基础信息](#基础信息)
- [对话管理 API](#对话管理-api)
- [文档管理 API](#文档管理-api)
- [幻灯片相关 API](#幻灯片相关-api)
- [知识图谱查询 API](#知识图谱查询-api)
- [样本试题管理 API](#样本试题管理-api)
- [错误处理](#错误处理)
- [快速参考](#快速参考)

---

## 基础信息

### 服务器地址
- **开发环境**: `http://127.0.0.1:8000`
- **API 文档（Swagger UI）**: `http://127.0.0.1:8000/docs`
- **API 文档（ReDoc）**: `http://127.0.0.1:8000/redoc`

### 请求格式
- **Content-Type**: `application/json`（POST/PUT 请求）
- **文件上传**: `multipart/form-data`

### 响应格式
所有响应均为 JSON 格式。

---

## 对话管理 API

### 1. 创建对话

**接口**: `POST /api/conversations`

**描述**: 手动创建一个新对话。如果不提供标题，系统会自动生成编号（对话_1, 对话_2...）。

**请求体**:
```json
{
  "title": "可选标题"  // 可选，如不提供则自动生成编号
}
```

**响应** (201 Created):
```json
{
  "conversation_id": "uuid-string",
  "title": "对话_1",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "file_count": 0,
  "status": "active"
}
```

**使用场景**:
- 用户点击"创建新对话"按钮时调用
- 如果不提供标题，系统会自动生成编号（对话_1, 对话_2...）
- **注意**: 即使修改了对话标题，后续的自动编号仍会继续递增

**示例**:
```bash
# 自动编号
curl -X POST http://127.0.0.1:8000/api/conversations \
  -H "Content-Type: application/json" \
  -d "{}"

# 提供标题
curl -X POST http://127.0.0.1:8000/api/conversations \
  -H "Content-Type: application/json" \
  -d '{"title": "我的项目"}'
```

---

### 2. 获取对话列表

**接口**: `GET /api/conversations`

**描述**: 获取所有对话列表，按更新时间倒序排列。

**查询参数**:
- `status_filter` (可选): 过滤状态，值可以是 `active` 或 `archived`

**响应** (200 OK):
```json
{
  "conversations": [
    {
      "conversation_id": "uuid-string",
      "title": "对话_1",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z",
      "file_count": 5,
      "status": "active"
    }
  ],
  "total": 1
}
```

**示例**:
```bash
# 获取所有对话
curl http://127.0.0.1:8000/api/conversations

# 只获取活跃对话
curl "http://127.0.0.1:8000/api/conversations?status_filter=active"
```

---

### 3. 获取对话详情

**接口**: `GET /api/conversations/{conversation_id}`

**描述**: 获取指定对话的详细信息。

**路径参数**:
- `conversation_id`: 对话ID（UUID格式）

**响应** (200 OK):
```json
{
  "conversation_id": "uuid-string",
  "title": "对话_1",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "file_count": 5,
  "status": "active"
}
```

**错误响应** (404 Not Found):
```json
{
  "detail": "对话 {conversation_id} 不存在"
}
```

**示例**:
```bash
curl http://127.0.0.1:8000/api/conversations/{conversation_id}
```

---

### 4. 删除对话

**接口**: `DELETE /api/conversations/{conversation_id}`

**描述**: 删除指定对话及其所有相关数据（包括文件、LightRAG数据等）。

**路径参数**:
- `conversation_id`: 对话ID

**响应** (204 No Content): 无响应体

**错误响应** (404 Not Found):
```json
{
  "detail": "对话 {conversation_id} 不存在"
}
```

**示例**:
```bash
curl -X DELETE http://127.0.0.1:8000/api/conversations/{conversation_id}
```

---

## 文档管理 API

### 1. 上传文档

**接口**: `POST /api/conversations/{conversation_id}/documents/upload`

**描述**: 上传一个或多个文档到指定对话。支持自动创建对话。

**路径参数**:
- `conversation_id`: 对话ID，使用 `"new"` 表示自动创建新对话

**请求格式**: `multipart/form-data`

**请求字段**:
- `files`: 文件列表（支持多文件上传）

**限制**:
- 每个对话最多 20 个文件
- 单个文件最大 50MB
- 支持格式: `.pptx`, `.pdf`

**响应** (201 Created):
```json
{
  "conversation_id": "uuid-string",
  "uploaded_files": [
    {
      "file_id": "uuid-string",
      "filename": "example.pdf",
      "file_size": 1024000,
      "status": "pending"
    }
  ],
  "total_files": 1
}
```

**注意事项**:
- 上传后立即返回响应，文档处理在后台异步进行
- 文档状态: `pending` → `processing` → `completed`/`failed`
- 需要使用状态查询接口来获取处理进度

**示例**:
```bash
# 自动创建对话
curl -X POST http://127.0.0.1:8000/api/conversations/new/documents/upload \
  -F "files=@document1.pdf" \
  -F "files=@document2.pptx"

# 上传到指定对话
curl -X POST http://127.0.0.1:8000/api/conversations/{conversation_id}/documents/upload \
  -F "files=@document.pdf"
```

**错误响应** (400 Bad Request):
```json
{
  "detail": "对话已有 18 个文件，再上传 3 个将超过限制 (20 个)"
}
```

---

### 2. 获取文档列表

**接口**: `GET /api/conversations/{conversation_id}/documents`

**描述**: 获取指定对话的所有文档列表，按上传时间倒序排列。

**路径参数**:
- `conversation_id`: 对话ID

**响应** (200 OK):
```json
{
  "documents": [
    {
      "file_id": "uuid-string",
      "conversation_id": "uuid-string",
      "filename": "example.pdf",
      "file_size": 1024000,
      "file_extension": "pdf",
      "upload_time": "2024-01-01T00:00:00Z",
      "status": "completed",
      "lightrag_track_id": "insert_20240101_120000_abc123"
    }
  ],
  "total": 1
}
```

**状态说明**:
- `pending`: 已上传，等待处理
- `processing`: 正在处理中
- `completed`: 处理完成
- `failed`: 处理失败

**示例**:
```bash
curl http://127.0.0.1:8000/api/conversations/{conversation_id}/documents
```

---

### 3. 获取文档详情

**接口**: `GET /api/conversations/{conversation_id}/documents/{file_id}`

**描述**: 获取指定文档的详细信息。

**路径参数**:
- `conversation_id`: 对话ID
- `file_id`: 文件ID

**响应** (200 OK):
```json
{
  "file_id": "uuid-string",
  "conversation_id": "uuid-string",
  "filename": "example.pdf",
  "file_size": 1024000,
  "file_extension": "pdf",
  "upload_time": "2024-01-01T00:00:00Z",
  "status": "completed",
  "lightrag_track_id": "insert_20240101_120000_abc123"
}
```

**错误响应** (404 Not Found):
```json
{
  "detail": "文档 {file_id} 不存在"
}
```

**示例**:
```bash
curl http://127.0.0.1:8000/api/conversations/{conversation_id}/documents/{file_id}
```

---

### 4. 查询文档处理状态

**接口**: `GET /api/conversations/{conversation_id}/documents/{file_id}/status`

**描述**: 查询文档的处理状态和进度。

**路径参数**:
- `conversation_id`: 对话ID
- `file_id`: 文件ID

**响应** (200 OK):
```json
{
  "file_id": "uuid-string",
  "status": "completed",
  "lightrag_track_id": "insert_20240101_120000_abc123",
  "error": null,
  "upload_time": "2024-01-01T00:00:00Z"
}
```

**状态说明**:
- `pending`: 待处理
- `processing`: 处理中
- `completed`: 已完成（此时 `lightrag_track_id` 有值）
- `failed`: 失败（此时 `error` 字段包含错误信息）

**使用建议**:
- 上传文档后，建议每 2-5 秒轮询一次状态
- 处理时间取决于文档大小和 API 响应速度，通常需要 30-60 秒

**示例**:
```bash
curl http://127.0.0.1:8000/api/conversations/{conversation_id}/documents/{file_id}/status
```

---

### 5. 删除文档

**接口**: `DELETE /api/conversations/{conversation_id}/documents/{file_id}`

**描述**: 删除指定文档（包括文件和相关数据）。

**路径参数**:
- `conversation_id`: 对话ID
- `file_id`: 文件ID

**响应** (204 No Content): 无响应体

**错误响应** (404 Not Found):
```json
{
  "detail": "文档 {file_id} 不存在"
}
```

**示例**:
```bash
curl -X DELETE http://127.0.0.1:8000/api/conversations/{conversation_id}/documents/{file_id}
```

---

## 幻灯片相关 API

### 1. 获取所有幻灯片

**接口**: `GET /api/conversations/{conversation_id}/documents/{file_id}/slides`

**描述**: 获取PPTX文档的所有幻灯片列表。

**限制**: 仅支持 `.pptx` 格式文件

**路径参数**:
- `conversation_id`: 对话ID
- `file_id`: 文件ID（必须是PPTX文件）

**响应** (200 OK):
```json
{
  "filename": "presentation.pptx",
  "total_slides": 19,
  "slides": [
    {
      "slide_number": 1,
      "title": "幻灯片标题",
      "text_content": "幻灯片文本内容...",
      "images": [
        {
          "image_id": "slide_1_img_0",
          "position": {
            "left": 1000000,
            "top": 500000,
            "width": 2000000,
            "height": 1500000
          },
          "alt_text": "Image 1"
        }
      ],
      "structure": {
        "layout": "标题幻灯片",
        "shapes_count": 5
      }
    }
  ]
}
```

**错误响应** (400 Bad Request):
```json
{
  "detail": "此接口仅支持 PPTX 格式文件"
}
```

**示例**:
```bash
curl http://127.0.0.1:8000/api/conversations/{conversation_id}/documents/{file_id}/slides
```

---

### 2. 获取单个幻灯片

**接口**: `GET /api/conversations/{conversation_id}/documents/{file_id}/slides/{slide_id}`

**描述**: 获取PPTX文档的指定幻灯片内容和元数据。

**限制**: 仅支持 `.pptx` 格式文件

**路径参数**:
- `conversation_id`: 对话ID
- `file_id`: 文件ID（必须是PPTX文件）
- `slide_id`: 幻灯片编号（从 1 开始）

**响应** (200 OK):
```json
{
  "slide_number": 1,
  "title": "幻灯片标题",
  "text_content": "幻灯片文本内容...",
  "images": [
    {
      "image_id": "slide_1_img_0",
      "position": {
        "left": 1000000,
        "top": 500000,
        "width": 2000000,
        "height": 1500000
      },
      "alt_text": "Image 1"
    }
  ],
  "structure": {
    "layout": "标题幻灯片",
    "shapes_count": 5
  }
}
```

**错误响应** (404 Not Found):
```json
{
  "detail": "幻灯片 100 不存在（共 19 张）"
}
```

**示例**:
```bash
# 获取第1张幻灯片
curl http://127.0.0.1:8000/api/conversations/{conversation_id}/documents/{file_id}/slides/1

# 获取第5张幻灯片
curl http://127.0.0.1:8000/api/conversations/{conversation_id}/documents/{file_id}/slides/5
```

---

## 知识图谱查询 API

### 1. 获取知识图谱

**接口**: `GET /api/conversations/{conversation_id}/graph`

**描述**: 获取指定对话的知识图谱，包括所有实体和关系。

**路径参数**:
- `conversation_id`: 对话ID

**响应** (200 OK):
```json
{
  "entities": [
    {
      "entity_id": "人工智能",
      "name": "人工智能",
      "type": "concept",
      "description": "计算机科学的一个分支"
    }
  ],
  "relations": [
    {
      "relation_id": "人工智能->机器学习",
      "source": "人工智能",
      "target": "机器学习",
      "type": "包含",
      "description": ""
    }
  ],
  "total_entities": 29,
  "total_relations": 19
}
```

**注意事项**:
- 需要先上传文档并等待处理完成
- 处理完成后才能获取到实体和关系

**示例**:
```bash
curl http://127.0.0.1:8000/api/conversations/{conversation_id}/graph
```

---

### 2. 获取实体详情

**接口**: `GET /api/conversations/{conversation_id}/graph/entities/{entity_id}`

**描述**: 获取指定实体的详细信息。

**路径参数**:
- `conversation_id`: 对话ID
- `entity_id`: 实体ID（实体名称）

**响应** (200 OK):
```json
{
  "entity_id": "人工智能",
  "name": "人工智能",
  "type": "concept",
  "description": "计算机科学的一个分支，旨在创建智能机器"
}
```

**错误响应** (404 Not Found):
```json
{
  "detail": "实体 {entity_id} 不存在"
}
```

**示例**:
```bash
curl http://127.0.0.1:8000/api/conversations/{conversation_id}/graph/entities/人工智能
```

---

### 3. 查询知识图谱

**接口**: `POST /api/conversations/{conversation_id}/query`

**描述**: 在指定对话的知识图谱中进行智能查询。

**路径参数**:
- `conversation_id`: 对话ID

**请求体**:
```json
{
  "query": "什么是人工智能？",
  "mode": "mix"  // 可选: naive, local, global, mix（默认）
}
```

**查询模式说明**:
- `naive`: 基础查询，基于向量相似度检索文本块
- `local`: 本地查询，基于知识图谱的子图检索
- `global`: 全局查询，基于整个知识图谱检索
- `mix`: 混合查询（推荐），结合多种方式

**响应** (200 OK):
```json
{
  "conversation_id": "uuid-string",
  "query": "什么是人工智能？",
  "mode": "mix",
  "result": "人工智能（Artificial Intelligence, AI）是计算机科学的一个重要分支..."
}
```

**错误响应** (400 Bad Request):
```json
{
  "detail": "无效的查询模式: invalid_mode，支持的模式: naive, local, global, mix"
}
```

**注意事项**:
- 需要先上传文档并等待处理完成
- 查询结果基于该对话中已处理的文档内容
- 不同对话之间的知识图谱完全独立

**示例**:
```bash
curl -X POST http://127.0.0.1:8000/api/conversations/{conversation_id}/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "什么是人工智能？",
    "mode": "mix"
  }'
```

---

## 样本试题管理 API

### 1. 上传样本试题

**接口**: `POST /api/conversations/{conversation_id}/exercises/samples/upload`

**描述**: 上传一个或多个样本试题文件（PDF/DOCX/TXT格式），系统会自动解析文本和图片。

**路径参数**:
- `conversation_id`: 对话ID

**请求格式**: `multipart/form-data`

**请求字段**:
- `files`: 文件列表（支持多文件上传）

**限制**:
- 每个对话最多 50 个样本
- 单个文件最大 50MB
- 支持格式: `.pdf`, `.docx`, `.txt`

**响应** (201 Created):
```json
{
  "conversation_id": "uuid-string",
  "uploaded_samples": [
    {
      "sample_id": "final24",
      "filename": "final24.pdf",
      "file_size": 1024000,
      "file_type": "pdf",
      "text_length": 2567,
      "image_count": 5,
      "upload_time": "2024-01-01T00:00:00Z"
    }
  ],
  "total_samples": 1
}
```

**注意事项**:
- 上传后立即解析文件，提取文本和图片
- 解析结果保存在 `uploads/exercises/{conversation_id}/samples/{sample_id}/` 目录
- 图片标记会嵌入到文本中，格式为 `[IMAGE: img_1.png]`

**示例**:
```bash
curl -X POST http://127.0.0.1:8000/api/conversations/{conversation_id}/exercises/samples/upload \
  -F "files=@final24.pdf" \
  -F "files=@assignment1.docx"
```

**错误响应** (400 Bad Request):
```json
{
  "detail": "不支持的文件类型: doc，仅支持 pdf, docx, txt"
}
```

---

### 2. 获取样本试题列表

**接口**: `GET /api/conversations/{conversation_id}/exercises/samples`

**描述**: 获取指定对话的所有样本试题列表，按上传时间倒序排列。

**路径参数**:
- `conversation_id`: 对话ID

**响应** (200 OK):
```json
{
  "samples": [
    {
      "sample_id": "final24",
      "filename": "final24.pdf",
      "file_type": "pdf",
      "file_size": 1024000,
      "text_length": 2567,
      "image_count": 5,
      "upload_time": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 1
}
```

**示例**:
```bash
curl http://127.0.0.1:8000/api/conversations/{conversation_id}/exercises/samples
```

---

### 3. 获取样本试题详情

**接口**: `GET /api/conversations/{conversation_id}/exercises/samples/{sample_id}`

**描述**: 获取指定样本试题的详细信息，包括文本内容和图片列表。

**路径参数**:
- `conversation_id`: 对话ID
- `sample_id`: 样本ID（通常是文件名去除扩展名）

**响应** (200 OK):
```json
{
  "sample_id": "final24",
  "conversation_id": "uuid-string",
  "filename": "final24.pdf",
  "file_type": "pdf",
  "file_size": 1024000,
  "text_length": 2567,
  "image_count": 5,
  "upload_time": "2024-01-01T00:00:00Z",
  "images": [
    {
      "page_number": 1,
      "image_index": 1,
      "file_path": "images/page_1_img_1.png",
      "image_format": "png",
      "width": 0,
      "height": 0
    }
  ],
  "text_content": "完整的文本内容，包含图片标记 [IMAGE: img_1.png]..."
}
```

**错误响应** (404 Not Found):
```json
{
  "detail": "样本试题 final24 不存在"
}
```

**示例**:
```bash
curl http://127.0.0.1:8000/api/conversations/{conversation_id}/exercises/samples/final24
```

---

### 4. 获取样本试题文本

**接口**: `GET /api/conversations/{conversation_id}/exercises/samples/{sample_id}/text`

**描述**: 仅获取样本试题的文本内容（不包含其他元数据）。

**路径参数**:
- `conversation_id`: 对话ID
- `sample_id`: 样本ID

**响应** (200 OK):
```json
{
  "text": "完整的文本内容，包含图片标记 [IMAGE: img_1.png]..."
}
```

**示例**:
```bash
curl http://127.0.0.1:8000/api/conversations/{conversation_id}/exercises/samples/final24/text
```

---

### 5. 获取样本试题图片

**接口**: `GET /api/conversations/{conversation_id}/exercises/samples/{sample_id}/images/{image_name}`

**描述**: 获取样本试题中的指定图片文件。

**路径参数**:
- `conversation_id`: 对话ID
- `sample_id`: 样本ID
- `image_name`: 图片文件名（例如：`page_1_img_1.png`）

**响应** (200 OK):
- Content-Type: `image/png` 或 `image/jpeg` 等
- 响应体: 图片二进制数据

**错误响应** (404 Not Found):
```json
{
  "detail": "图片 page_1_img_1.png 不存在"
}
```

**示例**:
```bash
curl http://127.0.0.1:8000/api/conversations/{conversation_id}/exercises/samples/final24/images/page_1_img_1.png \
  --output image.png
```

---

### 6. 删除样本试题

**接口**: `DELETE /api/conversations/{conversation_id}/exercises/samples/{sample_id}`

**描述**: 删除指定样本试题及其所有相关文件（文本、图片等）。

**路径参数**:
- `conversation_id`: 对话ID
- `sample_id`: 样本ID

**响应** (204 No Content): 无响应体

**错误响应** (404 Not Found):
```json
{
  "detail": "样本试题 final24 不存在"
}
```

**示例**:
```bash
curl -X DELETE http://127.0.0.1:8000/api/conversations/{conversation_id}/exercises/samples/final24
```

---

## 错误处理

### HTTP 状态码

- **200 OK**: 请求成功
- **201 Created**: 创建成功
- **204 No Content**: 删除成功
- **400 Bad Request**: 请求错误（如文件类型不支持、超过限制等）
- **404 Not Found**: 资源不存在
- **500 Internal Server Error**: 服务器内部错误

### 错误响应格式

```json
{
  "detail": "错误信息描述"
}
```

### 常见错误

#### 1. 文件类型不支持
```json
{
  "detail": "不支持的文件类型: docx，仅支持 pptx, pdf"
}
```

#### 2. 文件大小超限
```json
{
  "detail": "文件大小 60.50MB 超过限制 50MB"
}
```

#### 3. 文件数量超限
```json
{
  "detail": "对话已有 18 个文件，再上传 3 个将超过限制 (20 个)"
}
```

#### 4. 资源不存在
```json
{
  "detail": "对话 {conversation_id} 不存在"
}
```

---

## 重要提示

### 1. 对话隔离
- **所有接口都需要 `conversation_id` 参数**
- **不同对话之间的数据完全独立**
- 每个对话有独立的 LightRAG 知识图谱

### 2. 文件上传限制
- **每个对话最多 20 个文件**
- **单个文件最大 50MB**
- **支持格式**: `.pptx`, `.pdf`

### 3. 文档处理
- 上传后立即返回响应
- 文档处理在后台异步进行
- 需要通过状态查询接口获取处理进度
- 处理时间通常需要 30-60 秒（取决于文档大小）

### 4. 对话创建
- **自动创建**: 使用 `conversation_id="new"` 上传文档时自动创建
- **手动创建**: 调用 `POST /api/conversations` 接口
- **自动编号**: 不提供标题时自动生成（对话_1, 对话_2...）
- **编号规则**: 即使修改了对话标题，编号仍会继续递增

### 5. 知识图谱查询
- 需要先上传文档并等待处理完成
- 处理完成后才能查询到实体和关系
- 查询结果仅基于该对话的文档内容

---

## 快速参考

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 创建对话 | POST | `/api/conversations` | 手动创建对话 |
| 对话列表 | GET | `/api/conversations` | 获取所有对话 |
| 对话详情 | GET | `/api/conversations/{id}` | 获取对话信息 |
| 删除对话 | DELETE | `/api/conversations/{id}` | 删除对话 |
| 上传文档 | POST | `/api/conversations/{id}/documents/upload` | 上传文档（使用`new`自动创建） |
| 文档列表 | GET | `/api/conversations/{id}/documents` | 获取文档列表 |
| 文档详情 | GET | `/api/conversations/{id}/documents/{file_id}` | 获取文档信息 |
| 文档状态 | GET | `/api/conversations/{id}/documents/{file_id}/status` | 查询处理状态 |
| 删除文档 | DELETE | `/api/conversations/{id}/documents/{file_id}` | 删除文档 |
| 幻灯片列表 | GET | `/api/conversations/{id}/documents/{file_id}/slides` | 获取所有幻灯片（仅PPTX） |
| 单个幻灯片 | GET | `/api/conversations/{id}/documents/{file_id}/slides/{slide_id}` | 获取单个幻灯片（仅PPTX） |
| 知识图谱 | GET | `/api/conversations/{id}/graph` | 获取所有实体和关系 |
| 实体详情 | GET | `/api/conversations/{id}/graph/entities/{entity_id}` | 获取实体信息 |
| 查询图谱 | POST | `/api/conversations/{id}/query` | 智能查询 |
| 上传样本 | POST | `/api/conversations/{id}/exercises/samples/upload` | 上传样本试题 |
| 样本列表 | GET | `/api/conversations/{id}/exercises/samples` | 获取样本列表 |
| 样本详情 | GET | `/api/conversations/{id}/exercises/samples/{sample_id}` | 获取样本详情 |
| 样本文本 | GET | `/api/conversations/{id}/exercises/samples/{sample_id}/text` | 获取样本文本 |
| 样本图片 | GET | `/api/conversations/{id}/exercises/samples/{sample_id}/images/{image_name}` | 获取样本图片 |
| 删除样本 | DELETE | `/api/conversations/{id}/exercises/samples/{sample_id}` | 删除样本 |

---

**文档版本**: 1.0  
**最后更新**: 2024-11-01  
**API 版本**: 1.0.0

