"""试卷管理 API 路由

提供：
- POST /api/exams/upload - 上传试卷
- GET /api/exams/{exam_id}/status - 查询处理状态
- GET /api/exams/{exam_id} - 获取试卷详情
- GET /api/exams - 列出所有试卷
- DELETE /api/exams/{exam_id} - 删除试卷
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse

from app.schemas.exam import (
    ExamUploadResponse,
    ExamStatusResponse,
    ExamPaper,
    ExamListResponse,
)
from app.services.exam.exam_service import ExamService

router = APIRouter(prefix="/api/exams", tags=["exams"])

# 服务实例
_exam_service: Optional[ExamService] = None


def get_exam_service() -> ExamService:
    """获取试卷服务实例（懒加载）"""
    global _exam_service
    if _exam_service is None:
        _exam_service = ExamService()
    return _exam_service


@router.post("/upload", response_model=ExamUploadResponse)
async def upload_exam(
    file: UploadFile = File(..., description="试卷 PDF 文件"),
    year: int = Form(..., ge=1900, le=2100, description="考试年份"),
    title: str = Form(default="", description="试卷标题"),
    subject: str = Form(default="", description="科目名称"),
):
    """上传试卷 PDF 并开始异步解析
    
    上传成功后立即返回 exam_id，可通过 /status 接口轮询处理进度。
    """
    service = get_exam_service()
    
    try:
        result = await service.upload_exam(
            file=file,
            year=year,
            title=title,
            subject=subject
        )
        return ExamUploadResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.get("/{exam_id}/status", response_model=ExamStatusResponse)
async def get_exam_status(exam_id: str):
    """获取试卷处理状态
    
    状态值：
    - pending: 等待处理
    - processing: 处理中
    - completed: 处理完成
    - failed: 处理失败
    """
    service = get_exam_service()
    
    result = service.get_exam_status(exam_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"试卷不存在: {exam_id}")
    
    return result


@router.get("/{exam_id}", response_model=ExamPaper)
async def get_exam(exam_id: str):
    """获取试卷完整信息（含所有题目）"""
    service = get_exam_service()
    
    exam = service.get_exam(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail=f"试卷不存在或尚未解析完成: {exam_id}")
    
    return exam


@router.get("", response_model=ExamListResponse)
async def list_exams(
    year: Optional[int] = Query(default=None, ge=1900, le=2100, description="按年份筛选"),
    subject: Optional[str] = Query(default=None, description="按科目筛选"),
):
    """列出所有试卷"""
    service = get_exam_service()
    
    items = service.list_exams(year=year, subject=subject)
    return ExamListResponse(total=len(items), items=items)


@router.delete("/{exam_id}")
async def delete_exam(exam_id: str):
    """删除试卷及其所有相关文件"""
    service = get_exam_service()
    
    success = service.delete_exam(exam_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"试卷不存在: {exam_id}")
    
    return {"message": "删除成功", "exam_id": exam_id}


@router.post("/{exam_id}/reparse")
async def reparse_exam(exam_id: str):
    """重新解析试卷（跳过 OCR，仅重跑结构化提取）"""
    service = get_exam_service()
    try:
        result = await service.reparse_exam(exam_id)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重解析失败: {str(e)}")


@router.get("/{exam_id}/images/{image_name}")
async def get_exam_image(exam_id: str, image_name: str):
    """获取试卷图片"""
    service = get_exam_service()
    
    # 验证文件名安全性 (简单防路径穿越)
    if ".." in image_name or "/" in image_name or "\\" in image_name:
         raise HTTPException(status_code=400, detail="Invalid image name")

    image_path = service.storage.get_images_dir(exam_id) / image_name
    
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
        
    return FileResponse(image_path)
