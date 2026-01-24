"""试卷处理业务服务

负责协调：
- 文件上传
- OCR 解析
- 结构化抽取
- 存储管理
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import UploadFile

import app.config as config
from app.config import get_logger
from app.schemas.exam import ExamPaper, ExamListItem, ExamStatusResponse
from app.services.exam.exam_parser import ExamParser
from app.services.exam.exam_storage import ExamStorage
from app.services.paddle_ocr_client import get_gitee_client, GiteePaddleOCRClient
from app.utils.text_cleaner import TextCleaner

logger = get_logger("app.exam_service")


class ExamService:
    """试卷处理服务"""
    
    def __init__(self):
        self.storage = ExamStorage()
        self.parser = ExamParser()
        self.ocr_client: Optional[GiteePaddleOCRClient] = None
        
        # 尝试初始化 OCR 客户端
        try:
            self.ocr_client = get_gitee_client()
            if not self.ocr_client.enabled:
                logger.warning("Gitee OCR Token 未配置，OCR 功能不可用")
                self.ocr_client = None
        except Exception as e:
            logger.warning(f"OCR 客户端初始化失败: {e}")
    
    async def upload_exam(
        self,
        file: UploadFile,
        year: int,
        title: str = "",
        subject: str = ""
    ) -> dict:
        """上传并处理试卷
        
        Args:
            file: 上传的 PDF 文件
            year: 考试年份
            title: 试卷标题
            subject: 科目名称
            
        Returns:
            包含 exam_id 和 task_id 的字典
        """
        # 1. 验证文件类型
        filename = file.filename or "unknown.pdf"
        ext = Path(filename).suffix.lower()
        if ext not in [".pdf"]:
            raise ValueError(f"不支持的文件类型: {ext}，仅支持 PDF")
        
        # 2. 读取文件内容
        content = await file.read()
        if len(content) > config.settings.max_file_size:
            raise ValueError(f"文件过大，最大支持 {config.settings.max_file_size // 1024 // 1024}MB")
        
        # 3. 创建试卷条目
        exam_id = self.storage.create_exam_entry(year=year, title=title, subject=subject)
        
        # 4. 保存原始 PDF
        self.storage.save_source_pdf(exam_id, content, filename)
        
        # 5. 启动异步处理任务
        task = asyncio.create_task(self._process_exam_async(exam_id, year))
        task_id = f"exam-{exam_id}"
        
        logger.info(
            "试卷上传成功，开始异步处理",
            extra={"event": "exam.upload", "exam_id": exam_id, "file_name": filename, "year": year}
        )
        
        return {
            "exam_id": exam_id,
            "task_id": task_id,
            "filename": filename,
            "status": "processing",
            "message": "试卷已上传，正在解析中..."
        }
    
    async def reparse_exam(self, exam_id: str) -> dict:
        """重新解析试卷（跳过 OCR，仅进行结构化抽取）
        
        Args:
            exam_id: 试卷 ID
            
        Returns:
            状态字典
        """
        # 验证试卷是否存在
        exam_info = self.storage.get_exam_status(exam_id)
        if not exam_info:
            raise FileNotFoundError(f"试卷不存在: {exam_id}")
            
        # 启动异步处理
        task = asyncio.create_task(self._reparse_exam_async(exam_id))
        
        return {
            "exam_id": exam_id,
            "status": "processing",
            "message": "已触发重新解析（跳过 OCR）"
        }

    async def _reparse_exam_async(self, exam_id: str) -> None:
        """异步处理重解析流程"""
        try:
            self.storage.update_status(exam_id, "processing")
            exam_info = self.storage.get_exam_status(exam_id)
            year = exam_info.get("year", 2024)
            
            # 1. 获取已存在的 Markdown 内容
            exam_dir = self.storage.get_exam_dir(exam_id)
            cleaned_path = exam_dir / "cleaned.md"
            raw_path = exam_dir / "raw.md"
            
            cleaned_text = ""
            
            if cleaned_path.exists():
                logger.info(f"直接复用 cleaned.md: {exam_id}")
                cleaned_text = cleaned_path.read_text(encoding="utf-8")
            elif raw_path.exists():
                logger.info(f"复用 raw.md 并进行清洗: {exam_id}")
                raw_markdown = raw_path.read_text(encoding="utf-8")
                
                # 文本清洗
                images_dir = self.storage.get_images_dir(exam_id)
                cleaner = TextCleaner(base64_output_dir=images_dir)
                cleaned_text, base64_map = cleaner.clean(raw_markdown)
                self.storage.save_cleaned_markdown(exam_id, cleaned_text)
                
                if base64_map:
                    base64_path = exam_dir / "base64_map.json"
                    cleaner.save_base64_map(base64_path)
            else:
                self.storage.update_status(exam_id, "failed", error_message="Markdown 文件丢失，请重新上传")
                return

            # 2. 结构化解析
            logger.info(f"开始结构化解析 (Reparse): {exam_id}")
            questions = await self.parser.parse(cleaned_text, exam_id, year)
            
            # 3. 构建完整试卷对象
            exam_paper = ExamPaper(
                id=exam_id,
                year=year,
                title=exam_info.get("title", ""),
                subject=exam_info.get("subject", ""),
                questions=questions,
                source_pdf_path=exam_info.get("source_pdf_path", ""),
                raw_markdown_path=str(raw_path),
                parsed_json_path=str(exam_dir / "parsed.json"),
                created_at=datetime.utcnow(), # 注意：不想覆盖创建时间的话应读取原值，但简单起见更新
                status="completed"
            )
            
            # 4. 保存结果
            self.storage.save_parsed_json(exam_id, exam_paper)
            
            logger.info(
                "试卷重解析完成",
                extra={"event": "exam.reparsed", "exam_id": exam_id, "question_count": len(questions)}
            )
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"试卷重解析失败: {exam_id}, 错误: {error_msg}")
            self.storage.update_status(exam_id, "failed", error_message=error_msg)

    async def _process_exam_async(self, exam_id: str, year: int) -> None:
        """异步处理试卷的完整流程"""
        try:
            self.storage.update_status(exam_id, "processing")
            
            # 1. 获取 PDF 路径
            exam_info = self.storage.get_exam_status(exam_id)
            pdf_path = exam_info.get("source_pdf_path")
            if not pdf_path or not Path(pdf_path).exists():
                raise FileNotFoundError("原始 PDF 文件不存在")
            
            # 2. OCR 解析
            logger.info(f"开始 OCR 解析: {exam_id}")
            raw_markdown = await self._perform_ocr(exam_id, pdf_path)
            self.storage.save_raw_markdown(exam_id, raw_markdown)
            
            # 3. 文本清洗
            logger.info(f"开始文本清洗: {exam_id}")
            images_dir = self.storage.get_images_dir(exam_id)
            cleaner = TextCleaner(base64_output_dir=images_dir)
            cleaned_text, base64_map = cleaner.clean(raw_markdown)
            self.storage.save_cleaned_markdown(exam_id, cleaned_text)
            
            # 保存 base64 映射（如果有）
            if base64_map:
                base64_path = self.storage.get_exam_dir(exam_id) / "base64_map.json"
                cleaner.save_base64_map(base64_path)
            
            # 4. 结构化解析
            logger.info(f"开始结构化解析: {exam_id}")
            questions = await self.parser.parse(cleaned_text, exam_id, year)
            
            # 5. 构建完整试卷对象
            exam_paper = ExamPaper(
                id=exam_id,
                year=year,
                title=exam_info.get("title", ""),
                subject=exam_info.get("subject", ""),
                questions=questions,
                source_pdf_path=pdf_path,
                raw_markdown_path=str(self.storage.get_exam_dir(exam_id) / "raw.md"),
                parsed_json_path=str(self.storage.get_exam_dir(exam_id) / "parsed.json"),
                created_at=datetime.utcnow(),
                status="completed"
            )
            
            # 6. 保存结果
            self.storage.save_parsed_json(exam_id, exam_paper)
            
            logger.info(
                "试卷解析完成",
                extra={"event": "exam.completed", "exam_id": exam_id, "question_count": len(questions)}
            )
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"试卷处理失败: {exam_id}, 错误: {error_msg}")
            self.storage.update_status(exam_id, "failed", error_message=error_msg)
    
    async def _perform_ocr(self, exam_id: str, pdf_path: str) -> str:
        """执行 OCR 解析"""
        if self.ocr_client and self.ocr_client.enabled:
            # 使用 Gitee PaddleOCR
            result = self.ocr_client.parse_pdf(
                file_path=pdf_path,
                conversation_id=exam_id,  # 复用 conversation_id 参数
                document_id=exam_id,
                output_dir=self.storage.get_exam_dir(exam_id)
            )
            return result.get("text", "")
        else:
            # 回退方案：使用本地 PDF 解析器
            from app.utils.pdf_parser import PDFParser
            parser = PDFParser()
            return parser.extract_text(pdf_path)
    
    def get_exam_status(self, exam_id: str) -> Optional[ExamStatusResponse]:
        """获取试卷处理状态"""
        info = self.storage.get_exam_status(exam_id)
        if not info:
            return None
        
        # 如果已完成，附带完整数据
        result = None
        if info.get("status") == "completed":
            result = self.storage.get_exam(exam_id)
        
        return ExamStatusResponse(
            exam_id=exam_id,
            status=info.get("status", "unknown"),
            message=info.get("error_message"),
            result=result
        )
    
    def get_exam(self, exam_id: str) -> Optional[ExamPaper]:
        """获取完整试卷数据"""
        return self.storage.get_exam(exam_id)
    
    def list_exams(self, year: int = None, subject: str = None) -> List[ExamListItem]:
        """列出试卷"""
        return self.storage.list_exams(year=year, subject=subject)
    
    def delete_exam(self, exam_id: str) -> bool:
        """删除试卷"""
        return self.storage.delete_exam(exam_id)
