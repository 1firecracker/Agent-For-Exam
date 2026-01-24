"""试卷数据存储服务

负责：
- 试卷文件的目录管理
- JSON/Markdown 文件的读写
- 试卷元数据索引维护
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import app.config as config
from app.schemas.exam import ExamPaper, ExamListItem


class ExamStorage:
    """试卷存储管理器"""
    
    def __init__(self, base_dir: Path = None):
        """
        Args:
            base_dir: 试卷存储根目录，默认为 data/exams
        """
        self.base_dir = base_dir or Path(config.settings.data_dir) / "exams"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # 索引文件路径
        self._index_path = self.base_dir / "index.json"
        self._index: Dict[str, dict] = self._load_index()
    
    def _load_index(self) -> Dict[str, dict]:
        """加载试卷索引"""
        if self._index_path.exists():
            try:
                with open(self._index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_index(self) -> None:
        """保存试卷索引"""
        with open(self._index_path, 'w', encoding='utf-8') as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2, default=str)
    
    def get_exam_dir(self, exam_id: str) -> Path:
        """获取试卷专属目录"""
        exam_dir = self.base_dir / exam_id
        exam_dir.mkdir(parents=True, exist_ok=True)
        return exam_dir
    
    def create_exam_entry(self, year: int, title: str = "", subject: str = "") -> str:
        """创建新的试卷条目
        
        Args:
            year: 考试年份
            title: 试卷标题
            subject: 科目名称
            
        Returns:
            新创建的 exam_id
        """
        exam_id = str(uuid.uuid4())
        exam_dir = self.get_exam_dir(exam_id)
        
        # 创建子目录
        (exam_dir / "images").mkdir(exist_ok=True)
        
        # 更新索引
        self._index[exam_id] = {
            "id": exam_id,
            "year": year,
            "title": title,
            "subject": subject,
            "status": "pending",
            "question_count": 0,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": None,
        }
        self._save_index()
        
        return exam_id
    
    def save_source_pdf(self, exam_id: str, pdf_content: bytes, original_filename: str) -> Path:
        """保存原始 PDF 文件
        
        Returns:
            保存后的文件路径
        """
        exam_dir = self.get_exam_dir(exam_id)
        # 保留原始文件名的扩展名
        ext = Path(original_filename).suffix.lower() or ".pdf"
        pdf_path = exam_dir / f"source{ext}"
        pdf_path.write_bytes(pdf_content)
        
        # 更新索引
        if exam_id in self._index:
            self._index[exam_id]["source_pdf_path"] = str(pdf_path)
            self._save_index()
        
        return pdf_path
    
    def save_raw_markdown(self, exam_id: str, markdown_content: str) -> Path:
        """保存 OCR 解析后的原始 Markdown"""
        exam_dir = self.get_exam_dir(exam_id)
        md_path = exam_dir / "raw.md"
        md_path.write_text(markdown_content, encoding='utf-8')
        
        if exam_id in self._index:
            self._index[exam_id]["raw_markdown_path"] = str(md_path)
            self._save_index()
        
        return md_path
    
    def save_cleaned_markdown(self, exam_id: str, cleaned_content: str) -> Path:
        """保存清洗后的 Markdown"""
        exam_dir = self.get_exam_dir(exam_id)
        md_path = exam_dir / "cleaned.md"
        md_path.write_text(cleaned_content, encoding='utf-8')
        return md_path
    
    def save_parsed_json(self, exam_id: str, exam_paper: ExamPaper) -> Path:
        """保存结构化解析结果"""
        exam_dir = self.get_exam_dir(exam_id)
        json_path = exam_dir / "parsed.json"
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(exam_paper.model_dump(), f, ensure_ascii=False, indent=2, default=str)
        
        # 更新索引
        if exam_id in self._index:
            self._index[exam_id]["parsed_json_path"] = str(json_path)
            self._index[exam_id]["question_count"] = len(exam_paper.questions)
            self._index[exam_id]["status"] = "completed"
            self._index[exam_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
            self._save_index()
        
        return json_path
    
    def update_status(self, exam_id: str, status: str, error_message: str = None) -> None:
        """更新试卷处理状态"""
        if exam_id in self._index:
            self._index[exam_id]["status"] = status
            self._index[exam_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
            if error_message:
                self._index[exam_id]["error_message"] = error_message
            self._save_index()
    
    def get_exam(self, exam_id: str) -> Optional[ExamPaper]:
        """获取完整试卷数据"""
        exam_dir = self.get_exam_dir(exam_id)
        json_path = exam_dir / "parsed.json"
        
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return ExamPaper(**data)
        return None
    
    def get_exam_status(self, exam_id: str) -> Optional[dict]:
        """获取试卷状态信息"""
        return self._index.get(exam_id)
    
    def list_exams(self, year: int = None, subject: str = None) -> List[ExamListItem]:
        """列出试卷
        
        Args:
            year: 按年份筛选
            subject: 按科目筛选
        """
        items = []
        for exam_id, info in self._index.items():
            # 筛选条件
            if year and info.get("year") != year:
                continue
            if subject and info.get("subject") != subject:
                continue
            
            items.append(ExamListItem(
                exam_id=exam_id,
                year=info.get("year", 0),
                title=info.get("title", ""),
                subject=info.get("subject", ""),
                question_count=info.get("question_count", 0),
                status=info.get("status", "pending"),
                created_at=datetime.fromisoformat(info.get("created_at", "1970-01-01T00:00:00Z").replace("Z", "+00:00")),
            ))
        
        # 按创建时间倒序
        items.sort(key=lambda x: x.created_at, reverse=True)
        return items
    
    def delete_exam(self, exam_id: str) -> bool:
        """删除试卷及其所有文件"""
        exam_dir = self.base_dir / exam_id
        if exam_dir.exists():
            shutil.rmtree(exam_dir, ignore_errors=True)
        
        if exam_id in self._index:
            del self._index[exam_id]
            self._save_index()
            return True
        return False
    
    def get_images_dir(self, exam_id: str) -> Path:
        """获取试卷图片目录"""
        images_dir = self.get_exam_dir(exam_id) / "images"
        images_dir.mkdir(exist_ok=True)
        return images_dir
