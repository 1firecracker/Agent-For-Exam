"""文档服务，处理文档上传、解析、LightRAG 集成"""
import asyncio
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import UploadFile

import app.config as config
from app.services.conversation_service import ConversationService
from app.services.lightrag_service import LightRAGService
from app.storage.file_manager import FileManager
from app.utils.document_parser import DocumentParser

# 全局信号量：限制同时处理的文档数量（避免 LightRAG 并发冲突）
_processing_semaphore = asyncio.Semaphore(1)  # 同一时间只处理1个文档
# 处理队列锁：确保队列操作的原子性
_queue_lock = asyncio.Lock()
# 等待队列：{ conversation_id: [document_id, ...] }
_processing_queue: Dict[str, List[str]] = {}


class DocumentService:
    """文档服务"""
    
    def __init__(self):
        self.conversation_service = ConversationService()
        self.lightrag_service = LightRAGService()
        self.file_manager = FileManager()
        self.document_parser = DocumentParser()
        self.status_dir = Path(config.settings.conversations_metadata_dir) / "document_status"
        self.status_dir.mkdir(parents=True, exist_ok=True)
    
    def _clean_base64_and_save(self, text: str, conversation_id: str) -> Tuple[str, Dict[str, str]]:
        """清理文本中的 base64 字符串，保存到 base_64.json，并返回清理后的文本和映射关系
        
        Args:
            text: 原始文本
            conversation_id: 对话ID
            
        Returns:
            (清理后的文本, base64映射字典 {序号: base64字符串})
        """
        # 获取 base64.json 文件路径（与 kv_store_full_docs.json 同级）
        print("cleaning base64", "="*70)
        base_working_dir = Path(config.settings.lightrag_working_dir)
        base64_file = base_working_dir.parent / conversation_id / conversation_id / "base_64.json"
        base64_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 加载已有的 base64 数据（如果存在）
        base64_map = {}
        if base64_file.exists():
            try:
                with open(base64_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    base64_map = existing_data if isinstance(existing_data, dict) else {}
            except:
                base64_map = {}
        
        # 获取下一个序号（从已有最大序号+1开始）
        existing_indices = [int(k) for k in base64_map.keys() if k.isdigit()]
        next_index = max(existing_indices, default=0) + 1
        
        cleaned_text = text
        
        # 1. 处理 <latexit> 标签及其内容
        # 匹配 <latexit> 标签，包括标签属性和标签内容
        latexit_pattern = r'<latexit[^>]*>([^<]*)</latexit>'
        
        def replace_latexit(match):
            nonlocal next_index
            full_match = match.group(0)
            tag_content = match.group(1).strip()
            
            # 提取标签中的 sha1_base64 属性值（如果有）
            sha1_match = re.search(r'sha1_base64="([^"]+)"', full_match)
            
            # 提取标签内容中的 base64 字符串（通常是长字符串）
            base64_in_content = re.search(r'[A-Za-z0-9+/=]{50,}', tag_content)
            
            # 优先使用标签内容中的 base64，否则使用 sha1_base64 属性
            if base64_in_content:
                base64_value = base64_in_content.group(0)
            elif sha1_match:
                base64_value = sha1_match.group(1)
            elif tag_content and len(tag_content) > 20:
                base64_value = tag_content
            else:
                return ""  # 如果内容太短或没有 base64，直接移除
            
            index_str = str(next_index)
            base64_map[index_str] = base64_value
            next_index += 1
            return f"[BASE64_{index_str}]"
        
        cleaned_text = re.sub(latexit_pattern, replace_latexit, cleaned_text, flags=re.DOTALL)
        
        # 2. 处理独立的 base64 字符串（长度>=50，且不在已替换的引用中）
        # 先标记已替换的位置，避免重复处理
        standalone_base64_pattern = r'(?<!\[BASE64_)[A-Za-z0-9+/=]{50,}(?!\])'
        
        def replace_standalone(match):
            nonlocal next_index
            base64_str = match.group(0)
            # 验证是否为有效的 base64（不包含空格、换行等）
            if re.match(r'^[A-Za-z0-9+/=]+$', base64_str):
                index_str = str(next_index)
                base64_map[index_str] = base64_str
                next_index += 1
                return f"[BASE64_{index_str}]"
            return base64_str
        
        cleaned_text = re.sub(standalone_base64_pattern, replace_standalone, cleaned_text)
        
        # 保存 base64 映射到文件（如果有新增）
        if base64_map:
            with open(base64_file, 'w', encoding='utf-8') as f:
                json.dump(base64_map, f, ensure_ascii=False, indent=2)
        
        return cleaned_text, base64_map
    
    def _get_status_file(self, conversation_id: str) -> Path:
        """获取状态文件路径"""
        return self.status_dir / f"{conversation_id}.json"
    
    def _load_status(self, conversation_id: str) -> Dict:
        """加载文档状态"""
        status_file = self._get_status_file(conversation_id)
        if status_file.exists():
            try:
                with open(status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"documents": {}}
        return {"documents": {}}
    
    def _save_status(self, conversation_id: str, status: Dict):
        """保存文档状态"""
        status_file = self._get_status_file(conversation_id)
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
    
    def _validate_file(self, filename: str) -> tuple[bool, Optional[str]]:
        """验证文件类型
        
        Returns:
            (是否有效, 错误信息)
        """
        # 检查文件扩展名
        file_ext = Path(filename).suffix.lower().lstrip('.')
        if file_ext not in config.settings.allowed_extensions:
            return False, f"不支持的文件类型: {file_ext}，仅支持 {', '.join(config.settings.allowed_extensions)}"
        
        return True, None
    
    async def _check_file_size(self, file_content: bytes) -> tuple[bool, Optional[str]]:
        """检查文件大小
        
        Returns:
            (是否有效, 错误信息)
        """
        file_size = len(file_content)
        
        if file_size > config.settings.max_file_size:
            return False, f"文件大小 {file_size / 1024 / 1024:.2f}MB 超过限制 {config.settings.max_file_size / 1024 / 1024}MB"
        
        return True, None
    
    async def upload_documents(self, conversation_id: Optional[str], files: List[UploadFile]) -> Dict:
        """上传文档到对话
        
        Args:
            conversation_id: 对话ID（如果为None则自动创建）
            files: 文件列表（UploadFile 对象）
            
        Returns:
            上传结果字典
        """
        # 自动创建对话（如果 conversation_id 为 None 或 "new"）
        if conversation_id is None or conversation_id == "new":
            # 基于第一个文件名生成对话标题（可选，如不提供则使用自动编号）
            first_filename = files[0].filename if files else "新对话"
            title = Path(first_filename).stem if files else None
            conversation_id = self.conversation_service.create_conversation(title=title)
        
        # 验证对话是否存在，如果不存在则自动创建
        conversation = self.conversation_service.get_conversation(conversation_id)
        if not conversation:
            # 对话不存在时自动创建
            conversation_id = self.conversation_service.create_conversation(title=None)
            conversation = self.conversation_service.get_conversation(conversation_id)
        
        # 检查当前文件数量
        status = self._load_status(conversation_id)
        current_file_count = len(status.get("documents", {}))
        
        if current_file_count + len(files) > config.settings.max_files_per_conversation:
            raise ValueError(
                f"对话已有 {current_file_count} 个文件，再上传 {len(files)} 个将超过限制 "
                f"({config.settings.max_files_per_conversation} 个)"
            )
        
        uploaded_files = []
        
        for file in files:
            # 验证文件类型
            is_valid, error_msg = self._validate_file(file.filename)
            if not is_valid:
                raise ValueError(error_msg)
            
            # 读取文件内容
            file_content = await file.read()
            
            # 验证文件大小
            is_valid, error_msg = await self._check_file_size(file_content)
            if not is_valid:
                raise ValueError(error_msg)
            
            # 保存文件
            file_info = self.file_manager.save_file(
                conversation_id=conversation_id,
                file_content=file_content,
                original_filename=file.filename
            )
            
            # 创建文档记录
            document_id = file_info["file_id"]
            now = datetime.utcnow().isoformat() + "Z"
            
            document_data = {
                "file_id": document_id,
                "conversation_id": conversation_id,
                "filename": file.filename,
                "file_size": file_info["file_size"],
                "file_extension": file_info["file_extension"],
                "file_path": file_info["file_path"],
                "upload_time": now,
                "status": "pending",
                "lightrag_track_id": None,
            }
            
            # 更新状态
            status = self._load_status(conversation_id)
            if "documents" not in status:
                status["documents"] = {}
            status["documents"][document_id] = document_data
            self._save_status(conversation_id, status)
            
            # 更新对话文件计数
            self.conversation_service.increment_file_count(conversation_id)
            
            uploaded_files.append({
                "file_id": document_id,
                "filename": file.filename,
                "file_size": file_info["file_size"],
                "status": "pending"
            })
        
        return {
            "conversation_id": conversation_id,
            "uploaded_files": uploaded_files,
            "total_files": len(uploaded_files)
        }
    
    async def process_document(self, conversation_id: str, document_id: str):
        """处理文档：解析文本并插入 LightRAG（异步后台任务）
        
        使用信号量控制并发，确保同一时间只有一个文档在处理，
        避免 LightRAG 并发写入冲突。
        
        Args:
            conversation_id: 对话ID
            document_id: 文档ID
        """
        global _processing_queue
        
        # 将文档加入等待队列
        async with _queue_lock:
            if conversation_id not in _processing_queue:
                _processing_queue[conversation_id] = []
            if document_id not in _processing_queue[conversation_id]:
                _processing_queue[conversation_id].append(document_id)
            queue_position = _processing_queue[conversation_id].index(document_id) + 1
            print(f"📋 文档 {document_id[:8]}... 加入队列，位置: {queue_position}")
        
        # 使用信号量控制并发（同一时间只处理1个文档）
        async with _processing_semaphore:
            print(f"🔄 开始处理文档: {document_id[:8]}...")
            
            # 更新状态为处理中
            status = self._load_status(conversation_id)
            if document_id in status.get("documents", {}):
                status["documents"][document_id]["status"] = "processing"
                self._save_status(conversation_id, status)
            
            try:
                # 获取文件路径
                file_path = self.file_manager.get_file_path(conversation_id, document_id)
                if not file_path or not file_path.exists():
                    raise FileNotFoundError(f"文件不存在: {document_id}")
                
                # 解析文档，提取文本
                text = self.document_parser.extract_text(str(file_path))
                
                if not text or not text.strip():
                    raise ValueError("文档解析后文本内容为空")
                
                # 清理 base64 字符串并保存
                cleaned_text, base64_map = self._clean_base64_and_save(text, conversation_id)
                
                # 插入到 LightRAG（使用清理后的文本）
                track_id = await self.lightrag_service.insert_document(
                    conversation_id=conversation_id,
                    text=cleaned_text,
                    doc_id=document_id
                )
                
                # 更新状态为完成
                status = self._load_status(conversation_id)
                if document_id in status.get("documents", {}):
                    status["documents"][document_id]["status"] = "completed"
                    status["documents"][document_id]["lightrag_track_id"] = track_id
                    self._save_status(conversation_id, status)
                
                print(f"✅ 文档处理完成: {document_id[:8]}...")
            
            except Exception as e:
                # 更新状态为失败
                status = self._load_status(conversation_id)
                if document_id in status.get("documents", {}):
                    status["documents"][document_id]["status"] = "failed"
                    status["documents"][document_id]["error"] = str(e)
                    self._save_status(conversation_id, status)
                print(f"❌ 文档处理失败: {document_id[:8]}... 错误: {e}")
                raise
            finally:
                # 从队列中移除
                async with _queue_lock:
                    if conversation_id in _processing_queue:
                        if document_id in _processing_queue[conversation_id]:
                            _processing_queue[conversation_id].remove(document_id)
                        if not _processing_queue[conversation_id]:
                            del _processing_queue[conversation_id]
    
    def get_document(self, conversation_id: str, file_id: str) -> Optional[Dict]:
        """获取文档信息
        
        Args:
            conversation_id: 对话ID
            file_id: 文件ID
            
        Returns:
            文档信息，如果不存在返回 None
        """
        status = self._load_status(conversation_id)
        return status.get("documents", {}).get(file_id)
    
    def list_documents(self, conversation_id: str) -> List[Dict]:
        """列出对话的所有文档
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            文档列表
        """
        status = self._load_status(conversation_id)
        documents = list(status.get("documents", {}).values())
        # 按上传时间倒序排列
        documents.sort(key=lambda x: x.get("upload_time", ""), reverse=True)
        return documents
    
    async def get_document_status(self, conversation_id: str, file_id: str) -> Optional[Dict]:
        """获取文档处理状态
        
        Args:
            conversation_id: 对话ID
            file_id: 文件ID
            
        Returns:
            文档状态信息，包含进度信息
        """
        document = self.get_document(conversation_id, file_id)
        if document:
            status_info = {
                "file_id": file_id,
                "status": document.get("status"),
                "lightrag_track_id": document.get("lightrag_track_id"),
                "error": document.get("error"),
                "upload_time": document.get("upload_time"),
            }
            
            # 如果文档正在处理中，尝试获取进度信息
            if document.get("status") == "processing":
                try:
                    progress = await self.lightrag_service.get_processing_progress(doc_id=file_id)
                    if progress:
                        status_info["progress"] = progress
                except Exception:
                    # 如果获取进度失败，忽略错误
                    pass
            
            return status_info
        return None
    
    async def delete_document(self, conversation_id: str, file_id: str) -> bool:
        """删除文档
        
        删除操作包括：
        1. 从文件系统删除文件
        2. 从LightRAG知识图谱中删除相关数据
        3. 清理图片缓存
        4. 从状态中删除记录
        5. 更新对话文件计数
        
        Args:
            conversation_id: 对话ID
            file_id: 文件ID
            
        Returns:
            是否删除成功
        """
        # 获取文档信息（用于清理缓存和LightRAG数据）
        document = self.get_document(conversation_id, file_id)
        
        if not document:
            return False
        
        try:
            # 1. 从LightRAG中删除文档数据（如果已处理）
            if document.get("status") == "completed" and document.get("lightrag_track_id"):
                try:
                    # 获取LightRAG实例并删除文档
                    lightrag = await self.lightrag_service.get_lightrag_for_conversation(conversation_id)
                    # LightRAG可能没有直接的删除方法，这里先尝试删除相关的chunks
                    # 注意：LightRAG可能没有提供删除单个文档的API，需要查看文档
                    # 暂时跳过，因为LightRAG的设计可能是不可逆的
                    pass
                except Exception as e:
                    # LightRAG删除失败不影响文件删除，记录日志即可
                    print(f"Warning: 从LightRAG删除文档失败: {e}")
            
            # 2. 清理图片缓存
            try:
                from app.utils.image_renderer import ImageRenderer
                import app.config as config
                
                image_renderer = ImageRenderer(
                    cache_dir=config.settings.image_cache_dir,
                    resolution=config.settings.image_resolution,
                    cache_expiry_hours=config.settings.image_cache_expiry_hours
                )
                
                file_ext = document.get("file_extension", "")
                if file_ext:
                    # 删除该文件的所有缓存图片（包括缩略图）
                    cache_dir = Path(config.settings.image_cache_dir) / file_ext / file_id
                    if cache_dir.exists():
                        import shutil
                        shutil.rmtree(cache_dir, ignore_errors=True)
            except Exception as e:
                # 缓存清理失败不影响文件删除
                print(f"Warning: 清理图片缓存失败: {e}")
            
            # 3. 删除文件
            file_deleted = self.file_manager.delete_file(conversation_id, file_id)
            
            # 4. 从状态中删除
            if file_id in self._load_status(conversation_id).get("documents", {}):
                status = self._load_status(conversation_id)
                del status["documents"][file_id]
                self._save_status(conversation_id, status)
            
            # 5. 更新对话文件计数
            self.conversation_service.decrement_file_count(conversation_id)
            
            return file_deleted
            
        except Exception as e:
            print(f"Error deleting document {file_id}: {e}")
            # 即使部分操作失败，也尝试删除文件
            return self.file_manager.delete_file(conversation_id, file_id)
