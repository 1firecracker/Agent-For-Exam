"""知识图谱服务"""
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
from app.services.lightrag_service import LightRAGService
from app.services.document_service import DocumentService
from app.services.memory_service import MemoryService


class GraphService:
    """知识图谱服务，封装 LightRAG 查询功能"""
    
    def __init__(self):
        self.lightrag_service = LightRAGService()
        self.document_service = DocumentService()
        from app.services.conversation_service import ConversationService
        self.conversation_service = ConversationService()
        self.memory_service = MemoryService()
    
    def _parse_file_path_to_doc_info(self, file_path: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        """解析 file_path 到文档信息
        
        Args:
            file_path: 文件路径（如 "uploads/conversations/{conversation_id}/documents/{file_id}.pptx"）
            conversation_id: 对话ID
            
        Returns:
            文档信息字典，包含 file_id 和 filename，如果无法解析返回 None
        """
        if not file_path or file_path == "unknown_source":
            return None
        
        try:
            # 从路径中提取 file_id
            # 路径格式：uploads/conversations/{conversation_id}/documents/{file_id}.{ext}
            path_obj = Path(file_path)
            if path_obj.suffix:  # 有扩展名
                file_id = path_obj.stem  # 文件名（不含扩展名）
            else:
                return None
            
            # 获取文档信息
            status = self.document_service._load_status(conversation_id)
            for doc_id, doc_data in status.get("documents", {}).items():
                if doc_id == file_id:
                    return {
                        "file_id": doc_id,
                        "filename": doc_data.get("filename", path_obj.name),
                        "file_type": path_obj.suffix.lower()
                    }
            
            return None
        except Exception:
            return None
    
    async def _get_source_chunks_info(self, lightrag, source_id: str, conversation_id: str = None) -> List[Dict[str, Any]]:
        """从 source_id 获取 chunk 信息，用于映射到文档
        
        Args:
            lightrag: LightRAG 实例
            source_id: source_id（可能是多个 chunk_id 用分隔符连接）
            conversation_id: 对话ID（可选，用于解析文档信息）
            
        Returns:
            chunk 信息列表，包含 file_id 和 page_index（如果可用）
        """
        if not source_id:
            return []
        
        chunks_info = []
        try:
            # source_id 可能是多个 chunk_id 用 GRAPH_FIELD_SEP 分隔
            # 使用正确的分隔符：GRAPH_FIELD_SEP = "<SEP>"
            from lightrag.constants import GRAPH_FIELD_SEP
            chunk_ids = source_id.split(GRAPH_FIELD_SEP) if GRAPH_FIELD_SEP in source_id else [source_id]
            
            for chunk_id in chunk_ids:
                if not chunk_id or not chunk_id.startswith("chunk-"):
                    continue
                
                # 从 text_chunks 获取 chunk 信息
                try:
                    chunk_data = await lightrag.text_chunks.get_by_id(chunk_id)
                    if chunk_data:
                        file_path = chunk_data.get("file_path", "")
                        chunk_info = {
                            "chunk_id": chunk_id,
                            "file_path": file_path,
                            "full_doc_id": chunk_data.get("full_doc_id", ""),
                            "chunk_order_index": chunk_data.get("chunk_order_index", 0),
                        }
                        
                        # 尝试从 chunk_data 中获取 page_index 和 file_id
                        # 1. 先检查 chunk_data 中是否直接存储了
                        page_index = chunk_data.get("page_index") or chunk_data.get("page_number") or chunk_data.get("slide_number")
                        
                        # 2. 从 chunk 内容中解析页面标记和文件ID
                        chunk_content = chunk_data.get("content", "")
                        if chunk_content:
                            import re
                        # 优先解析完整格式：[FILE:{file_id}][PAGE/SLIDE:{index}]
                        full_match = re.search(r'\[FILE:([^\]]+)\]\[(?:PAGE|SLIDE):(\d+)\]', chunk_content)
                        if full_match:
                            file_id_from_content = full_match.group(1)
                            page_index = int(full_match.group(2))
                            # 如果提供了 conversation_id，直接使用从内容中提取的 file_id
                            if conversation_id:
                                chunk_info["file_id"] = file_id_from_content
                        else:
                            # 兼容旧格式：分别查找 [FILE:{file_id}]、[PAGE:N] 或 [SLIDE:N]
                            if page_index is None:
                                page_match = re.search(r'\[PAGE:(\d+)\]', chunk_content)
                                slide_match = re.search(r'\[SLIDE:(\d+)\]', chunk_content)
                            if page_match:
                                page_index = int(page_match.group(1))
                            elif slide_match:
                                page_index = int(slide_match.group(1))
                            
                            # 如果还没有 file_id，尝试从内容中提取
                            if conversation_id and not chunk_info.get("file_id"):
                                file_match = re.search(r'\[FILE:([^\]]+)\]', chunk_content)
                                if file_match:
                                    chunk_info["file_id"] = file_match.group(1)
                    
                        if page_index is not None:
                            chunk_info["page_index"] = int(page_index)
                        
                        # 如果提供了 conversation_id 且还没有 file_id，尝试从 file_path 解析
                        if conversation_id and not chunk_info.get("file_id") and file_path and file_path != "unknown_source":
                            doc_info = self._parse_file_path_to_doc_info(file_path, conversation_id)
                            if doc_info:
                                chunk_info["file_id"] = doc_info["file_id"]
                                chunk_info["filename"] = doc_info["filename"]
                        
                        chunks_info.append(chunk_info)
                except Exception:
                    continue
        except Exception:
            pass
        
        return chunks_info
    
    async def get_all_entities(self, conversation_id: str) -> List[Dict[str, Any]]:
        """获取对话的所有实体
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            实体列表
        """
        lightrag = await self.lightrag_service.get_lightrag_for_conversation(conversation_id)
        
        # 获取所有节点（实体）
        entities = await lightrag.chunk_entity_relation_graph.get_all_nodes()
        
        # entities 已经是 list[dict] 格式
        entity_list = []
        for entity_data in entities:
            # entity_data 是字典，id 字段就是节点ID（实体名称）
            entity_id = entity_data.get("id", "")
            source_id = entity_data.get("source_id", "")
            file_path = entity_data.get("file_path", "")
            
            # 解析来源信息
            source_documents = []
            if source_id:
                chunks_info = await self._get_source_chunks_info(lightrag, source_id, conversation_id)
                # 从 chunks 中提取唯一的文档信息
                seen_file_ids = set()
                for chunk_info in chunks_info:
                    chunk_file_path = chunk_info.get("file_path", "")
                    if chunk_file_path and chunk_file_path != "unknown_source":
                        doc_info = self._parse_file_path_to_doc_info(chunk_file_path, conversation_id)
                        if doc_info and doc_info["file_id"] not in seen_file_ids:
                            seen_file_ids.add(doc_info["file_id"])
                            source_documents.append(doc_info)
            elif file_path and file_path != "unknown_source":
                # 如果没有 source_id，尝试直接从 file_path 解析
                doc_info = self._parse_file_path_to_doc_info(file_path, conversation_id)
                if doc_info:
                    source_documents.append(doc_info)
            
            entity_list.append({
                "entity_id": entity_id,
                "name": entity_id,  # 节点ID就是实体名称
                "type": entity_data.get("entity_type", entity_data.get("type", "")),
                "description": entity_data.get("description", ""),
                "source_id": source_id,
                "file_path": file_path,
                "source_documents": source_documents,  # 来源文档列表
            })
        
        return entity_list
    
    async def get_all_relations(self, conversation_id: str) -> List[Dict[str, Any]]:
        """获取对话的所有关系
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            关系列表
        """
        lightrag = await self.lightrag_service.get_lightrag_for_conversation(conversation_id)
        
        # 获取所有边（关系）
        relations = await lightrag.chunk_entity_relation_graph.get_all_edges()
        
        # relations 已经是 list[dict] 格式
        relation_list = []
        for relation_data in relations:
            # source 和 target 已经在边数据中
            relation_list.append({
                "relation_id": f"{relation_data.get('source', '')}->{relation_data.get('target', '')}",
                "source": relation_data.get("source", ""),
                "target": relation_data.get("target", ""),
                "type": relation_data.get("relation_type", relation_data.get("type", "")),
                "description": relation_data.get("description", ""),
            })
        
        return relation_list
    
    async def get_entity_detail(self, conversation_id: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """获取实体详情
        
        Args:
            conversation_id: 对话ID
            entity_id: 实体ID
            
        Returns:
            实体详情，如果不存在返回 None
        """
        entities = await self.get_all_entities(conversation_id)
        
        for entity in entities:
            if entity["entity_id"] == entity_id:
                return entity
        
        return None
    
    async def get_relation_detail(self, conversation_id: str, source: str, target: str) -> Optional[Dict[str, Any]]:
        """获取关系详情
        
        Args:
            conversation_id: 对话ID
            source: 源实体ID
            target: 目标实体ID
            
        Returns:
            关系详情，如果不存在返回 None
        """
        relations = await self.get_all_relations(conversation_id)
        
        for relation in relations:
            if relation["source"] == source and relation["target"] == target:
                return relation
        
        return None
    
    def check_has_documents_fast(self, conversation_id: str) -> bool:
        """快速检查对话是否有文档（无需初始化 LightRAG）
        
        通过检查对话元数据中的 file_count 或文档状态文件来判断。
        这是一个轻量级的检查，用于在查询前快速判断是否需要初始化 LightRAG。
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            True 表示有文档，False 表示没有文档
        """
        try:
            # 获取对话信息，提取 subject_id
            conversation = self.conversation_service.get_conversation(conversation_id)
            if not conversation:
                return False
            
            subject_id = conversation.get("subject_id")
            
            # 如果对话有 subject_id，检查 subject 的文档（因为文档现在基于 subject_id 存储）
            if subject_id:
                # 检查 subject 的文档状态
                status = self.document_service._load_subject_status(subject_id)
                documents = status.get("documents", {})
                if documents:
                    # 检查是否有已处理的文档
                    for doc_id, doc_data in documents.items():
                        doc_status = doc_data.get("status", "")
                        # 如果文档状态是 completed 或 processing，认为有文档
                        if doc_status in ["completed", "processing"]:
                            return True
                return False
            
            # 回退到旧的 conversation_id 方式（向后兼容）
            # 方式1：检查对话元数据中的 file_count（最快）
            file_count = conversation.get("file_count", 0)
            if file_count > 0:
                return True
            
            # 方式2：检查文档状态文件（更准确，但稍慢）
            status = self.document_service._load_status(conversation_id)
            documents = status.get("documents", {})
            if documents:
                # 检查是否有已处理的文档
                for doc_id, doc_data in documents.items():
                    doc_status = doc_data.get("status", "")
                    # 如果文档状态是 completed 或 processing，认为有文档
                    if doc_status in ["completed", "processing"]:
                        return True
            
            # 都没有，返回 False
            return False
            
        except Exception:
            # 检查出错时，保守起见返回 True（假设有文档，进入正常流程）
            return True
    
    async def check_knowledge_graph_empty(self, conversation_id: str) -> tuple[bool, Optional[str]]:
        """检测知识图谱是否为空
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            (is_empty, error_message): 
            - is_empty: True 表示知识图谱为空（实体=0 且 关系=0 且 文档块=0）
            - error_message: 如果检测过程中出错，返回错误信息；否则为 None
        """
        try:
            lightrag = await self.lightrag_service.get_lightrag_for_conversation(conversation_id)
            
            # 检查实体数量
            entities = await lightrag.chunk_entity_relation_graph.get_all_nodes()
            entity_count = len(entities) if entities else 0
            
            # 检查关系数量
            relations = await lightrag.chunk_entity_relation_graph.get_all_edges()
            relation_count = len(relations) if relations else 0
            
            # 检查文档块数量（通过检查 chunks_vdb 或 text_chunks）
            # 注意：chunks_vdb 可能没有直接的 count 方法，需要尝试其他方式
            chunk_count = 0
            try:
                # 尝试通过查询一个空查询来获取总数（如果 API 支持）
                # 或者通过检查 text_chunks 的键数量
                # 这里使用一个简单的检查：尝试获取一些 chunks
                # 由于 LightRAG 的存储结构，我们可能需要通过其他方式检查
                # 暂时先检查实体和关系，如果都为空，认为可能没有文档块
                pass
            except Exception:
                # 如果无法检查文档块数量，仅基于实体和关系判断
                pass
            
            # 判定标准：实体=0 且 关系=0 才判定为空
            # 注意：文档块数量检查可能较复杂，暂时主要依赖实体和关系
            is_empty = (entity_count == 0 and relation_count == 0)
            
            return is_empty, None
            
        except Exception as e:
            # 检测过程中出错，返回错误信息
            return False, f"检测知识图谱状态时出错: {str(e)}"
    
    async def check_query_result_empty(self, query_result: Dict[str, Any], kg_empty_before: bool) -> tuple[bool, bool]:
        """检查查询结果是否为空
        
        Args:
            query_result: aquery_llm 返回的结果字典
            kg_empty_before: 查询前知识图谱是否为空
            
        Returns:
            (is_empty, is_no_content):
            - is_empty: True 表示查询结果为空（实体=0 且 关系=0 且 文档块=0）
            - is_no_content: True 表示查询未匹配到相关内容（查询前有知识图谱，但查询后无结果）
        """
        try:
            # 如果查询状态为失败，直接判定为空
            if query_result.get("status") == "failure":
                return True, False
            
            data = query_result.get("data", {})
            
            entities = data.get("entities", [])
            relationships = data.get("relationships", [])
            chunks = data.get("chunks", [])
            
            entity_count = len(entities) if entities else 0
            relation_count = len(relationships) if relationships else 0
            chunk_count = len(chunks) if chunks else 0
            
            # 全部为空：判定为查询结果为空
            is_empty = (entity_count == 0 and relation_count == 0 and chunk_count == 0)
            
            # 查询未匹配到相关内容：查询前有知识图谱，但查询后无结果
            is_no_content = (not kg_empty_before and is_empty)
            
            return is_empty, is_no_content
            
        except Exception:
            # 解析失败，假设不为空
            return False, False
    
    async def query(self, conversation_id: str, query: str, mode: str = "mix", use_history: bool = True) -> str:
        """在对话的知识图谱中查询
        
        Args:
            conversation_id: 对话ID
            query: 查询文本
            mode: 查询模式（naive/local/global/mix）
            use_history: 是否使用历史对话
            
        Returns:
            查询结果（文本）
        """
        # 获取对话信息，提取 subject_id
        conversation = self.conversation_service.get_conversation(conversation_id)
        subject_id = conversation.get("subject_id") if conversation else None
        
        # 如果对话有 subject_id，使用 subject_id 来检索知识图谱（因为文档和知识图谱现在基于 subject_id 存储）
        # 否则回退到使用 conversation_id（向后兼容）
        rag_id = subject_id if subject_id else conversation_id
        
        # 获取历史对话（减少到3轮，并限制单条消息长度）
        history = []
        if use_history:
            history = self.memory_service.get_recent_history(conversation_id, max_turns=3, max_tokens_per_message=1000)
        
        result = await self.lightrag_service.query(rag_id, query, mode=mode, conversation_history=history)
        
        # 如果结果是字符串，直接返回
        if isinstance(result, str):
            return result
        
        # 如果是其他类型，转换为字符串
        return str(result)

    async def build_entity_page_mapping(
        self,
        target_id: str,
        document_ids: Optional[List[str]] = None
    ) -> None:
        """构建实体到页码的映射表
        
        扫描该知识库下的所有实体 + 所有 page_index JSON，
        计算实体最相关的 (file_id, page_index)，
        写入 entity_page_map/{subject_id}.json
        
        Args:
            target_id: 目标ID（可能是 conversation_id 或 subject_id，会自动转换为 subject_id）
            document_ids: 指定的文档ID列表（可选，如果为None则处理该知识库下的所有文档）
        """
        import json
        import re
        import app.config as config
        
        try:
            # 尝试获取 target_id 对应的 subject_id
            # 如果 target_id 本身就是 subject_id（用于文档处理），则直接使用
            # 如果是 conversation_id，则尝试获取其 subject_id
            subject_id = target_id
            try:
                conversation = self.conversation_service.get_conversation(target_id)
                if conversation and conversation.get("subject_id"):
                    subject_id = conversation["subject_id"]
            except Exception:
                # 如果获取失败，使用原始的 target_id（向后兼容）
                subject_id = target_id
            
            print(f"🔄 开始构建实体页码映射: {subject_id}...")
            
            # 1. 获取所有实体（使用 subject_id 作为 LightRAG 的命名空间）
            entities = await self.get_all_entities(subject_id)
            if not entities:
                print(f"⚠️ 知识库 {subject_id} 没有实体，跳过映射构建")
                return
                
            # 2. 加载页级索引（优先使用新路径：subjects/{subject_id}/page_index）
            page_index_dir = Path(config.settings.conversations_metadata_dir) / "subjects" / subject_id / "page_index"
            if not page_index_dir.exists():
                # 回退到旧路径：page_index/{conversation_id}
                page_index_dir = Path(config.settings.conversations_metadata_dir) / "page_index" / target_id
                if not page_index_dir.exists():
                    print(f"⚠️ 知识库 {subject_id} 没有页级索引目录，跳过映射构建")
                    return
                
            all_pages = [] # List[Dict] -> {file_id, page_index, content}
            
            # 遍历该对话下的所有文档索引文件
            for index_file in page_index_dir.glob("*.json"):
                # 如果指定了 document_ids，则只处理指定的文档
                doc_id = index_file.stem
                if document_ids and doc_id not in document_ids:
                    continue
                    
                try:
                    with open(index_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        file_id = data.get("document_id")
                        pages = data.get("pages", [])
                        for page in pages:
                            all_pages.append({
                                "file_id": file_id,
                                "page_index": page.get("page_index"),
                                "content": page.get("content", "").lower() # 转小写，方便匹配
                            })
                except Exception as e:
                    print(f"❌ 读取索引文件失败: {index_file}, 错误: {e}")
            
            if not all_pages:
                print(f"⚠️ 没有加载到任何页面内容，跳过映射构建")
                return
                
            # 3. 实体匹配
            entity_page_map = {
                "subject_id": subject_id,
                "entities": {}
            }
            
            # 预处理实体名称，转小写
            processed_entities = []
            for entity in entities:
                name = entity.get("name", "")
                if name:
                    processed_entities.append({
                        "original_name": name,
                        "lower_name": name.lower(),
                        "type": entity.get("type", "")
                    })
            
            # 对每个实体进行搜索
            for entity in processed_entities:
                name_lower = entity["lower_name"]
                original_name = entity["original_name"]
                
                candidates = []
                
                for page in all_pages:
                    # 简单匹配：计算实体名称在页面中出现的次数
                    count = page["content"].count(name_lower)
                    
                    if count > 0:
                        candidates.append({
                            "file_id": page["file_id"],
                            "page_index": page["page_index"],
                            "score": count # 简单使用频次作为分数
                        })
                
                # 如果有匹配结果
                if candidates:
                    # 按分数降序排列
                    candidates.sort(key=lambda x: x["score"], reverse=True)
                    # 只保留前 5 个候选项
                    entity_page_map["entities"][original_name] = candidates[:5]
            
            # 4. 保存映射表（使用 subject_id 作为文件名）
            map_dir = Path(config.settings.conversations_metadata_dir) / "entity_page_map"
            map_dir.mkdir(parents=True, exist_ok=True)
            map_file = map_dir / f"{subject_id}.json"
            
            with open(map_file, 'w', encoding='utf-8') as f:
                json.dump(entity_page_map, f, ensure_ascii=False, indent=2)
                
            print(f"✅ 实体页码映射构建完成: {map_file}, 包含 {len(entity_page_map['entities'])} 个实体的映射")
            
        except Exception as e:
            print(f"❌ 构建实体页码映射失败: {e}")
            import traceback
            traceback.print_exc()

    def load_entity_page_mapping(
        self,
        target_id: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """读取实体页码映射表
        
        Args:
            target_id: 目标ID（可能是 conversation_id 或 subject_id，会自动转换为 subject_id）
            
        Returns:
            实体映射字典 {entity_name: [candidates...]}，如果文件不存在则返回 {}
        """
        import json
        import app.config as config
        
        try:
            # 尝试获取 target_id 对应的 subject_id
            subject_id = target_id
            try:
                conversation = self.conversation_service.get_conversation(target_id)
                if conversation and conversation.get("subject_id"):
                    subject_id = conversation["subject_id"]
            except Exception:
                # 如果获取失败，使用原始的 target_id（向后兼容）
                subject_id = target_id
            
            # 优先使用 subject_id 作为文件名
            map_file = Path(config.settings.conversations_metadata_dir) / "entity_page_map" / f"{subject_id}.json"
            
            # 如果不存在，尝试使用 target_id（向后兼容）
            if not map_file.exists() and target_id != subject_id:
                map_file = Path(config.settings.conversations_metadata_dir) / "entity_page_map" / f"{target_id}.json"
            
            if map_file.exists():
                with open(map_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("entities", {})
            return {}
            
        except Exception as e:
            print(f"❌ 加载实体页码映射失败: {e}")
            return {}
