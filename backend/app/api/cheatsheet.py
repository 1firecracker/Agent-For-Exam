"""Cheatsheet API"""
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.services.cheatsheet_service import CheatsheetService

router = APIRouter(tags=["cheatsheet"])


class CheatsheetRequest(BaseModel):
    include_images: bool = False


@router.post("/api/subjects/{subject_id}/cheatsheet/generate")
async def generate_cheatsheet(subject_id: str, request: CheatsheetRequest):
    """流式生成 Cheatsheet

    Returns:
        NDJSON stream:
        - {"image_refs": [...]}  (如果 include_images=true，首行返回图片引用列表)
        - {"content": "..."}    (流式文本片段)
        - {"error": "..."}      (错误)
    """
    service = CheatsheetService()

    return StreamingResponse(
        service.generate_stream(subject_id, request.include_images),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
