"""
设置 API

提供 LLM 配置的获取和更新接口
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict
from app.services.config_service import config_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


# 支持的模型列表（仅硅基流动）
MODEL_LISTS = {
    "siliconflow": [
        "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
        "deepseek-ai/DeepSeek-V3",
        "deepseek-ai/DeepSeek-V3.2-Exp",
        "MiniMaxAI/MiniMax-M2",
        "moonshotai/Kimi-K2-Thinking",
        "Qwen/Qwen2.5-72B-Instruct",
        "Qwen/Qwen2.5-32B-Instruct",
        "Qwen/Qwen2.5-14B-Instruct",
        "Qwen/Qwen2.5-7B-Instruct",
    ]
}

# 固定使用硅基流动
SILICONFLOW_HOST = "https://api.siliconflow.cn/v1"


class LLMConfigUpdate(BaseModel):
    """LLM 配置更新请求"""
    binding: str
    model: str
    host: str
    api_key: Optional[str] = None  # 可选，如果不提供则不更新


@router.get("/llm-config")
async def get_llm_config():
    """获取所有场景的 LLM 配置
    
    Returns:
        包含三个场景配置的字典，不包含 API Key
    """
    return {
        "knowledge_graph": config_service.get_all_configs()["knowledge_graph"],
        "chat": config_service.get_all_configs()["chat"],
        "mindmap": config_service.get_all_configs()["mindmap"],
        "model_lists": MODEL_LISTS
    }


@router.post("/llm-config/{scene}")
async def update_llm_config(scene: str, config_data: LLMConfigUpdate):
    """更新指定场景的 LLM 配置
    
    Args:
        scene: 场景名称（knowledge_graph, chat, mindmap）
        config_data: 配置数据
        
    Returns:
        更新后的配置（不包含 API Key）
    """
    if scene not in ["knowledge_graph", "chat", "mindmap"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的场景名称: {scene}，必须是 knowledge_graph, chat 或 mindmap"
        )
    
    # 验证 binding（只支持硅基流动）
    if config_data.binding != "siliconflow":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的服务商: {config_data.binding}，当前只支持 siliconflow"
        )
    
    # 固定使用硅基流动地址
    fixed_host = SILICONFLOW_HOST
    
    # 更新配置
    config_service.update_config(
        scene=scene,
        binding="siliconflow",
        model=config_data.model,
        host=fixed_host,
        api_key=config_data.api_key
    )
    
    # 返回更新后的配置（不包含 API Key）
    updated_config = config_service.get_all_configs()[scene]
    return {
        "status": "success",
        "message": f"{scene} 配置已更新并立即生效",
        "config": updated_config
    }


@router.get("/model-lists")
async def get_model_lists():
    """获取支持的模型列表"""
    return {
        "model_lists": MODEL_LISTS
    }

