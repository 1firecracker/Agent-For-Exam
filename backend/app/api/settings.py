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
        "Qwen/Qwen3-Embedding-4B",
        "PaddlePaddle/PaddleOCR-VL-1.5",
        "deepseek-ai/DeepSeek-OCR"
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


class ProviderAPIKeyUpdate(BaseModel):
    """统一服务商 API Key 更新请求"""
    api_key: str


def _get_merged_model_lists() -> Dict[str, list]:
    """合并内置模型、远程同步模型和用户自定义模型。"""
    custom_models = config_service.get_custom_models()
    remote_models = config_service.get_remote_models()
    merged_model_lists = {}

    bindings = set(MODEL_LISTS.keys()) | set(remote_models.keys())
    for binding in bindings:
        default_models = MODEL_LISTS.get(binding, [])
        remote_list = remote_models.get(binding, [])
        custom_list = custom_models.get(binding, [])
        merged_model_lists[binding] = list(dict.fromkeys(default_models + remote_list + custom_list))

    return merged_model_lists


@router.get("/llm-config")
async def get_llm_config():
    """获取所有场景的 LLM 配置
    
    Returns:
        包含所有场景配置的字典，不包含 API Key
    """
    all_configs = config_service.get_all_configs()
    merged_model_lists = _get_merged_model_lists()
    
    return {
        "knowledge_graph": all_configs["knowledge_graph"],
        "chat": all_configs["chat"],
        "mindmap": all_configs["mindmap"],
        "embedding": all_configs.get("embedding", {}),
        "ocr": all_configs.get("ocr", {}),
        "model_lists": merged_model_lists,
        "providers": config_service.get_provider_status()
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
    if scene not in ["knowledge_graph", "chat", "mindmap", "embedding", "ocr"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的场景名称: {scene}，必须是 knowledge_graph, chat, mindmap, embedding 或 ocr"
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
    
    # 更新配置（会自动添加自定义模型）
    config_service.update_config(
        scene=scene,
        binding=config_data.binding,
        model=config_data.model,
        host=fixed_host,
        api_key=config_data.api_key
    )
    
    all_configs = config_service.get_all_configs()
    merged_model_lists = _get_merged_model_lists()
    
    updated_config = all_configs[scene]
    return {
        "status": "success",
        "message": f"{scene} 配置已更新并立即生效",
        "config": updated_config,
        "model_lists": merged_model_lists,
        "providers": config_service.get_provider_status()
    }


@router.get("/model-lists")
async def get_model_lists():
    """获取支持的模型列表（包含自定义模型）"""
    return {
        "model_lists": _get_merged_model_lists(),
        "providers": config_service.get_provider_status()
    }


@router.post("/providers/{binding}/api-key")
async def update_provider_api_key(binding: str, payload: ProviderAPIKeyUpdate):
    """更新统一服务商 API Key。"""
    if binding != "siliconflow":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="目前仅支持 siliconflow 的统一 API Key"
        )
    if not payload.api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API Key 不能为空"
        )

    config_service.update_provider_api_key(binding, payload.api_key)

    refresh_result = None
    refresh_error = ""
    try:
        refresh_result = await config_service.refresh_provider_models(binding)
    except Exception as exc:
        refresh_error = str(exc)

    return {
        "status": "success",
        "message": "统一 API Key 已更新",
        "providers": config_service.get_provider_status(),
        "model_lists": _get_merged_model_lists(),
        "refresh": refresh_result,
        "refresh_error": refresh_error
    }


@router.post("/providers/{binding}/models/refresh")
async def refresh_provider_models(binding: str):
    """手动刷新服务商模型列表。"""
    if binding != "siliconflow":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="目前仅支持刷新 siliconflow 的模型列表"
        )
    try:
        refresh_result = await config_service.refresh_provider_models(binding)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"刷新模型列表失败: {exc}")

    return {
        "status": "success",
        "refresh": refresh_result,
        "providers": config_service.get_provider_status(),
        "model_lists": _get_merged_model_lists()
    }
