# 后端服务

基于 FastAPI 和 LightRAG 的 Web 应用后端。

## Agent 模式概览

后端内置了一个基于 LLM Function Calling 的 **Agent 服务**（`AgentService`），用于在单一接口中统一编排多种工具调用。通过 Agent 模式，后端可以：

- 根据用户问题自动选择是否调用工具或直接回答；
- 调用 **文档列表工具**（列出当前对话下的所有文档）；
- 调用 **知识图谱查询工具**（基于 LightRAG 的图谱检索）；
- 调用 **思维导图生成工具**（生成并保存对应对话的脑图内容）。

这些工具通过统一的注册表 `ToolRegistry` 管理，并以 OpenAI 兼容的 tools 格式暴露给上游 LLM。

## 环境要求

- Python 3.10+
- pip

macOS 可先检查：

```bash
python3 --version
```

如果 `python3` 不存在或版本低于 3.10，建议从 https://www.python.org/downloads/macos/ 安装新版 Python。Homebrew 是可选方案，不是必须。

## 安装步骤

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

启动服务：

```bash
source venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

如果需要后端热更新：

```bash
source venv/bin/activate
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Windows CMD

```cmd
python -m venv venv
venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Windows PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 配置环境变量（可选）

```bash
cp .env.example .env
```

复制后按需编辑 `.env` 文件即可。

常用 LLM 配置不再要求写入 `.env`。应用启动后可在前端设置页配置统一 API Key 和各场景模型，后端会加密保存到 `backend/data/llm_config.json`。

## 测试

访问以下 URL 测试服务是否正常：

- http://localhost:8000/ - 根路径
- http://localhost:8000/health - 健康检查
- http://localhost:8000/docs - API 文档（自动生成）

## LLM / 模型配置

后端通过 `ConfigService` 统一管理模型配置，主要能力包括：

- **统一 API Key**：当前主要支持 `siliconflow`，Key 只需保存一次，知识图谱、聊天、思维导图、嵌入向量、OCR 等场景共用。
- **加密存储**：API Key 使用 Fernet 加密保存，密钥位于 `backend/data/.encryption_key`，配置位于 `backend/data/llm_config.json`。
- **场景模型独立选择**：每个场景仍可独立选择模型、host 和 binding。
- **启动自动同步模型列表**：应用启动时如果已保存统一 API Key，会调用 SiliconFlow OpenAI 兼容接口的 `GET /models` 拉取当前账号可用模型。
- **手动刷新模型列表**：前端设置页可触发模型列表刷新，后端会把远程模型缓存进配置文件。
- **向后兼容**：历史按场景保存的 API Key 仍可读取；如果配置中存在 `openai` binding 但 host 是 SiliconFlow，会自动规范为 `siliconflow`。

相关接口：

```http
GET  /api/settings/llm-config
GET  /api/settings/model-lists
POST /api/settings/llm-config/{scene}
POST /api/settings/providers/siliconflow/api-key
POST /api/settings/providers/siliconflow/models/refresh
```

`GET /api/settings/llm-config` 不会返回明文 API Key，只会返回 `providers.siliconflow.has_api_key`、上次同步时间和模型列表。

## Cheatsheet 生成（后端）

对话路由中提供 Cheatsheet 生成与管理接口，用于基于当前 subject 下已处理完成的 PDF / PPTX 讲义生成可打印 Markdown 速查表。该功能直接使用聊天场景 LLM 配置，不属于 Agent tool。

相关接口：

```http
GET    /api/conversations/{conversation_id}/cheatsheet
PATCH  /api/conversations/{conversation_id}/cheatsheet
DELETE /api/conversations/{conversation_id}/cheatsheet
POST   /api/conversations/{conversation_id}/cheatsheet/generate
POST   /api/conversations/{conversation_id}/cheatsheet/pdf
```

生成接口返回 `text/event-stream`，事件包括 `progress`、`warning`、`chunk`、`done`、`error`。生成结果保存到 `backend/uploads/conversations/{conversation_id}/cheatsheet.json`。PDF 导出接口使用 Playwright 显式生成多页，并在导出前修复旧版 token/短行换行内容。详细说明见 `../docs/feature/feature-cheatsheet-generation.md` 和 `../docs/spec/API接口文档.md`。

## Agent 模式技术说明（后端）

后端的 Agent 模式主要由以下几个核心组件组成：

- **工具定义与注册**：在 `app/services/agent/tools/` 目录中定义具体工具（如思维导图工具、查询工具），并通过 `ToolRegistry` 统一注册、转换为 OpenAI tools / function calling 所需的 JSON Schema 格式。
- **AgentService 调度**：`AgentService` 负责：
  - 组装 system prompt 和对话历史；
  - 将工具列表作为 `tools` 传给 LLM；
  - 解析 LLM 返回的 `tool_calls` 结构，依次执行对应的工具；
  - 把工具结果封装为 `tool` 消息，再次发给 LLM 生成最终回答。
- **多轮工具调用**：Agent 支持多轮工具调用（例如先列出文档，再基于选择结果生成思维导图），并在 `process_user_query` 中通过循环控制最大轮数和消息上下文。

通过这一套机制，后端可以较为容易地扩展新的工具，只需补充工具定义和处理函数，而无需改动 Agent 主流程。
