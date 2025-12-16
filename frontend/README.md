# 前端应用

基于 Vue 3 + Vite 的现代化前端应用，提供知识图谱构建、智能问答、思维导图生成等功能的 Web 界面。

## 技术栈

- **Vue 3** - 渐进式前端框架（Composition API）
- **Vite** - 快速的前端构建工具
- **Pinia** - 现代化状态管理
- **Vue Router** - 单页应用路由管理
- **Element Plus** - 企业级 UI 组件库
- **Cytoscape.js** - 知识图谱可视化引擎
- **Markmap** - 思维导图可视化引擎
- **Axios** - HTTP 客户端库

## 核心功能

### 1. 智能对话（Chat）
- 基于 Agent 模式的智能问答
- 支持多轮对话，保持上下文
- 实时流式响应显示
- 工具调用可视化（思维导图生成、知识图谱查询等）
- 工具执行进度显示

### 2. 知识图谱（Graph）
- 基于 LightRAG 构建的知识图谱可视化
- 实体和关系交互式展示
- 支持节点过滤和搜索
- 实体来源文档追踪

### 3. 思维导图（Mindmap）
- 自动生成文档的思维导图
- 支持 Markmap 可视化
- 可导出为 XMind 格式
- 实时生成进度显示

### 4. 文档管理（Documents）
- PPTX 幻灯片浏览
- PDF 文档浏览
- 文本高亮和表格渲染
- 文档处理状态跟踪

### 5. 设置配置（Settings）
- LLM 模型配置（支持 OpenAI、SiliconFlow、Ollama）
- 嵌入向量模型配置
- 前端统一配置管理

## 项目结构

```
frontend/
├── src/
│   ├── views/              # 页面级组件（路由入口）
│   │   ├── HomeView.vue           # 首页（知识库列表）
│   │   └── SubjectDocsView.vue    # 主题文档列表页
│   │
│   ├── modules/            # 功能模块（按功能划分）
│   │   ├── chat/           # 聊天对话模块
│   │   │   ├── ChatView.vue
│   │   │   ├── components/        # 模块组件
│   │   │   ├── store/             # Pinia store
│   │   │   └── services/          # API 服务
│   │   │
│   │   ├── graph/          # 知识图谱模块
│   │   ├── mindmap/        # 思维导图模块
│   │   ├── documents/      # 文档管理模块
│   │   └── settings/       # 设置配置模块
│   │
│   ├── services/           # 公共服务
│   │   └── api.js          # 统一的 axios 实例
│   │
│   ├── router/             # 路由配置
│   ├── layout/             # 布局组件
│   └── styles/             # 全局样式
│
├── docs/                   # 开发文档
│   └── 前端开发规范.md     # 开发规范和模块化指南
│
└── package.json
```

## 模块说明

### Chat 模块
- **功能**：智能对话界面，支持 Agent 工具调用
- **组件**：`ChatView.vue`、`ToolCallInline.vue`
- **Store**：`chatStore.js`（消息管理）、`conversationStore.js`（对话管理）
- **Service**：`chatService.js`、`conversationService.js`

### Graph 模块
- **功能**：知识图谱可视化展示
- **组件**：`GraphViewer.vue`、`GraphCanvas.vue`、`GraphFilters.vue`
- **Store**：`graphStore.js`
- **Service**：`graphService.js`

### Mindmap 模块
- **功能**：思维导图生成和展示
- **组件**：`MindMapViewer.vue`
- **Store**：`mindmapStore.js`
- **Service**：`mindmapService.js`

### Documents 模块
- **功能**：文档浏览和管理
- **组件**：`PPTViewer/`、`RecordView.vue`
- **Store**：`documentStore.js`
- **Service**：`documentService.js`

### Settings 模块
- **功能**：系统配置管理
- **组件**：`SettingsDialog.vue`、`ConfigForm.vue`
- **Store**：`settingsStore.js`
- **Service**：`settingsService.js`

## 快速开始

### 环境要求

- Node.js 16+
- npm 或 yarn

### 安装依赖

```bash
npm install
```

### 开发模式

```bash
npm run dev
```

访问 http://localhost:5173

### 构建生产版本

```bash
npm run build
```

### 预览生产构建

```bash
npm run preview
```

## 开发规范

详细的开发规范、模块化指南和新增模块教程，请参考：[前端开发规范.md](./docs/前端开发规范.md)

### 核心原则

1. **模块化优先**：按功能划分模块，每个模块自包含组件、store、services
2. **避免全局污染**：不在顶层 `src/stores/` 或 `src/services/` 创建新文件（`api.js` 除外）
3. **相对路径导入**：模块内使用相对路径，跨模块使用 `../` 或 `../../`
4. **路由懒加载**：页面级组件使用动态导入

## 路由说明

- `/` - 首页（知识库列表）
- `/subject/:id` - 主题文档列表页
- `/chat/:id` - 对话页面

## 环境变量

创建 `.env` 文件（可选）：

```env
VITE_API_BASE_URL=http://localhost:8000
```

## 主要特性

- ✅ 模块化架构，代码组织清晰
- ✅ 响应式设计，适配不同屏幕
- ✅ 实时流式响应，提升用户体验
- ✅ 工具调用可视化，清晰展示执行过程
- ✅ 知识图谱交互式展示
- ✅ 思维导图自动生成和导出

