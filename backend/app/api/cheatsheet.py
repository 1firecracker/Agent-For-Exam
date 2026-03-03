"""Cheatsheet API"""
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

from app.services.cheatsheet_service import CheatsheetService

router = APIRouter(tags=["cheatsheet"])


class CheatsheetRequest(BaseModel):
    include_images: bool = False
    file_ids: Optional[List[str]] = None


@router.post("/api/subjects/{subject_id}/cheatsheet/generate")
async def generate_cheatsheet(subject_id: str, request: CheatsheetRequest):
    """流式生成 Cheatsheet"""
    service = CheatsheetService()

    return StreamingResponse(
        service.generate_stream(subject_id, request.include_images, request.file_ids),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
