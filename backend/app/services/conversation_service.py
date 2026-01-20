"""对话服务"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import app.config as config


class ConversationService:
    """对话服务，管理对话的创建、查询、删除"""
    
    def __init__(self):
        self.metadata_dir = Path(config.settings.conversations_metadata_dir)
        self.conversations_dir = Path(config.settings.conversations_dir)
        self.metadata_file = self.metadata_dir / "conversations.json"
        
        # 确保目录存在
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.conversations_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载元数据
        self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """加载对话元数据"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    # 确保有必要的字段
                    if "next_conversation_number" not in metadata:
                        metadata["next_conversation_number"] = 1
                    if "conversations" not in metadata:
                        metadata["conversations"] = {}
                    return metadata
            except:
                return {"conversations": {}, "next_conversation_number": 1}
        return {"conversations": {}, "next_conversation_number": 1}
    
    def _save_metadata(self, data: Dict):
        """保存对话元数据"""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def create_conversation(self, title: Optional[str] = None, subject_id: Optional[str] = None) -> str:
        """创建新对话
        
        Args:
            title: 对话标题（可选，如不提供则使用自动编号生成）
            
        Returns:
            conversation_id: 对话的唯一ID
        """
        conversation_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        
        # 加载现有元数据
        metadata = self._load_metadata()
        if "conversations" not in metadata:
            metadata["conversations"] = {}
        if "next_conversation_number" not in metadata:
            metadata["next_conversation_number"] = 1
        
        # 如果没有提供标题，使用自动编号
        if title is None:
            next_number = metadata["next_conversation_number"]
            title = f"对话_{next_number}"
            # 递增编号
            metadata["next_conversation_number"] = next_number + 1
        
        conversation_data = {
            "conversation_id": conversation_id,
            "title": title,
            "subject_id": subject_id,
            "created_at": now,
            "updated_at": now,
            "file_count": 0,
            "status": "active"
        }
        
        # 添加新对话
        metadata["conversations"][conversation_id] = conversation_data
        
        # 保存元数据
        self._save_metadata(metadata)
        
        # 创建对话目录
        conversation_dir = self.conversations_dir / conversation_id
        conversation_dir.mkdir(parents=True, exist_ok=True)
        (conversation_dir / "documents").mkdir(parents=True, exist_ok=True)
        
        return conversation_id
    
    def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """获取对话信息
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            对话信息字典，如果不存在返回 None
        """
        metadata = self._load_metadata()
        conversation = metadata.get("conversations", {}).get(conversation_id)
        if conversation and "pinned" not in conversation:
            conversation["pinned"] = False
        return conversation
    
    def list_conversations(self, status: Optional[str] = None) -> List[Dict]:
        """获取对话列表
        
        Args:
            status: 可选，过滤状态（如 "active", "archived"）
            
        Returns:
            对话列表（置顶的排在前面，然后按更新时间倒序）
        """
        metadata = self._load_metadata()
        conversations = list(metadata.get("conversations", {}).values())
        
        # 确保每个对话都有 pinned 字段
        for conv in conversations:
            if "pinned" not in conv:
                conv["pinned"] = False
        
        if status:
            conversations = [c for c in conversations if c.get("status") == status]
        
        # 排序：置顶的排在前面，然后按更新时间倒序
        conversations.sort(key=lambda x: (not x.get("pinned", False), x.get("updated_at", "")), reverse=False)
        # 再按更新时间倒序（在各自分组内）
        pinned = [c for c in conversations if c.get("pinned", False)]
        unpinned = [c for c in conversations if not c.get("pinned", False)]
        pinned.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        unpinned.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        
        return pinned + unpinned

    def list_conversations_by_subject(self, subject_id: str, status: Optional[str] = None) -> List[Dict]:
        """按知识库获取对话列表"""
        conversations = self.list_conversations(status=status)
        return [c for c in conversations if c.get("subject_id") == subject_id]
    
    def update_conversation(self, conversation_id: str, title: Optional[str] = None, pinned: Optional[bool] = None, **kwargs) -> bool:
        """更新对话信息（重命名、置顶等）
        
        Args:
            conversation_id: 对话ID
            title: 新标题（可选）
            pinned: 是否置顶（可选）
            **kwargs: 其他要更新的字段
            
        Returns:
            是否更新成功
        """
        metadata = self._load_metadata()
        
        if conversation_id not in metadata.get("conversations", {}):
            return False
        
        conversation = metadata["conversations"][conversation_id]
        
        # 更新标题
        if title is not None:
            conversation["title"] = title
        
        # 更新置顶状态
        if pinned is not None:
            conversation["pinned"] = pinned
        
        # 更新其他字段
        for key, value in kwargs.items():
            if value is not None:
                conversation[key] = value
        
        conversation["updated_at"] = datetime.utcnow().isoformat() + "Z"
        
        self._save_metadata(metadata)
        return True
    
    def increment_file_count(self, conversation_id: str) -> bool:
        """增加对话的文件计数
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            是否成功
        """
        metadata = self._load_metadata()
        
        if conversation_id not in metadata.get("conversations", {}):
            return False
        
        conversation = metadata["conversations"][conversation_id]
        conversation["file_count"] = conversation.get("file_count", 0) + 1
        conversation["updated_at"] = datetime.utcnow().isoformat() + "Z"
        
        self._save_metadata(metadata)
        return True
    
    def decrement_file_count(self, conversation_id: str) -> bool:
        """减少对话的文件计数
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            是否成功
        """
        metadata = self._load_metadata()
        
        if conversation_id not in metadata.get("conversations", {}):
            return False
        
        conversation = metadata["conversations"][conversation_id]
        current_count = conversation.get("file_count", 0)
        conversation["file_count"] = max(0, current_count - 1)
        conversation["updated_at"] = datetime.utcnow().isoformat() + "Z"
        
        self._save_metadata(metadata)
        return True
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """删除对话及所有相关数据
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            是否删除成功
        """
        metadata = self._load_metadata()
        
        if conversation_id not in metadata.get("conversations", {}):
            return False
        
        # 从元数据中删除
        del metadata["conversations"][conversation_id]
        self._save_metadata(metadata)
        
        # 删除对话目录（包括所有文件和子目录）
        conversation_dir = self.conversations_dir / conversation_id
        if conversation_dir.exists():
            import shutil
            shutil.rmtree(conversation_dir)
        
        # 删除 LightRAG 数据目录
        lightrag_dir = Path(config.settings.lightrag_working_dir).parent / conversation_id
        if lightrag_dir.exists():
            import shutil
            shutil.rmtree(lightrag_dir)
        
        return True
    
    def get_conversation_dir(self, conversation_id: str) -> Path:
        """获取对话的文件目录路径
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            对话目录路径
        """
        return self.conversations_dir / conversation_id
    
    def _get_messages_file(self, conversation_id: str) -> Path:
        """获取消息历史文件路径"""
        conversation_dir = self.get_conversation_dir(conversation_id)
        return conversation_dir / "messages.json"
    
    def add_message(self, conversation_id: str, query: str, answer: str, tool_calls: Optional[List[dict]] = None, stream_items: Optional[List[dict]] = None) -> bool:
        """添加消息到对话历史
        
        Args:
            conversation_id: 对话ID
            query: 用户查询
            answer: AI回复
            tool_calls: 工具调用信息（可选），格式为：
                [
                    {
                        "toolName": "tool_name",
                        "arguments": {...},
                        "result": {...},
                        "status": "success" | "error",
                        "errorMessage": "..." (可选)
                    }
                ]
            stream_items: 流式输出项（可选），格式为：
                [
                    {"type": "tool_call", "toolName": "...", "arguments": {...}, "result": {...}, "status": "..."},
                    {"type": "text", "content": "..."}
                ]
            
        Returns:
            是否成功
        """
        messages_file = self._get_messages_file(conversation_id)
        messages_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 加载现有消息
        messages = []
        if messages_file.exists():
            try:
                with open(messages_file, 'r', encoding='utf-8') as f:
                    messages = json.load(f)
            except:
                messages = []
        
        # 添加用户消息
        user_message = {
            "role": "user",
            "content": query,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        messages.append(user_message)
        
        # 如果有工具调用，先添加 assistant 消息（包含 tool_calls）
        if tool_calls and len(tool_calls) > 0:
            # 构建 tool_calls 格式（OpenAI Function Calling 格式）
            assistant_tool_calls = []
            for i, tool_call in enumerate(tool_calls):
                tool_name = tool_call.get("toolName", "")
                arguments = tool_call.get("arguments", {})
                
                assistant_tool_calls.append({
                    "id": f"call_{i}_{int(datetime.utcnow().timestamp() * 1000)}",
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(arguments, ensure_ascii=False)
                    }
                })
            
            # 添加 assistant 消息（包含 tool_calls）
            assistant_message = {
                "role": "assistant",
                "content": "",  # 工具调用时 content 为空字符串
                "tool_calls": assistant_tool_calls,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            messages.append(assistant_message)
            
            # 添加 tool 消息（工具执行结果）
            for i, tool_call in enumerate(tool_calls):
                tool_name = tool_call.get("toolName", "")
                result = tool_call.get("result", {})
                status = tool_call.get("status", "unknown")
                error_message = tool_call.get("errorMessage")
                
                # 格式化工具结果内容
                if status == "success":
                    if isinstance(result, dict):
                        result_content = result.get("message", "执行成功")
                        if result.get("result"):
                            result_content += f"\n\n查询结果：\n{result.get('result')}"
                    else:
                        result_content = str(result) if result else "执行成功"
                else:
                    result_content = error_message or "执行失败"
                
                tool_message = {
                    "role": "tool",
                    "content": result_content,
                    "tool_call_id": assistant_tool_calls[i]["id"],
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                messages.append(tool_message)
        
        # 添加最终的 assistant 回答消息
        assistant_message = {
            "role": "assistant",
            "content": answer,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        # 如果有 stream_items，保存到消息中
        if stream_items:
            assistant_message["stream_items"] = stream_items
        messages.append(assistant_message)
        
        # 保存消息
        with open(messages_file, 'w', encoding='utf-8') as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
        
        return True
    
    def get_messages(self, conversation_id: str) -> List[Dict]:
        """获取对话历史消息
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            消息列表
        """
        messages_file = self._get_messages_file(conversation_id)
        
        if not messages_file.exists():
            return []
        
        try:
            with open(messages_file, 'r', encoding='utf-8') as f:
                messages = json.load(f)
                return messages if isinstance(messages, list) else []
        except:
            return []

    def reset_history(self, conversation_id: str, message_index: int) -> bool:
        """重置对话历史，保留指定索引之前的所有消息
        
        Args:
            conversation_id: 对话ID
            message_index: 保留到的最后一条消息索引（保留索引 0 到 message_index - 1 的消息）
            
        Returns:
            是否重置成功
        """
        messages_file = self._get_messages_file(conversation_id)
        
        if not messages_file.exists():
            return False
        
        messages = []
        if messages_file.exists():
            try:
                with open(messages_file, 'r', encoding='utf-8') as f:
                    messages = json.load(f)
            except:
                return False
        
        if not isinstance(messages, list):
            return False
        
        if message_index < 0 or message_index > len(messages):
            return False
        
        truncated_messages = messages[:message_index]
        
        with open(messages_file, 'w', encoding='utf-8') as f:
            json.dump(truncated_messages, f, ensure_ascii=False, indent=2)
        
        return True

