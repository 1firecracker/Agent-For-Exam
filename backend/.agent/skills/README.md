# Agent Skills

本目录包含 Agent 可用的所有技能（Skills）定义。

## 目录结构

```
.agent/skills/
├── README.md                 # 本文件
├── mindmap/                  # 思维导图生成技能
│   └── SKILL.md
├── knowledge_query/          # 知识图谱查询技能
│   └── SKILL.md
└── list_documents/           # 文档列表技能
    └── SKILL.md
```

## SKILL.md 格式

每个技能文件夹必须包含一个 `SKILL.md` 文件，格式如下：

```markdown
---
name: skill_name           # 技能唯一标识符，对应工具名称
description: 简短描述       # 用于 Agent 判断是否相关（仅此两个字段）
---

# 技能完整说明（Markdown 正文）

## 用途
何时使用此技能...

## 参数说明
参数表格...

## 使用规则
详细的使用说明...

## 示例
调用示例...

## 返回格式
JSON 示例...
```

**注意**: YAML Frontmatter 只包含 `name` 和 `description` 两个字段，保持最小化。其他信息（如参数定义、示例等）全部放在 Markdown 正文中。

## 渐进式披露机制

1. **Discovery Phase**: 系统启动时，仅加载 YAML Frontmatter（name + description）
2. **Activation Phase**: 当 Agent 判断某个技能相关时，加载完整的 Markdown 正文
3. **Execution Phase**: 调用对应的 Python handler 执行实际操作

## 添加新技能

1. 创建新文件夹: `.agent/skills/<skill_name>/`
2. 编写 `SKILL.md` 文件（遵循上述格式）
3. 在 `backend/app/services/agent/tools/` 中实现对应的 handler
4. 在 `SkillManager` 中注册技能与 handler 的映射
