"""知识库文档管理 API（按 subjectId）"""
from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

import app.config as config
from app.services.document_service import DocumentService
from app.services.subject_service import SubjectService
from app.utils.document_parser import DocumentParser
from app.utils.image_renderer import ImageRenderer

router = APIRouter(tags=["subject-documents"])

# 初始化图片渲染器
image_renderer = ImageRenderer(
    cache_dir=config.settings.image_cache_dir,
    resolution=config.settings.image_resolution,
    cache_expiry_hours=config.settings.image_cache_expiry_hours
)

# 响应模型
class DocumentResponse(BaseModel):
    file_id: str
    filename: str
    file_size: int
    status: str

class DocumentDetailResponse(BaseModel):
    file_id: str
    subject_id: str
    filename: str
    file_size: int
    file_extension: str
    upload_time: str
    status: str
    lightrag_track_id: Optional[str] = None

class DocumentListResponse(BaseModel):
    documents: List[DocumentDetailResponse]
    total: int

class DocumentUploadResponse(BaseModel):
    subject_id: str
    uploaded_files: List[DocumentResponse]
    total_files: int

class DocumentStatusResponse(BaseModel):
    file_id: str
    status: str
    lightrag_track_id: Optional[str] = None
    error: Optional[str] = None
    upload_time: str
    progress: Optional[dict] = None

# 幻灯片相关 API
class SlideResponse(BaseModel):
    slide_number: int
    title: str
    text_content: str
    images: List[dict] = []
    structure: dict = {}
    text_positions: List[dict] = []
    slide_dimensions: Optional[dict] = None

class SlideListResponse(BaseModel):
    filename: str
    total_slides: int
    slides: List[SlideResponse]


@router.post("/api/subjects/{subject_id}/documents/upload", 
             response_model=DocumentUploadResponse,
             status_code=status.HTTP_201_CREATED)
async def upload_documents_for_subject(
    subject_id: str,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """上传文档到知识库
    
    支持上传多个文件（最多20个）
    
    Args:
        subject_id: 知识库ID
        files: 文件列表
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少需要上传一个文件"
        )
    
    # 验证知识库是否存在
    subject_service = SubjectService()
    subject = subject_service.get_subject(subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知识库 {subject_id} 不存在"
        )
    
    service = DocumentService()
    
    try:
        # 上传文档
        result = await service.upload_documents_for_subject(subject_id, files)
        
        # 为每个上传的文件启动后台处理任务
        for uploaded_file in result["uploaded_files"]:
            background_tasks.add_task(
                service.process_document_for_subject,
                subject_id,
                uploaded_file["file_id"]
            )
        
        return DocumentUploadResponse(**result)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传文档失败: {str(e)}"
        )


@router.get("/api/subjects/{subject_id}/documents",
            response_model=DocumentListResponse)
async def list_documents_for_subject(subject_id: str):
    """获取知识库的所有文档列表
    
    Args:
        subject_id: 知识库ID
    """
    # 验证知识库是否存在
    subject_service = SubjectService()
    subject = subject_service.get_subject(subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知识库 {subject_id} 不存在"
        )
    
    service = DocumentService()
    
    try:
        documents = service.list_documents_for_subject(subject_id)
        
        return DocumentListResponse(
            documents=[DocumentDetailResponse(**doc) for doc in documents],
            total=len(documents)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文档列表失败: {str(e)}"
        )


@router.get("/api/subjects/{subject_id}/documents/{file_id}",
            response_model=DocumentDetailResponse)
async def get_document_for_subject(subject_id: str, file_id: str):
    """获取单个文档详情
    
    Args:
        subject_id: 知识库ID
        file_id: 文件ID
    """
    service = DocumentService()
    
    document = service.get_document_for_subject(subject_id, file_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文档 {file_id} 不存在"
        )
    
    return DocumentDetailResponse(**document)


@router.get("/api/subjects/{subject_id}/documents/{file_id}/status",
            response_model=DocumentStatusResponse)
async def get_document_status_for_subject(subject_id: str, file_id: str):
    """查询文档处理状态
    
    Args:
        subject_id: 知识库ID
        file_id: 文件ID
    """
    service = DocumentService()
    
    doc_status = await service.get_document_status_for_subject(subject_id, file_id)
    
    if not doc_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文档 {file_id} 不存在"
        )
    
    return DocumentStatusResponse(**doc_status)


@router.delete("/api/subjects/{subject_id}/documents/{file_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_for_subject(subject_id: str, file_id: str):
    """删除文档
    
    Args:
        subject_id: 知识库ID
        file_id: 文件ID
    """
    service = DocumentService()
    
    document = service.get_document_for_subject(subject_id, file_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文档 {file_id} 不存在"
        )
    
    success = await service.delete_document_for_subject(subject_id, file_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除文档失败"
        )
    
    return None


@router.get("/api/subjects/{subject_id}/documents/{file_id}/slides")
async def get_document_slides_for_subject(subject_id: str, file_id: str):
    """获取文档的所有幻灯片/页面列表（支持浏览器缓存）
    
    支持 PPTX 和 PDF 格式
    
    Args:
        subject_id: 知识库ID
        file_id: 文件ID
    """
    from fastapi.responses import JSONResponse
    import os
    import hashlib
    
    service = DocumentService()
    parser = DocumentParser()
    
    # 获取文档信息
    document = service.get_document_for_subject(subject_id, file_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文档 {file_id} 不存在"
        )
    
    # 检查文件类型
    file_ext = document["file_extension"]
    if file_ext not in ["pptx", "pdf"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此接口仅支持 PPTX 和 PDF 格式文件"
        )
    
    # 生成 ETag
    file_path = document["file_path"]
    file_stat = os.stat(file_path)
    etag = hashlib.md5(f"{file_path}{file_stat.st_mtime}".encode()).hexdigest()
    
    try:
        # 解析文档
        parsed_data = parser.parse(file_path)
        
        # 如果是PDF，需要将pages转换为slides格式
        if file_ext == "pdf":
            slides_data = []
            for page in parsed_data.get("pages", []):
                text_positions = []
                page_dimensions = None
                
                slide_data = {
                    "slide_number": page["page_number"],
                    "title": f"第 {page['page_number']} 页",
                    "text_content": page["text_content"],
                    "images": page.get("images", []),
                    "structure": page.get("structure", {}),
                    "text_positions": text_positions,
                    "slide_dimensions": page_dimensions
                }
                slides_data.append(slide_data)
            
            result = {
                "filename": document["filename"],
                "total_slides": parsed_data["total_pages"],
                "slides": slides_data
            }
        else:
            # PPTX
            for slide in parsed_data.get("slides", []):
                slide["text_positions"] = []
                slide["slide_dimensions"] = None
            
            result = {
                "filename": document["filename"],
                "total_slides": parsed_data["total_slides"],
                "slides": parsed_data["slides"]
            }
        
        # 返回带缓存头的响应
        return JSONResponse(
            content=result,
            headers={
                "Cache-Control": "public, max-age=3600",
                "ETag": f'"{etag}"'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"解析文档失败: {str(e)}"
        )


@router.get("/api/subjects/{subject_id}/documents/{file_id}/slides/{slide_id}",
            response_model=SlideResponse)
async def get_document_slide_for_subject(subject_id: str, file_id: str, slide_id: int):
    """获取单个幻灯片/页面内容和元数据
    
    支持 PPTX 和 PDF 格式
    
    Args:
        subject_id: 知识库ID
        file_id: 文件ID
        slide_id: 幻灯片/页面编号（从1开始）
    """
    service = DocumentService()
    parser = DocumentParser()
    
    # 获取文档信息
    document = service.get_document_for_subject(subject_id, file_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文档 {file_id} 不存在"
        )
    
    # 检查文件类型
    file_ext = document["file_extension"]
    if file_ext not in ["pptx", "pdf"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此接口仅支持 PPTX 和 PDF 格式文件"
        )
    
    try:
        # 解析文档
        parsed_data = parser.parse(document["file_path"])
        
        text_positions = []
        slide_dimensions = None
        
        if file_ext == "pdf":
            # PDF: 从 pages 中查找
            pages = parsed_data.get("pages", [])
            if slide_id < 1 or slide_id > len(pages):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"页面 {slide_id} 不存在（共 {len(pages)} 页）"
                )
            
            page = pages[slide_id - 1]
            slide_data = {
                "slide_number": page["page_number"],
                "title": f"第 {page['page_number']} 页",
                "text_content": page["text_content"],
                "images": page.get("images", []),
                "structure": page.get("structure", {}),
                "text_positions": text_positions,
                "slide_dimensions": slide_dimensions
            }
            return SlideResponse(**slide_data)
        else:
            # PPTX: 从 slides 中查找
            slides = parsed_data.get("slides", [])
            if slide_id < 1 or slide_id > len(slides):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"幻灯片 {slide_id} 不存在（共 {len(slides)} 张）"
                )
            
            slide = slides[slide_id - 1]
            slide["text_positions"] = text_positions
            slide["slide_dimensions"] = slide_dimensions
            return SlideResponse(**slide)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"解析文档失败: {str(e)}"
        )


@router.get("/api/subjects/{subject_id}/documents/{file_id}/slides/{slide_id}/image")
async def get_slide_image_for_subject(
    subject_id: str,
    file_id: str,
    slide_id: int,
    use_cache: bool = True
):
    """获取知识库文档的幻灯片/页面渲染图片
    
    Args:
        subject_id: 知识库ID
        file_id: 文件ID
        slide_id: 幻灯片/页面编号（从1开始）
        use_cache: 是否使用缓存（默认True）
    """
    service = DocumentService()
    
    # 获取文档信息
    document = service.get_document_for_subject(subject_id, file_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文档 {file_id} 不存在"
        )
    
    file_extension = document["file_extension"]
    if file_extension not in ["pptx", "pdf"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此接口仅支持 PPTX 和 PDF 格式文件"
        )
    
    try:
        # 渲染图片
        image_path = image_renderer.get_image_path(
            file_path=document["file_path"],
            slide_number=slide_id,
            file_id=file_id,
            file_extension=file_extension,
            use_cache=use_cache,
            is_thumbnail=False
        )
        
        if not image_path or not image_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"图片渲染失败：无法生成幻灯片 {slide_id} 的图片"
            )
        
        # 返回文件响应
        response = FileResponse(
            path=str(image_path),
            media_type="image/png",
            filename=f"slide_{slide_id}.png"
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取图片失败: {str(e)}"
        )


@router.get("/api/subjects/{subject_id}/documents/{file_id}/slides/{slide_id}/thumbnail")
async def get_slide_thumbnail_for_subject(
    subject_id: str,
    file_id: str,
    slide_id: int,
    use_cache: bool = True
):
    """获取知识库文档的幻灯片/页面缩略图
    
    Args:
        subject_id: 知识库ID
        file_id: 文件ID
        slide_id: 幻灯片/页面编号（从1开始）
        use_cache: 是否使用缓存（默认True）
    """
    service = DocumentService()
    
    # 获取文档信息
    document = service.get_document_for_subject(subject_id, file_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文档 {file_id} 不存在"
        )
    
    file_extension = document["file_extension"]
    if file_extension not in ["pptx", "pdf"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此接口仅支持 PPTX 和 PDF 格式文件"
        )
    
    try:
        # 渲染缩略图
        image_path = image_renderer.get_image_path(
            file_path=document["file_path"],
            slide_number=slide_id,
            file_id=file_id,
            file_extension=file_extension,
            use_cache=use_cache,
            is_thumbnail=True
        )
        
        if not image_path or not image_path.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"缩略图渲染失败：无法生成幻灯片 {slide_id} 的缩略图"
            )
        
        # 返回文件响应
        response = FileResponse(
            path=str(image_path),
            media_type="image/png",
            filename=f"slide_{slide_id}_thumb.png"
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取缩略图失败: {str(e)}"
        )

