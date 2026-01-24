"""试卷数据结构定义 (Exam Schemas)

本模块定义了历年试题分析功能所需的数据结构，包括：
- Question: 单个题目的结构化表示
- ExamPaper: 完整试卷的结构化表示
- 相关 API 请求/响应模型
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    """题目类型枚举"""
    CHOICE = "choice"           # 选择题（单选/多选）
    BLANK = "blank"             # 填空题
    QA = "qa"                   # 问答题/简答题
    CALCULATION = "calculation" # 计算题
    PROOF = "proof"             # 证明题
    OTHER = "other"             # 其他


class Question(BaseModel):
    """单个题目的结构化表示"""
    id: str = Field(..., description="题目唯一ID，格式: {year}-Q{index}")
    index: int = Field(..., ge=1, description="题目序号，从1开始")
    type: QuestionType = Field(default=QuestionType.OTHER, description="题目类型")
    content: str = Field(..., description="题目正文（含题干描述）")
    options: List[str] = Field(default_factory=list, description="选择题选项列表")
    score: Optional[float] = Field(default=None, ge=0, description="题目分值")
    images: List[str] = Field(default_factory=list, description="关联图片路径列表")
    original_text: str = Field(default="", description="原始 OCR 文本（用于回溯校验）")
    
    # 可选的元数据
    sub_questions: List[Question] = Field(default_factory=list, description="子问题列表（用于大题包含小题的情况）")
    
    class Config:
        use_enum_values = True


class ExamPaper(BaseModel):
    """完整试卷的结构化表示"""
    id: str = Field(..., description="试卷唯一ID (UUID)")
    year: int = Field(..., ge=1900, le=2100, description="考试年份")
    title: str = Field(default="", description="试卷标题")
    subject: str = Field(default="", description="科目名称")
    total_score: Optional[float] = Field(default=None, ge=0, description="试卷总分")
    duration_minutes: Optional[int] = Field(default=None, ge=0, description="考试时长（分钟）")
    questions: List[Question] = Field(default_factory=list, description="题目列表")
    
    # 文件路径
    source_pdf_path: str = Field(default="", description="原始 PDF 文件路径")
    raw_markdown_path: str = Field(default="", description="OCR 解析后的 Markdown 文件路径")
    parsed_json_path: str = Field(default="", description="结构化 JSON 文件路径")
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")
    status: str = Field(default="pending", description="处理状态: pending/processing/completed/failed")
    error_message: Optional[str] = Field(default=None, description="错误信息（如果失败）")


# ========== API Request/Response Models ==========

class ExamUploadResponse(BaseModel):
    """试卷上传响应"""
    exam_id: str = Field(..., description="试卷ID")
    task_id: str = Field(..., description="异步处理任务ID")
    filename: str = Field(..., description="原始文件名")
    status: str = Field(default="pending", description="当前状态")
    message: str = Field(default="", description="提示信息")


class ExamStatusResponse(BaseModel):
    """试卷处理状态响应"""
    exam_id: str
    status: str  # pending/processing/completed/failed
    progress: Optional[int] = Field(default=None, ge=0, le=100, description="处理进度百分比")
    message: Optional[str] = None
    result: Optional[ExamPaper] = None  # 完成时返回完整试卷数据


class ExamListItem(BaseModel):
    """试卷列表项（简化信息）"""
    exam_id: str
    year: int
    title: str
    subject: str
    question_count: int
    status: str
    created_at: datetime


class ExamListResponse(BaseModel):
    """试卷列表响应"""
    total: int
    items: List[ExamListItem]
