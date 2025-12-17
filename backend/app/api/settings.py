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
        "Pro/Qwen/Qwen2.5-VL-7B-Instruct",
        "zai-org/GLM-4.6V",
        "Qwen/Qwen2.5-72B-Instruct",
        "Qwen/Qwen2.5-32B-Instruct",
        "Qwen/Qwen2.5-14B-Instruct",
        "Qwen/Qwen2.5-7B-Instruct",
        "Qwen/Qwen3-Embedding-0.6B",
        "BAAI/bge-m3",
        "Qwen/Qwen3-Embedding-4B"
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
        包含所有场景配置的字典，不包含 API Key
    """
    all_configs = config_service.get_all_configs()
    return {
        "knowledge_graph": all_configs["knowledge_graph"],
        "chat": all_configs["chat"],
        "mindmap": all_configs["mindmap"],
        "embedding": all_configs.get("embedding", {}),
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
    if scene not in ["knowledge_graph", "chat", "mindmap", "embedding"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的场景名称: {scene}，必须是 knowledge_graph, chat, mindmap 或 embedding"
        )
    
    # 验证 binding
    # 所有场景都支持：openai, siliconflow, ollama
    allowed_bindings = ["openai", "siliconflow", "ollama"]
    if config_data.binding not in allowed_bindings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的服务商: {config_data.binding}，{scene} 场景只支持 {', '.join(allowed_bindings)}"
        )
    
    # 根据 binding 确定 host
    # 如果 binding 是 siliconflow，使用硅基流动地址
    # 否则使用传入的 host
    if config_data.binding == "siliconflow":
        fixed_host = SILICONFLOW_HOST
    else:
        fixed_host = config_data.host
    
    # 更新配置
    config_service.update_config(
        scene=scene,
        binding=config_data.binding,
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

