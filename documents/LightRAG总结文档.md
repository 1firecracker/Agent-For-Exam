# LightRAG 框架总结文档

## 1. 项目概述

LightRAG 是一个基于知识图谱技术的简单且快速的检索增强生成（RAG）系统。它采用高度模块化的设计，支持多种存储后端和 LLM 提供商，提供完整的 RAG 功能，包括文档处理、知识图谱构建、查询检索和响应生成。

### 1.1 核心特性

- **模块化架构**：存储后端、LLM 提供商、嵌入模型均可插拔
- **多存储支持**：KV 存储、向量存储、图存储、文档状态存储
- **多种查询模式**：local、global、hybrid、naive、mix
- **异步处理**：支持高并发文档处理和查询
- **Web 界面**：提供图形化界面用于文档管理和知识图谱可视化
- **API 服务**：完整的 REST API 和 Ollama 兼容接口

## 2. 项目结构

### 2.1 目录结构

```
LightRAG/
├── lightrag/                    # 核心代码目录
│   ├── lightrag.py              # LightRAG 主类（145KB）
│   ├── base.py                  # 基础类定义（31KB）
│   ├── operate.py               # 操作实现类（169KB）
│   ├── utils.py                 # 工具函数集合（109KB）
│   ├── utils_graph.py           # 图相关工具函数（44KB）
│   ├── prompt.py                # 提示词模板管理（29KB）
│   ├── rerank.py                # 重排序功能实现（12KB）
│   ├── kg/                      # 知识图谱存储模块
│   ├── llm/                     # 大语言模型集成模块
│   ├── api/                     # API 服务模块
│   └── tools/                   # 工具模块
├── lightrag_webui/              # Web 用户界面
├── examples/                    # 示例代码
├── tests/                       # 测试代码
├── docs/                        # 文档
├── reproduce/                   # 复现实验代码
└── k8s-deploy/                  # Kubernetes 部署配置
```

### 2.2 核心模块详解

#### 2.2.1 LightRAG 主类

**位置**: `lightrag/lightrag.py`

**主要功能**:
- 文档插入和处理（`insert()`, `ainsert()`）
- 文档查询（`query()`, `aquery()`, `aquery_data()`）
- 知识图谱管理
- 存储初始化和管理

**关键配置参数**:
- `working_dir`: 工作目录
- `kv_storage`: KV 存储后端类型
- `vector_storage`: 向量存储后端类型
- `graph_storage`: 图存储后端类型
- `doc_status_storage`: 文档状态存储类型
- `llm_model_func`: LLM 模型函数
- `embedding_func`: 嵌入函数
- `top_k`: 检索数量
- `chunk_token_size`: 文本块大小（默认 1200 tokens）
- `chunk_overlap_token_size`: 块重叠大小（默认 100 tokens）

#### 2.2.2 存储模块 (`lightrag/kg/`)

**四种存储类型**:

1. **KV 存储 (键值存储)**
   - `json_kv_impl.py` - JSON 文件 KV 存储（默认）
   - `redis_impl.py` - Redis KV 存储
   - `mongo_impl.py` - MongoDB KV 存储
   - `postgres_impl.py` - PostgreSQL KV 存储

2. **向量存储**
   - `nano_vector_db_impl.py` - 轻量级向量数据库（默认）
   - `faiss_impl.py` - Facebook FAISS 向量存储
   - `milvus_impl.py` - Milvus 向量数据库
   - `qdrant_impl.py` - Qdrant 向量数据库
   - `postgres_impl.py` - PostgreSQL 向量存储（pgvector）
   - `mongo_impl.py` - MongoDB 向量存储

3. **图存储**
   - `networkx_impl.py` - NetworkX 图存储（默认）
   - `neo4j_impl.py` - Neo4j 图数据库
   - `memgraph_impl.py` - Memgraph 图数据库
   - `postgres_impl.py` - PostgreSQL 图存储（Apache AGE）
   - `mongo_impl.py` - MongoDB 图存储

4. **文档状态存储**
   - `json_doc_status_impl.py` - JSON 文件文档状态存储（默认）
   - `redis_impl.py` - Redis 文档状态存储
   - `mongo_impl.py` - MongoDB 文档状态存储
   - `postgres_impl.py` - PostgreSQL 文档状态存储

#### 2.2.3 LLM 集成模块 (`lightrag/llm/`)

**支持的 LLM 提供商**:
- `openai.py` - OpenAI API 集成
- `azure_openai.py` - Azure OpenAI 集成
- `anthropic.py` - Anthropic Claude 集成
- `ollama.py` - Ollama 本地模型集成（推荐用于本地部署）
- `hf.py` - Hugging Face 模型集成
- `zhipu.py` - 智谱 AI 集成
- `siliconcloud.py` - 硅基流动集成
- `jina.py` - Jina AI 集成
- `bedrock.py` - AWS Bedrock 集成
- `lollms.py` - LollMS 集成
- `nvidia_openai.py` - NVIDIA NIM 集成

#### 2.2.4 API 服务模块 (`lightrag/api/`)

**API 路由**:
- `lightrag_server.py` - 主服务器应用
- `routers/document_routes.py` - 文档处理路由
- `routers/query_routes.py` - 查询路由
- `routers/graph_routes.py` - 图谱操作路由
- `routers/ollama_api.py` - Ollama 兼容 API

## 3. 核心工作流程

### 3.1 文档处理流程

#### 3.1.1 流程概述

```
用户上传文档（PPTX/PPT/PDF）
↓
文档上传到 inputs 目录
↓
生成 track_id 跟踪处理状态
↓
文档分块处理（chunk_token_size=1200, overlap=100）
↓
文本块向量化并存储（chunks_vdb, text_chunks）
↓
实体和关系提取（使用 LLM）
↓
知识图谱构建（entities_vdb, relationships_vdb, chunk_entity_relation_graph）
↓
文档状态更新为 PROCESSED
```

#### 3.1.2 关键函数调用路径

```
文档上传
↓
lightrag/api/routers/document_routes.py:insert_text()
↓
lightrag/lightrag.py:ainsert()
↓
lightrag/lightrag.py:apipeline_enqueue_documents()
↓
lightrag/lightrag.py:apipeline_process_enqueue_documents()
↓
lightrag/lightrag.py:process_document()
↓
├── chunking_func() - 文档分块
├── chunks_vdb.upsert() - 向量存储
├── text_chunks.upsert() - 文本存储
└── _process_extract_entities() - 实体提取
    ↓
    lightrag/operate.py:extract_entities()
    ↓
    lightrag/operate.py:_process_single_content() - 单块处理
    ↓
    lightrag/operate.py:use_llm_func_with_cache() - LLM 实体提取
```

#### 3.1.3 支持的文档格式

- **文本文件**: TXT, MD, LOG, CONF, INI, PROPERTIES, SQL, BAT, SH
- **办公文档**: DOCX, PPTX, XLSX
- **电子书**: PDF, EPUB, ODT, RTF
- **网页文件**: HTML, HTM
- **代码文件**: C, CPP, PY, JAVA, JS, TS, SWIFT, GO, RB, PHP, CSS, SCSS, LESS
- **数据文件**: CSV, JSON, XML, YAML, YML
- **学术文件**: TEX

### 3.2 查询检索流程

#### 3.2.1 查询模式

LightRAG 支持 6 种查询模式：

1. **local**: 基于局部上下文的检索
   - 使用低层次关键词检索实体
   - 适用于具体、细粒度的问题

2. **global**: 基于全局知识的检索
   - 使用高层次关键词检索关系
   - 适用于抽象、概括性的问题

3. **hybrid**: 混合检索模式
   - 结合 local 和 global 模式
   - 提供更全面的上下文

4. **naive**: 基础向量检索
   - 仅使用向量相似度检索文本块
   - 不涉及知识图谱

5. **mix**: 知识图谱和向量检索混合（推荐）
   - 结合知识图谱和向量检索
   - 提供最全面的检索结果

6. **bypass**: 绕过 RAG，直接使用 LLM
   - 不进行检索，仅基于对话历史

#### 3.2.2 查询流程函数调用路径

```
用户查询
↓
lightrag/api/routers/query_routes.py:query_text()
↓
lightrag/lightrag.py:aquery()
↓
lightrag/operate.py:kg_query()
↓
├── get_keywords_from_query() - 提取关键词
│   ├── 高层次关键词 (hl_keywords)
│   └── 低层次关键词 (ll_keywords)
├── _build_query_context() - 构建查询上下文
│   ├── _perform_kg_search() - 执行知识图谱检索
│   ├── _apply_token_truncation() - Token 截断
│   ├── _merge_chunks() - 合并文本块
│   └── _build_llm_context() - 构建 LLM 上下文
└── use_llm_func_with_cache() - 调用 LLM 生成响应
```

#### 3.2.3 检索融合排序过程

1. **关键词提取** (`get_keywords_from_query`)
   - 提取高层次关键词: 用于检索关系
   - 提取低层次关键词: 用于检索实体

2. **知识图谱检索** (`_perform_kg_search`)
   - **实体向量检索**: 从 `entities_vdb` 中检索相关实体
   - **关系向量检索**: 从 `relationships_vdb` 中检索相关关系
   - **文本块检索**: 从 `chunks_vdb` 中检索相关文本块

3. **融合排序过程**
   - **向量相似度计算**: 计算查询与检索结果的余弦相似度
   - **图结构分析**: 分析实体之间的关系强度
   - **重排序** (如果启用): 使用重排序模型对结果进行二次排序
   - **上下文构建**: 根据 token 限制智能选择最相关的实体、关系和文本块

4. **LLM 生成响应**
   - **提示词构建**: 使用 `prompt.py` 中的模板构建最终提示词
   - **LLM 调用**: 调用配置的 LLM 生成自然语言响应
   - **引用生成**: 自动生成引用信息，标注信息来源

## 4. 关键技术特性

### 4.1 实体和关系提取

**提取流程**:
1. 文档分块后，对每个文本块使用 LLM 提取实体和关系
2. 实体类型包括: Person, Organization, Location, Concept 等
3. 使用缓存机制避免重复提取相同内容
4. 支持多次迭代提取（`entity_extract_max_gleaning`）

**提取阶段**:
- **提取阶段**: 从文本块中提取实体和关系
- **合并阶段**: 合并相同或相似的实体和关系

### 4.2 知识图谱构建

**图谱组成**:
- **实体节点**: 从文档中提取的实体，存储在 `entities_vdb` 和 `chunk_entity_relation_graph`
- **关系边**: 实体之间的关系，存储在 `relationships_vdb` 和 `chunk_entity_relation_graph`
- **文本块**: 原始文档块，存储在 `chunks_vdb` 和 `text_chunks`

**图谱操作**:
- 实体和关系的创建、编辑、删除
- 实体合并功能
- 自定义知识图谱插入
- 图可视化

### 4.3 存储架构

LightRAG 使用 4 种类型的存储：

1. **KV_STORAGE**
   - 存储 LLM 响应缓存
   - 存储文本块内容 (`text_chunks`)
   - 存储完整文档 (`full_docs`)
   - 存储文档实体和关系列表

2. **VECTOR_STORAGE**
   - 存储实体向量 (`entities_vdb`)
   - 存储关系向量 (`relationships_vdb`)
   - 存储文本块向量 (`chunks_vdb`)

3. **GRAPH_STORAGE**
   - 存储实体关系图 (`chunk_entity_relation_graph`)

4. **DOC_STATUS_STORAGE**
   - 存储文档处理状态 (`doc_status`)

### 4.4 异步处理和并发控制

**并发参数**:
- `MAX_PARALLEL_INSERT`: 并行处理文档数量（默认: 2）
- `MAX_ASYNC`: 最大并发 LLM 请求数（默认: 4）

**处理优先级**:
1. 查询操作（优先级 5）
2. 合并操作（优先级 3）
3. 提取操作（优先级 1）

**异步机制**:
- 所有主要操作都支持异步执行
- 使用 `asyncio.Semaphore` 控制并发数量
- 批量操作减少 I/O 开销

### 4.5 缓存机制

**LLM 响应缓存**:
- 避免重复计算相同的 LLM 请求
- 使用内容哈希作为缓存键
- 支持实体提取缓存（`enable_llm_cache_for_entity_extract`）

**向量缓存**:
- 可选启用（`embedding_cache_config`）
- 基于相似度阈值判断是否使用缓存

## 5. 配置系统

### 5.1 环境变量配置 (.env)

**服务器配置**:
```bash
HOST=0.0.0.0
PORT=9621
WORKERS=2
```

**LLM 配置**:
```bash
LLM_BINDING=openai  # 或 ollama, azure_openai 等
LLM_MODEL=gpt-4o-mini
LLM_BINDING_HOST=https://api.openai.com/v1
LLM_BINDING_API_KEY=your-api-key
MAX_ASYNC=4
TIMEOUT=150
```

**嵌入配置**:
```bash
EMBEDDING_BINDING=ollama
EMBEDDING_MODEL=bge-m3:latest
EMBEDDING_DIM=1024
EMBEDDING_BINDING_HOST=http://localhost:11434
```

**存储配置**:
```bash
LIGHTRAG_KV_STORAGE=JsonKVStorage
LIGHTRAG_VECTOR_STORAGE=NanoVectorDBStorage
LIGHTRAG_GRAPH_STORAGE=NetworkXStorage
LIGHTRAG_DOC_STATUS_STORAGE=JsonDocStatusStorage
```

**查询配置**:
```bash
TOP_K=60
CHUNK_TOP_K=60
MAX_ENTITY_TOKENS=800
MAX_RELATION_TOKENS=800
MAX_TOTAL_TOKENS=8000
COSINE_THRESHOLD=0.2
```

### 5.2 工作空间隔离

LightRAG 支持工作空间（workspace）概念，用于在不同实例间实现数据隔离：

- **本地文件数据库**: 通过工作空间子目录实现隔离
- **集合数据库**: 通过在工作空间名称前添加前缀实现隔离
- **关系数据库**: 通过添加 `workspace` 字段实现逻辑隔离
- **图数据库**: 通过标签实现逻辑隔离

## 6. API 接口

### 6.1 文档管理 API

- `POST /documents/upload` - 上传文档
- `POST /documents/text` - 插入文本
- `POST /documents/scan` - 扫描输入目录
- `GET /documents` - 获取文档列表
- `GET /track_status/{track_id}` - 查询处理状态
- `DELETE /documents/{doc_id}` - 删除文档

### 6.2 查询 API

- `POST /query` - 查询（JSON 响应）
- `POST /query/stream` - 查询（流式响应）

### 6.3 图谱操作 API

- `GET /graph/entities` - 获取实体列表
- `GET /graph/relationships` - 获取关系列表
- `POST /graph/entities` - 创建实体
- `DELETE /graph/entities/{entity_id}` - 删除实体

## 7. 性能优化

### 7.1 推荐配置

**LLM 要求**:
- 参数量至少 32B
- 上下文长度至少 32KB（推荐 64KB）
- 索引阶段不建议选择推理模型
- 查询阶段建议选择能力更强的模型

**Embedding 模型**:
- 推荐: BAAI/bge-m3, text-embedding-3-large
- **重要**: 索引前必须确定 Embedding 模型，查询阶段必须使用相同模型

**Reranker 模型**:
- 推荐: BAAI/bge-reranker-v2-m3
- 启用后推荐使用 "mix" 模式作为默认查询模式

### 7.2 存储选择建议

**开发环境**:
- 使用默认的 JSON 文件存储
- 配置本地 Ollama 或使用云 API

**生产环境**:
- KV 存储: Redis
- 向量存储: Milvus 或 Qdrant
- 图存储: Neo4j
- 或使用 PostgreSQL（pgvector + AGE）一体化方案

## 8. 多模态支持

LightRAG 现已与 **RAG-Anything** 实现无缝集成，支持多模态文档处理：

**支持的内容类型**:
- 文本
- 图片
- 表格
- 数学公式

**支持的文档格式**:
- PDF、Office 文档（DOC/DOCX/PPT/PPTX/XLS/XLSX）
- 图片文件

**主要特性**:
- 端到端多模态流程
- 通用文档支持
- 专业内容分析
- 多模态知识图谱
- 混合智能检索

## 9. 总结

LightRAG 采用高度模块化的设计，核心优势在于：

1. **灵活性**: 支持多种存储后端和 LLM 提供商
2. **可扩展性**: 插件化架构便于功能扩展
3. **性能**: 异步处理和批量操作优化
4. **易用性**: 提供 Web 界面和丰富的 API
5. **生产就绪**: 支持容器化部署和 Kubernetes

这个框架为构建企业级 RAG 应用提供了完整的基础设施，同时保持了足够的灵活性来适应不同的业务需求。

