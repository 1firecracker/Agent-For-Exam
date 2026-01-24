---
name: generate_mindmap
description: 根据对话中的文档内容生成思维导图。可以指定特定文档，或生成所有文档的思维导图。
---

# 思维导图生成工具

## 用途
当用户需要将复杂的文档内容可视化为层次结构图时使用此工具。

## 触发条件
当用户表达以下意图时，应该使用此工具：
- "生成思维导图"、"画个脑图"、"做个思维脑图"
- "帮我可视化这个文档"、"画出结构图"
- "summarize as a map"、"visualize the content"

## 参数说明

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| document_ids | array[string] | 否 | 要生成思维导图的文档ID列表。如果不提供则处理所有文档。**必须使用 file_id，不能使用文件名** |

## 使用规则

### 1. 获取文档 ID
如果用户指定了具体的文档名（如"帮我画 Lecture 1 的脑图"），你需要：
1. 先调用 `list_documents` 工具获取文档列表
2. 从结果中找到对应文件名的 `file_id`
3. 再调用 `generate_mindmap` 并传入该 `file_id`

### 2. 输出说明
- 思维导图会以 Markdown 格式保存到对话中
- 用户可以在前端的"思维脑图"标签页中查看可视化结果
- 对于多个文档，会逐个生成并合并

## 示例

### 示例 1: 生成所有文档的思维导图
**用户**: "帮我生成思维导图"
**调用**: `generate_mindmap({})`

### 示例 2: 生成指定文档的思维导图
**用户**: "给第一个文档画个脑图"
**步骤**:
1. 调用 `list_documents({})` 获取文档列表
2. 从结果中提取第一个文档的 `file_id`
3. 调用 `generate_mindmap({"document_ids": ["<file_id>"]})`

## 返回格式
```json
{
  "status": "success",
  "message": "思维脑图已生成（基于 N 个文档）",
  "mindmap_content": "# 标题\n\n- 节点1\n  - 子节点...",
  "document_count": 2,
  "document_names": ["doc1.pdf", "doc2.pdf"]
}
```
