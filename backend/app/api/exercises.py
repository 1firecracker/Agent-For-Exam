"""样本试题管理API路由"""
from fastapi import APIRouter, File, UploadFile, HTTPException, status, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, Response
from typing import List
from pydantic import BaseModel
from pathlib import Path

from app.services.exercise_service import ExerciseService

router = APIRouter()


# 响应模型
class SampleUploadResponse(BaseModel):
    """样本试题上传响应"""
    conversation_id: str
    uploaded_samples: List[dict]
    total_samples: int


class SampleListResponse(BaseModel):
    """样本试题列表响应"""
    samples: List[dict]
    total: int




@router.post(
    "/api/conversations/{conversation_id}/exercises/samples/upload",
    response_model=SampleUploadResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_samples(
    conversation_id: str,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """上传样本试题
    
    支持上传多个文件（PDF/DOCX/TXT格式）
    文件上传后立即返回，解析在后台异步进行
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少需要上传一个文件"
        )
    
    service = ExerciseService()
    
    try:
        result = await service.upload_samples(conversation_id, files)
        
        # 添加后台任务：异步解析每个文件
        for sample_info in result["uploaded_samples"]:
            sample_id = sample_info["sample_id"]
            sample_dir = service._get_sample_dir(conversation_id, sample_id)
            # 从元数据中获取文件路径，或查找原始文件
            metadata_file = service._get_metadata_file(conversation_id, sample_id)
            original_file_path = None
            
            if metadata_file.exists():
                import json
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    rel_path = metadata.get("original_file_path")
                    if rel_path:
                        original_file_path = sample_dir / rel_path
            
            # 如果元数据中没有路径，查找文件
            if not original_file_path or not original_file_path.exists():
                for f in sample_dir.iterdir():
                    if f.is_file() and f.suffix.lower() in ['.pdf', '.docx', '.txt']:
                        original_file_path = f
                        break
            
            if original_file_path and original_file_path.exists():
                background_tasks.add_task(
                    service._parse_sample_async,
                    conversation_id,
                    sample_id,
                    original_file_path
                )
        
        return SampleUploadResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传样本试题失败: {str(e)}"
        )


@router.get(
    "/api/conversations/{conversation_id}/exercises/samples",
    response_model=SampleListResponse
)
async def list_samples(conversation_id: str):
    """获取样本试题列表"""
    service = ExerciseService()
    
    try:
        samples = service.list_samples(conversation_id)
        return SampleListResponse(
            samples=samples,
            total=len(samples)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取样本试题列表失败: {str(e)}"
        )


@router.get(
    "/api/conversations/{conversation_id}/exercises/samples/{sample_id}"
)
async def get_sample(conversation_id: str, sample_id: str):
    """获取样本试题详情"""
    service = ExerciseService()
    sample = service.get_sample(conversation_id, sample_id)
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"样本试题 {sample_id} 不存在"
        )
    
    return JSONResponse(content=sample)


@router.get(
    "/api/conversations/{conversation_id}/exercises/samples/{sample_id}/status"
)
async def get_sample_status(conversation_id: str, sample_id: str):
    """获取样本试题解析状态"""
    service = ExerciseService()
    sample = service.get_sample(conversation_id, sample_id)
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"样本试题 {sample_id} 不存在"
        )
    
    return {
        "sample_id": sample_id,
        "conversation_id": conversation_id,
        "status": sample.get("status", "unknown"),
        "parse_start_time": sample.get("parse_start_time"),
        "parse_end_time": sample.get("parse_end_time"),
        "error": sample.get("error"),
        "text_length": sample.get("text_length", 0),
        "image_count": sample.get("image_count", 0)
    }


@router.delete(
    "/api/conversations/{conversation_id}/exercises/samples/{sample_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_sample(conversation_id: str, sample_id: str):
    """删除样本试题"""
    service = ExerciseService()
    
    try:
        success = service.delete_sample(conversation_id, sample_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"样本试题 {sample_id} 不存在"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除样本试题失败: {str(e)}"
        )


@router.get(
    "/api/conversations/{conversation_id}/exercises/samples/{sample_id}/text"
)
async def get_sample_text(conversation_id: str, sample_id: str):
    """获取样本试题文本内容"""
    service = ExerciseService()
    
    try:
        text = service.get_sample_text(conversation_id, sample_id)
        if text is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"样本试题 {sample_id} 不存在"
            )
        return {"text": text}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取样本试题文本失败: {str(e)}"
        )


@router.get(
    "/api/conversations/{conversation_id}/exercises/samples/{sample_id}/images/{image_name}"
)
async def get_sample_image(
    conversation_id: str,
    sample_id: str,
    image_name: str
):
    """获取样本试题图片"""
    from pathlib import Path
    import app.config as config
    
    # 构建图片路径
    exercises_dir = Path(config.settings.exercises_dir)
    image_path = exercises_dir / conversation_id / "samples" / sample_id / "images" / image_name
    
    if not image_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"图片 {image_name} 不存在"
        )
    
    return FileResponse(
        path=str(image_path),
        media_type=f"image/{Path(image_name).suffix.lstrip('.')}"
    )


@router.get(
    "/api/conversations/{conversation_id}/exercises/samples/{sample_id}/file"
)
async def get_sample_file(
    conversation_id: str,
    sample_id: str
):
    """获取样本试题原始文件"""
    from pathlib import Path
    import app.config as config
    
    service = ExerciseService()
    sample = service.get_sample(conversation_id, sample_id)
    
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"样本试题 {sample_id} 不存在"
        )
    
    # 获取原始文件路径
    sample_dir = service._get_sample_dir(conversation_id, sample_id)
    original_filename = sample.get("original_filename", sample.get("filename", ""))
    file_path = sample_dir / original_filename if original_filename else None
    
    # 如果原始文件不存在，尝试在样本目录中查找
    if not file_path or not file_path.exists():
        for f in sample_dir.iterdir():
            if f.is_file() and f.suffix.lower() in ['.pdf', '.docx', '.txt']:
                file_path = f
                break
    
    if not file_path or not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="原始文件不存在"
        )
    
    # 根据文件类型设置 media_type
    file_ext = file_path.suffix.lower()
    media_type_map = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.doc': 'application/msword',
        '.txt': 'text/plain'
    }
    media_type = media_type_map.get(file_ext, 'application/octet-stream')
    
    # 读取文件内容
    with open(file_path, 'rb') as f:
        file_content = f.read()
    
    # 设置响应头，强制内联显示（不下载）
    headers = {
        'Content-Disposition': f'inline; filename="{original_filename}"'
    }
    
    return Response(
        content=file_content,
        media_type=media_type,
        headers=headers
    )

