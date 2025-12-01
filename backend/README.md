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

- Python 3.9+
- pip

## 安装步骤

1. 创建虚拟环境：
```bash
python -m venv venv
```

2. 激活虚拟环境：
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 配置环境变量：
```bash
# 复制示例文件
copy .env.example .env

# 编辑 .env 文件，填入你的配置
```

5. 启动服务：
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 测试

访问以下 URL 测试服务是否正常：

- http://localhost:8000/ - 根路径
- http://localhost:8000/health - 健康检查
- http://localhost:8000/docs - API 文档（自动生成）

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
