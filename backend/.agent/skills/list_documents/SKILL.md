---
name: list_documents
description: 列出当前对话中的所有文档名称，包括文件名、上传时间、状态等信息但是查看不了具体内容。
---

# 文档列表工具

## 用途
列出当前对话中已上传的所有文档及其基本信息。这是一个**辅助工具**，通常在调用其他工具之前使用。

## 触发条件
当用户表达以下意图时，应该使用此工具：
- "列出所有文档"、"显示文件列表"
- "有哪些文档？"、"我上传了什么文件？"
- 当需要获取 `file_id` 以供其他工具使用时

## 参数说明
此工具不需要额外参数。`conversation_id` 由系统自动注入。

## 使用规则

### 1. 作为前置查询
当其他工具需要 `document_ids` 参数，但用户只提供了文件名时：
1. 先调用 `list_documents` 获取文档列表
2. 从结果中匹配文件名，提取 `file_id`
3. 再调用目标工具

### 2. 结果展示
向用户展示文档列表时，使用友好的格式，不要直接暴露技术细节（如完整的 file_id）。

## 示例

### 示例 1: 用户查看文档
**用户**: "我上传了哪些文件？"
**调用**: `list_documents({})`
**回复**: "您上传了 3 个文档：1. Lecture1.pdf  2. Lecture2.pdf  3. Notes.docx"

### 示例 2: 为其他工具获取 file_id
**用户**: "帮我画 Lecture1.pdf 的思维导图"
**步骤**:
1. 调用 `list_documents({})` -> 获取 `[{"file_id": "abc123", "filename": "Lecture1.pdf"}, ...]`
2. 调用 `generate_mindmap({"document_ids": ["abc123"]})`

## 返回格式
```json
{
  "status": "success",
  "message": "成功列出 3 个文档",
  "result": "当前对话共有 3 个文档：\n1. Lecture1.pdf (1.2 MB) - 已完成\n...",
  "documents": [
    {
      "file_id": "abc123-def456-ghi789",
      "filename": "Lecture1.pdf",
      "upload_time": "2024-01-15 10:30:00",
      "status": "completed",
      "file_type": "pdf",
      "file_size": 1258000
    }
  ],
  "document_count": 3
}
```
