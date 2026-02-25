import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
import app.config as config

# 添加 LightRAG 路径到 sys.path（必须在导入之前）
LIGHTRAG_BASE_PATH = Path(__file__).parent.parent.parent.parent / "LightRAG"
if str(LIGHTRAG_BASE_PATH) not in sys.path:
    sys.path.insert(0, str(LIGHTRAG_BASE_PATH))

# 现在可以导入 LightRAG
from lightrag import LightRAG
from lightrag.kg.shared_storage import initialize_pipeline_status, get_namespace_data
from lightrag.utils import EmbeddingFunc


class LightRAGService:
    """LightRAG 服务封装，支持对话隔离"""
    
    _instance: Optional['LightRAGService'] = None
    _lightrag_instances: Dict[str, LightRAG] = {}  # conversation_id -> LightRAG 实例
    _initialized_instances: Dict[str, bool] = {}  # conversation_id -> 是否已初始化
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._lightrag_instances = {}
            cls._instance._initialized_instances = {}
        return cls._instance
    
    def clear_all_instances(self):
        """清除所有已缓存的 LightRAG 实例（配置更新时调用）"""
        self._lightrag_instances.clear()
        self._initialized_instances.clear()
        # print("[LightRAG] 已清除所有缓存的实例，下次使用时将使用新配置重新创建")
    
    def get_chat_llm_func(self):
        """获取聊天场景的 LLM 函数（用于查询）"""
        return self._get_llm_func(use_chat_config=True)
    
    async def _init_lightrag_for_conversation(self, conversation_id: str) -> LightRAG:
        """为指定对话初始化 LightRAG 实例
        
        Args:
            conversation_id: 对话ID（可能是 conversation_id 或 subject_id）
            
        Returns:
            LightRAG 实例
        """
        # 尝试获取 conversation_id 对应的 subject_id
        # 如果 conversation_id 本身就是 subject_id（用于文档处理），则直接使用
        # 如果是 conversation_id，则尝试获取其 subject_id
        target_id = conversation_id
        try:
            from app.services.conversation_service import ConversationService
            conv_service = ConversationService()
            conversation = conv_service.get_conversation(conversation_id)
            if conversation and conversation.get("subject_id"):
                target_id = conversation["subject_id"]
        except Exception:
            # 如果获取失败，使用原始的 conversation_id（向后兼容）
            target_id = conversation_id
        
        # 如果已经初始化（使用 target_id 作为 key），直接返回
        if target_id in self._lightrag_instances and self._initialized_instances.get(target_id, False):
            return self._lightrag_instances[target_id]
        
        # 使用 data/<target_id> 作为工作目录（target_id 可能是 subject_id 或 conversation_id）
        # 知识图谱文件直接保存在此目录下
        working_dir = Path(config.settings.data_dir) / target_id
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置 LLM 函数
        llm_func = self._get_llm_func()
        
        # 配置 Embedding 函数
        embedding_func = self._get_embedding_func()
        
        # 创建 LightRAG 实例（不设置 workspace，避免创建嵌套子目录）
        lightrag = LightRAG(
            working_dir=str(working_dir),
            llm_model_func=llm_func,
            embedding_func=embedding_func,
            kv_storage=config.settings.lightrag_kv_storage,
            vector_storage=config.settings.lightrag_vector_storage,
            graph_storage=config.settings.lightrag_graph_storage,
            doc_status_storage=config.settings.lightrag_doc_status_storage,
            chunk_token_size=600,
            chunk_overlap_token_size=50,
            default_llm_timeout=config.settings.timeout,
        )
        
        # 初始化存储
        await lightrag.initialize_storages()
        await initialize_pipeline_status()
        
        # 缓存实例：使用 target_id 作为 key（确保同一 subject_id 下的多个 conversation_id 共享同一个实例）
        # 同时，也使用 conversation_id 作为 key（方便查找）
        self._lightrag_instances[target_id] = lightrag
        self._initialized_instances[target_id] = True
        # 如果 target_id 和 conversation_id 不同，也缓存 conversation_id 的映射
        if target_id != conversation_id:
            self._lightrag_instances[conversation_id] = lightrag
            self._initialized_instances[conversation_id] = True
        
        return lightrag
    
    def _get_llm_func(self, use_chat_config: bool = False):
        """获取 LLM 函数
        
        Args:
            use_chat_config: 如果为 True，使用聊天场景配置；否则使用知识图谱场景配置
        
        支持:
        - openai: OpenAI API 或兼容 OpenAI API 的服务（如硅基流动）
        - ollama: Ollama 本地模型
        """
        from app.services.config_service import config_service
        
        # 清除配置缓存，确保读取最新配置
        config_service._config_cache = None
        
        if use_chat_config:
            # 使用聊天场景的配置（用于查询）
            scene_config = config_service.get_config("chat")
            binding = scene_config.get("binding", config.settings.chat_llm_binding)
            model = scene_config.get("model", config.settings.chat_llm_model)
            api_key = scene_config.get("api_key", config.settings.chat_llm_binding_api_key)
            host = scene_config.get("host", config.settings.chat_llm_binding_host)
            error_msg = "聊天 LLM API Key 未配置"
            print(f"🔧 [LightRAG] 使用聊天配置: binding={binding}, model={model}, host={host[:50]}...")
        else:
            # 使用知识图谱场景的配置（用于文档抽取）
            scene_config = config_service.get_config("knowledge_graph")
            binding = scene_config.get("binding", config.settings.kg_llm_binding)
            model = scene_config.get("model", config.settings.kg_llm_model)
            api_key = scene_config.get("api_key", config.settings.kg_llm_binding_api_key)
            host = scene_config.get("host", config.settings.kg_llm_binding_host)
            error_msg = "知识图谱 LLM API Key 未配置"
            print(f"🔧 [LightRAG] 使用知识图谱配置: binding={binding}, model={model}, host={host[:50]}...")
        
        if binding == "openai" or binding == "siliconflow":
            from lightrag.llm.openai import openai_complete_if_cache
            
            if not api_key:
                raise ValueError(error_msg)

            is_siliconcloud_host = host.startswith("https://api.siliconflow.cn")
            
            # 支持 OpenAI 兼容 API（如硅基流动）
            # 使用 openai_complete_if_cache 函数，支持自定义模型名
            def llm_func(prompt, **kwargs):
                # 移除 LightRAG 内部参数（这些参数不应该传递给实际的 API 调用）
                kwargs.pop('api_base', None)
                kwargs.pop('_priority', None)  # LightRAG 内部优先级参数
                kwargs.pop('_timeout', None)  # LightRAG 内部超时参数
                kwargs.pop('_queue_timeout', None)  # LightRAG 内部队列超时参数

                if is_siliconcloud_host:
                    existing_extra_body = kwargs.get("extra_body") or {}
                    if "thinking_budget" not in existing_extra_body:
                        extra_body = dict(existing_extra_body)
                        extra_body["thinking_budget"] = 1024
                        kwargs["extra_body"] = extra_body
                    else:
                        kwargs["extra_body"] = existing_extra_body

                # 使用配置的模型名，传递 base_url 和 api_key
                return openai_complete_if_cache(
                    model=model,
                    prompt=prompt,
                    api_key=api_key,
                    base_url=host,
                    **kwargs
                )
            return llm_func
        elif binding == "ollama":
            from lightrag.llm.ollama import ollama_model_complete
            
            return lambda prompt, **kwargs: ollama_model_complete(
                prompt,
                model=model,
                host=host,
                timeout=config.settings.timeout,
                **kwargs
            )
        else:
            raise ValueError(f"不支持的 LLM binding: {binding}")
    
    def _get_embedding_func(self) -> EmbeddingFunc:
        """获取 Embedding 函数
        
        支持:
        - ollama: Ollama 本地模型
        - openai: OpenAI API 或兼容 OpenAI API 的服务
        - siliconflow: 硅基流动 Embedding API（使用 OpenAI 兼容接口）
        """
        if config.settings.embedding_binding == "ollama":
            from lightrag.llm.ollama import ollama_embed
            
            return EmbeddingFunc(
                embedding_dim=config.settings.embedding_dim,
                max_token_size=8192,
                func=lambda texts: ollama_embed(
                    texts,
                    embed_model=config.settings.embedding_model,
                    host=config.settings.embedding_binding_host,
                )
            )
        elif config.settings.embedding_binding == "openai":
            from lightrag.llm.openai import openai_embed
            
            api_key = config.settings.llm_binding_api_key
            if not api_key:
                raise ValueError("LLM_BINDING_API_KEY 未配置（Embedding 需要）")
            
            # 支持 OpenAI 兼容 API（如硅基流动）
            from lightrag.llm.openai import openai_embed
            
            return EmbeddingFunc(
                embedding_dim=config.settings.embedding_dim,
                max_token_size=8192,
                func=lambda texts: openai_embed(
                    texts,
                    api_key=api_key,
                    base_url=config.settings.llm_binding_host,
                )
            )
        elif config.settings.embedding_binding in ("siliconflow", "siliconcloud"):
            # 统一使用 siliconflow，使用 openai_embed（硅基流动是 OpenAI 兼容的）
            from lightrag.llm.openai import openai_embed
            from app.services.config_service import config_service
            
            # 从配置服务读取 embedding 配置（优先使用配置服务的配置）
            embedding_config = config_service.get_config("embedding")
            
            # 使用配置服务的 API Key，如果没有则使用全局的（向后兼容）
            api_key = embedding_config.get("api_key") or config.settings.llm_binding_api_key
            if not api_key:
                raise ValueError("Embedding API Key 未配置（硅基流动需要）")
            
            # 使用配置服务的模型和 host
            embedding_model = embedding_config.get("model") or config.settings.embedding_model
            embedding_host = embedding_config.get("host") or config.settings.llm_binding_host
            
            # 确保 host 以 /v1 结尾（openai_embed 会自动添加 /embeddings）
            if not embedding_host.endswith("/v1"):
                if embedding_host.endswith("/v1/embeddings"):
                    embedding_host = embedding_host.replace("/v1/embeddings", "/v1")
                else:
                    embedding_host = "https://api.siliconflow.cn/v1"
            
            return EmbeddingFunc(
                embedding_dim=config.settings.embedding_dim,
                max_token_size=8192,
                func=lambda texts: openai_embed(
                    texts,
                    model=embedding_model,
                    api_key=api_key,
                    base_url=embedding_host,
                )
            )
        else:
            raise ValueError(f"不支持的 Embedding binding: {config.settings.embedding_binding}")
    
    async def get_lightrag_for_conversation(self, conversation_id: str) -> LightRAG:
        """获取指定对话的 LightRAG 实例（延迟初始化）
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            LightRAG 实例
        """
        return await self._init_lightrag_for_conversation(conversation_id)
    
    async def insert_document(self, conversation_id: str, text: str, doc_id: Optional[str] = None) -> str:
        """异步插入文档到指定对话
        
        Args:
            conversation_id: 对话ID
            text: 文档文本内容
            doc_id: 文档ID（可选）
            
        Returns:
            track_id: LightRAG 处理跟踪ID
        """
        lightrag = await self.get_lightrag_for_conversation(conversation_id)
        # ainsert 使用 input 参数，doc_id 使用 ids 参数
        if doc_id:
            track_id = await lightrag.ainsert(input=text, ids=doc_id)
        else:
            track_id = await lightrag.ainsert(input=text)
        return track_id
    
    async def insert_file(self, conversation_id: str, file_path: str, doc_id: Optional[str] = None) -> str:
        """异步插入文件到指定对话
        
        Args:
            conversation_id: 对话ID
            file_path: 文件路径
            doc_id: 文档ID（可选）
            
        Returns:
            track_id: LightRAG 处理跟踪ID
        """
        lightrag = await self.get_lightrag_for_conversation(conversation_id)
        if doc_id:
            track_id = await lightrag.ainsert(file_paths=file_path, ids=doc_id)
        else:
            track_id = await lightrag.ainsert(file_paths=file_path)
        return track_id
    
    async def get_processing_progress(self, doc_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取处理进度信息
        
        Args:
            doc_id: 文档ID（可选），如果提供则只返回该文档的进度
            
        Returns:
            进度信息字典，包含 stage, current, total, percentage 等
        """
        try:
            pipeline_status = await get_namespace_data("pipeline_status", first_init=False)
            if not pipeline_status:
                return None
            
            progress = pipeline_status.get("progress")
            if not progress:
                return None
            
            # 如果指定了 doc_id，只返回匹配的进度
            if doc_id and progress.get("doc_id") != doc_id:
                return None
            
            return progress
        except Exception as e:
            # 如果 pipeline_status 未初始化或出错，返回 None
            return None
    
    async def query(self, conversation_id: str, query: str, mode: str = "mix", conversation_history: Optional[List[Dict[str, str]]] = None) -> Any:
        """在指定对话的知识图谱中查询（使用聊天场景配置）
        
        Args:
            conversation_id: 对话ID
            query: 查询文本
            mode: 查询模式（naive/local/global/mix）
            conversation_history: 对话历史，格式: [{"role": "user/assistant", "content": "..."}]
            
        Returns:
            查询结果
        """
        lightrag = await self.get_lightrag_for_conversation(conversation_id)
        
        # 临时替换 LLM 函数为聊天配置（用于查询）
        original_llm_func = lightrag.llm_model_func
        chat_llm_func = self._get_llm_func(use_chat_config=True)
        lightrag.llm_model_func = chat_llm_func
        
        from lightrag import QueryParam
        param = QueryParam(mode=mode)
        if conversation_history:
            param.conversation_history = conversation_history
        
        result = await lightrag.aquery(query, param=param)
        
        # 恢复原始的 LLM 函数（用于文档抽取）
        lightrag.llm_model_func = original_llm_func
        
        return result
