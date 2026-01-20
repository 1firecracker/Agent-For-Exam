from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import json
import uuid

import app.config as config


class SubjectService:
    """知识库服务，管理知识库的创建和查询"""

    def __init__(self) -> None:
        metadata_dir = Path(config.settings.conversations_metadata_dir)
        metadata_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = metadata_dir / "subjects.json"

    def _load_metadata(self) -> Dict:
        if self.metadata_file.exists():
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}

        if "subjects" not in data:
            data["subjects"] = {}
        if "next_subject_number" not in data:
            data["next_subject_number"] = 1
        return data

    def _save_metadata(self, data: Dict) -> None:
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def create_subject(self, name: Optional[str] = None, description: Optional[str] = None) -> str:
        metadata = self._load_metadata()

        subject_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"

        if not name:
            index = metadata["next_subject_number"]
            name = f"知识库_{index}"
            metadata["next_subject_number"] = index + 1

        metadata["subjects"][subject_id] = {
            "subject_id": subject_id,
            "name": name,
            "description": description or "",
            "created_at": now,
            "updated_at": now,
        }

        self._save_metadata(metadata)
        return subject_id

    def get_subject(self, subject_id: str) -> Optional[Dict]:
        metadata = self._load_metadata()
        return metadata["subjects"].get(subject_id)

    def list_subjects(self) -> List[Dict]:
        metadata = self._load_metadata()
        subjects = list(metadata["subjects"].values())
        subjects.sort(key=lambda x: x.get("created_at", ""))
        return subjects

    def update_subject(self, subject_id: str, name: Optional[str] = None, description: Optional[str] = None) -> bool:
        """更新知识库信息
        
        Args:
            subject_id: 知识库ID
            name: 新名称（可选）
            description: 新描述（可选）
            
        Returns:
            是否更新成功
        """
        metadata = self._load_metadata()
        if subject_id not in metadata.get("subjects", {}):
            return False
        
        subject = metadata["subjects"][subject_id]
        if name is not None:
            subject["name"] = name
        if description is not None:
            subject["description"] = description
        subject["updated_at"] = datetime.utcnow().isoformat() + "Z"
        
        self._save_metadata(metadata)
        return True

    def delete_subject(self, subject_id: str) -> bool:
        """删除知识库及所有相关数据
        
        Args:
            subject_id: 知识库ID
            
        Returns:
            是否删除成功
        """
        metadata = self._load_metadata()
        if subject_id not in metadata.get("subjects", {}):
            return False
        
        # 删除关联的对话
        from app.services.conversation_service import ConversationService
        conv_service = ConversationService()
        conversations = conv_service.list_conversations_by_subject(subject_id)
        for conv in conversations:
            conv_service.delete_conversation(conv["conversation_id"])
        
        # 从元数据中删除
        del metadata["subjects"][subject_id]
        self._save_metadata(metadata)
        
        # 删除知识库目录（包括文档、知识图谱等）
        subject_dir = Path(config.settings.data_dir) / subject_id
        if subject_dir.exists():
            import shutil
            shutil.rmtree(subject_dir)
        
        # 删除上传的文档目录
        subject_upload_dir = Path(config.settings.upload_dir) / "subjects" / subject_id
        if subject_upload_dir.exists():
            import shutil
            shutil.rmtree(subject_upload_dir)
        
        # 删除元数据目录
        subject_metadata_dir = Path(config.settings.conversations_metadata_dir) / "subjects" / subject_id
        if subject_metadata_dir.exists():
            import shutil
            shutil.rmtree(subject_metadata_dir)
        
        return True


