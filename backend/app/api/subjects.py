from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.services.subject_service import SubjectService
from app.services.conversation_service import ConversationService
from app.api.conversations import ConversationResponse, ConversationListResponse


router = APIRouter(prefix="/api/subjects", tags=["subjects"])


class SubjectCreateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class SubjectResponse(BaseModel):
    subject_id: str
    name: str
    description: str
    created_at: str
    updated_at: str


@router.post("", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(request: SubjectCreateRequest) -> SubjectResponse:
    service = SubjectService()
    subject_id = service.create_subject(request.name, request.description)
    subject = service.get_subject(subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="知识库创建失败",
        )
    return SubjectResponse(**subject)


@router.get("", response_model=List[SubjectResponse])
async def list_subjects() -> List[SubjectResponse]:
    service = SubjectService()
    subjects = service.list_subjects()
    return [SubjectResponse(**s) for s in subjects]


@router.get("/{subject_id}", response_model=SubjectResponse)
async def get_subject(subject_id: str) -> SubjectResponse:
    service = SubjectService()
    subject = service.get_subject(subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知识库 {subject_id} 不存在",
        )
    return SubjectResponse(**subject)


class SubjectConversationCreateRequest(BaseModel):
    title: Optional[str] = None


@router.get(
    "/{subject_id}/conversations",
    response_model=ConversationListResponse,
)
async def list_subject_conversations(
    subject_id: str, status_filter: Optional[str] = None
) -> ConversationListResponse:
    subject_service = SubjectService()
    subject = subject_service.get_subject(subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知识库 {subject_id} 不存在",
        )

    service = ConversationService()
    conversations = service.list_conversations_by_subject(subject_id, status=status_filter)
    return ConversationListResponse(
        conversations=[ConversationResponse(**c) for c in conversations],
        total=len(conversations),
    )


@router.post(
    "/{subject_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subject_conversation(
    subject_id: str, request: SubjectConversationCreateRequest
) -> ConversationResponse:
    subject_service = SubjectService()
    subject = subject_service.get_subject(subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知识库 {subject_id} 不存在",
        )

    service = ConversationService()
    conversation_id = service.create_conversation(title=request.title, subject_id=subject_id)
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="对话创建失败",
        )
    return ConversationResponse(**conversation)


class SubjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


@router.patch("/{subject_id}", response_model=SubjectResponse)
async def update_subject(subject_id: str, request: SubjectUpdateRequest) -> SubjectResponse:
    """更新知识库信息"""
    service = SubjectService()
    subject = service.get_subject(subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知识库 {subject_id} 不存在",
        )
    
    success = service.update_subject(
        subject_id,
        name=request.name,
        description=request.description
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新知识库失败",
        )
    
    updated_subject = service.get_subject(subject_id)
    return SubjectResponse(**updated_subject)


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(subject_id: str):
    """删除知识库及所有相关数据"""
    service = SubjectService()
    subject = service.get_subject(subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知识库 {subject_id} 不存在",
        )
    
    success = service.delete_subject(subject_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除知识库失败",
        )
    
    return None


