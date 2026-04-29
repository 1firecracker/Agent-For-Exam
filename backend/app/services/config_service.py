"""
配置管理服务

负责管理分场景的 LLM 配置，支持：
- JSON 文件存储
- API Key 加密存储
- 运行时配置更新（立即生效）
"""
import json
import base64
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from cryptography.fernet import Fernet
import httpx
import app.config as config

# 配置文件名
CONFIG_FILE = Path(config.BASE_DIR) / "data" / "llm_config.json"

# 加密密钥文件路径
_KEY_FILE = Path(config.BASE_DIR) / "data" / ".encryption_key"

def _get_or_create_key() -> bytes:
    """获取或创建加密密钥"""
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes()
    else:
        key = Fernet.generate_key()
        _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _KEY_FILE.write_bytes(key)
        return key

def _get_cipher():
    """获取加密器"""
    key = _get_or_create_key()
    return Fernet(key)


def _encrypt_api_key(api_key: str) -> str:
    """加密 API Key"""
    if not api_key:
        return ""
    cipher = _get_cipher()
    return cipher.encrypt(api_key.encode()).decode()


def _decrypt_api_key(encrypted_key: str) -> str:
    """解密 API Key"""
    if not encrypted_key:
        return ""
    cipher = _get_cipher()
    return cipher.decrypt(encrypted_key.encode()).decode()


class ConfigService:
    """配置管理服务"""
    
    def __init__(self):
        self.config_file = CONFIG_FILE
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self._config_cache: Optional[Dict] = None
    
    def _load_config(self, force_reload: bool = False) -> Dict:
        """加载配置文件
        
        Args:
            force_reload: 如果为 True，强制重新加载（忽略缓存）
        """
        if force_reload:
            self._config_cache = None
        
        if self._config_cache is not None:
            return self._config_cache
        
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._config_cache = json.load(f)
            self._ensure_config_shape()
        else:
            # 初始化默认配置（从环境变量或全局配置读取）
            # 如果全局配置有 API Key，则加密存储
            kg_api_key_encrypted = ""
            if config.settings.kg_llm_binding_api_key:
                kg_api_key_encrypted = _encrypt_api_key(config.settings.kg_llm_binding_api_key)
            
            chat_api_key_encrypted = ""
            if config.settings.chat_llm_binding_api_key:
                chat_api_key_encrypted = _encrypt_api_key(config.settings.chat_llm_binding_api_key)
            
            mindmap_api_key_encrypted = ""
            if config.settings.mindmap_llm_binding_api_key:
                mindmap_api_key_encrypted = _encrypt_api_key(config.settings.mindmap_llm_binding_api_key)
            
            # 默认使用硅基流动
            default_binding = "siliconflow"
            default_host = "https://api.siliconflow.cn/v1"
            
            # Embedding API Key（使用全局 LLM API Key 作为默认值）
            embedding_api_key_encrypted = ""
            if config.settings.llm_binding_api_key:
                embedding_api_key_encrypted = _encrypt_api_key(config.settings.llm_binding_api_key)
            
            default_api_key = config.settings.llm_binding_api_key or config.settings.chat_llm_binding_api_key or config.settings.kg_llm_binding_api_key or config.settings.mindmap_llm_binding_api_key
            
            self._config_cache = {
                "provider_api_keys": {
                    "siliconflow": _encrypt_api_key(default_api_key) if default_api_key else ""
                },
                "knowledge_graph": {
                    "binding": default_binding,
                    "model": config.settings.kg_llm_model or config.settings.llm_model or "",
                    "host": config.settings.kg_llm_binding_host or config.settings.llm_binding_host or default_host,
                    "api_key_encrypted": kg_api_key_encrypted or (_encrypt_api_key(config.settings.llm_binding_api_key) if config.settings.llm_binding_api_key else "")
                },
                "chat": {
                    "binding": default_binding,
                    "model": config.settings.chat_llm_model or config.settings.llm_model or "",
                    "host": config.settings.chat_llm_binding_host or config.settings.llm_binding_host or default_host,
                    "api_key_encrypted": chat_api_key_encrypted or (_encrypt_api_key(config.settings.llm_binding_api_key) if config.settings.llm_binding_api_key else "")
                },
                "mindmap": {
                    "binding": default_binding,
                    "model": config.settings.mindmap_llm_model or config.settings.llm_model or "",
                    "host": config.settings.mindmap_llm_binding_host or config.settings.llm_binding_host or default_host,
                    "api_key_encrypted": mindmap_api_key_encrypted or (_encrypt_api_key(config.settings.llm_binding_api_key) if config.settings.llm_binding_api_key else "")
                },
                "embedding": {
                    "binding": config.settings.embedding_binding or "siliconflow",
                    "model": config.settings.embedding_model or "Qwen/Qwen3-Embedding-0.6B",
                    "host": config.settings.embedding_binding_host or config.settings.llm_binding_host or default_host,
                    "api_key_encrypted": embedding_api_key_encrypted
                },
                "ocr": {
                    "binding": "siliconflow",
                    "model": "PaddlePaddle/PaddleOCR-VL-1.5",
                    "host": default_host,
                    "api_key_encrypted": _encrypt_api_key(config.settings.llm_binding_api_key) if config.settings.llm_binding_api_key else ""
                },
                "custom_models": {
                    "siliconflow": []  # 用户自定义的模型列表
                },
                "remote_models": {
                    "siliconflow": []
                },
                "model_sync": {
                    "siliconflow": {
                        "last_synced_at": "",
                        "last_error": ""
                    }
                }
            }
            self._save_config()
        
        return self._config_cache

    def _ensure_config_shape(self):
        """补齐新版本配置字段，并规范历史 siliconflow 配置。"""
        changed = False
        config_data = self._config_cache or {}

        if "provider_api_keys" not in config_data:
            config_data["provider_api_keys"] = {}
            changed = True
        if "remote_models" not in config_data:
            config_data["remote_models"] = {"siliconflow": []}
            changed = True
        if "model_sync" not in config_data:
            config_data["model_sync"] = {
                "siliconflow": {
                    "last_synced_at": "",
                    "last_error": ""
                }
            }
            changed = True

        for scene in ["knowledge_graph", "chat", "mindmap", "embedding", "ocr"]:
            scene_config = config_data.get(scene)
            if not scene_config:
                continue
            host = scene_config.get("host", "")
            if "siliconflow.cn" in host and scene_config.get("binding") != "siliconflow":
                scene_config["binding"] = "siliconflow"
                changed = True

        self._config_cache = config_data
        if changed:
            self._save_config()
    
    def _save_config(self):
        """保存配置文件"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self._config_cache, f, ensure_ascii=False, indent=2)
    
    def get_config(self, scene: str, force_reload: bool = True) -> Dict[str, str]:
        """获取指定场景的配置
        
        Args:
            scene: 场景名称（knowledge_graph, chat, mindmap）
            force_reload: 如果为 True，强制重新加载配置（忽略缓存），默认为 True 确保获取最新配置
            
        Returns:
            配置字典，包含 binding, model, host, api_key（已解密）
        """
        config_data = self._load_config(force_reload=force_reload)
        scene_config = config_data.get(scene, {})
        
        # 解密 API Key
        encrypted_key = scene_config.get("api_key_encrypted", "")
        api_key = _decrypt_api_key(encrypted_key) if encrypted_key else ""
        if not api_key:
            api_key = self.get_provider_api_key(scene_config.get("binding", "siliconflow"), force_reload=False)
        
        result = {
            "binding": scene_config.get("binding", "siliconflow"),
            "model": scene_config.get("model", ""),
            "host": scene_config.get("host", "https://api.siliconflow.cn/v1"),
            "api_key": api_key
        }
        
        # 调试输出
        config.get_logger("app.config").info(
            "读取场景配置",
            extra={
                "event": "config.read_scene",
                "scene": scene,
                "binding": result["binding"],
                "model": result["model"],
                "host": result["host"][:50] if result["host"] else "None",
            },
        )
        
        return result
    
    def update_config(self, scene: str, binding: str, model: str, host: str, api_key: Optional[str] = None):
        """更新指定场景的配置
        
        Args:
            scene: 场景名称（knowledge_graph, chat, mindmap）
            binding: 服务商（openai, siliconflow）
            model: 模型名称
            host: API 地址
            api_key: API Key（可选，如果不提供则不更新）
        """
        config_data = self._load_config()
        
        if scene not in config_data:
            config_data[scene] = {}
        
        config_data[scene]["binding"] = binding
        config_data[scene]["model"] = model
        config_data[scene]["host"] = host
        
        # 向后兼容：旧前端可能仍会在场景配置中提交 API Key。
        # 新逻辑统一保存到 provider_api_keys，所有相同 provider 的场景共享。
        if api_key is not None:
            if api_key.strip():
                self.update_provider_api_key(binding, api_key)
            else:
                # 如果传入空字符串，保留原有密钥（不更新）
                pass
        
        # 如果模型不在默认列表中，添加到自定义模型列表
        if model and binding:
            self._add_custom_model(binding, model)
        
        # 更新缓存并保存
        self._config_cache = config_data
        self._save_config()
        
        # 立即更新全局配置（立即生效）
        self._apply_to_global_config(scene)

    def get_provider_api_key(self, binding: str = "siliconflow", force_reload: bool = True) -> str:
        """获取统一服务商 API Key（已解密）。"""
        config_data = self._load_config(force_reload=force_reload)
        provider_keys = config_data.get("provider_api_keys", {})
        encrypted_key = provider_keys.get(binding, "")
        if encrypted_key:
            return _decrypt_api_key(encrypted_key)

        # 兼容历史配置：如果统一 Key 不存在，从场景 Key 中挑一个可用的。
        for scene in ["chat", "knowledge_graph", "mindmap", "embedding", "ocr"]:
            scene_config = config_data.get(scene, {})
            if scene_config.get("binding", "siliconflow") != binding:
                continue
            scene_key = scene_config.get("api_key_encrypted", "")
            if scene_key:
                return _decrypt_api_key(scene_key)

        if binding == "siliconflow":
            return config.settings.llm_binding_api_key or ""
        return ""

    def update_provider_api_key(self, binding: str, api_key: str):
        """更新统一服务商 API Key。"""
        config_data = self._load_config()
        if "provider_api_keys" not in config_data:
            config_data["provider_api_keys"] = {}
        config_data["provider_api_keys"][binding] = _encrypt_api_key(api_key.strip()) if api_key.strip() else ""
        self._config_cache = config_data
        self._save_config()

        if binding == "siliconflow":
            config.settings.llm_binding_api_key = api_key.strip()
            for scene in ["knowledge_graph", "chat", "mindmap"]:
                self._apply_to_global_config(scene)

    def get_provider_status(self) -> Dict[str, Dict[str, str]]:
        """获取服务商统一配置状态（不返回明文 Key）。"""
        config_data = self._load_config()
        sync_data = config_data.get("model_sync", {})
        return {
            "siliconflow": {
                "has_api_key": bool(self.get_provider_api_key("siliconflow", force_reload=False)),
                "host": "https://api.siliconflow.cn/v1",
                "last_synced_at": sync_data.get("siliconflow", {}).get("last_synced_at", ""),
                "last_error": sync_data.get("siliconflow", {}).get("last_error", "")
            }
        }
    
    def _add_custom_model(self, binding: str, model: str):
        """添加自定义模型到列表
        
        Args:
            binding: 服务商名称
            model: 模型名称
        """
        config_data = self._load_config()
        
        # 确保 custom_models 字段存在
        if "custom_models" not in config_data:
            config_data["custom_models"] = {}
        
        if binding not in config_data["custom_models"]:
            config_data["custom_models"][binding] = []
        
        # 如果模型不在列表中，则添加
        if model not in config_data["custom_models"][binding]:
            config_data["custom_models"][binding].append(model)
            self._config_cache = config_data
            self._save_config()
    
    def get_custom_models(self) -> Dict[str, list]:
        """获取自定义模型列表
        
        Returns:
            自定义模型字典，key 为 binding，value 为模型列表
        """
        config_data = self._load_config()
        return config_data.get("custom_models", {})

    def get_remote_models(self) -> Dict[str, list]:
        """获取远程同步的模型列表。"""
        config_data = self._load_config()
        return config_data.get("remote_models", {})

    async def refresh_provider_models(self, binding: str = "siliconflow") -> Dict[str, object]:
        """从模型服务商拉取可用模型列表并保存。"""
        if binding != "siliconflow":
            raise ValueError(f"暂不支持刷新 {binding} 的模型列表")

        api_key = self.get_provider_api_key(binding)
        if not api_key:
            raise ValueError("请先配置统一 API Key")

        host = "https://api.siliconflow.cn/v1"
        config_data = self._load_config()
        for scene in ["chat", "knowledge_graph", "mindmap", "embedding", "ocr"]:
            scene_config = config_data.get(scene, {})
            if scene_config.get("binding") == binding and scene_config.get("host"):
                host = scene_config["host"].rstrip("/")
                break

        url = f"{host.rstrip('/')}/models"
        model_ids = []
        last_error = ""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                response.raise_for_status()
                payload = response.json()

            for item in payload.get("data", []):
                model_id = item.get("id")
                if model_id:
                    model_ids.append(model_id)
            model_ids = list(dict.fromkeys(model_ids))
        except Exception as exc:
            last_error = str(exc)
            config.get_logger("app.config").warning(
                "刷新远程模型列表失败",
                extra={
                    "event": "config.refresh_models_failed",
                    "binding": binding,
                    "error_message": last_error,
                },
            )
            raise
        finally:
            config_data = self._load_config()
            if "model_sync" not in config_data:
                config_data["model_sync"] = {}
            config_data["model_sync"][binding] = {
                "last_synced_at": datetime.utcnow().isoformat(timespec="seconds") + "Z" if not last_error else config_data.get("model_sync", {}).get(binding, {}).get("last_synced_at", ""),
                "last_error": last_error
            }
            self._config_cache = config_data
            self._save_config()

        config_data = self._load_config()
        if "remote_models" not in config_data:
            config_data["remote_models"] = {}
        config_data["remote_models"][binding] = model_ids
        if "model_sync" not in config_data:
            config_data["model_sync"] = {}
        config_data["model_sync"][binding] = {
            "last_synced_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "last_error": ""
        }
        self._config_cache = config_data
        self._save_config()

        return {
            "binding": binding,
            "models": model_ids,
            "count": len(model_ids),
            "last_synced_at": config_data["model_sync"][binding]["last_synced_at"]
        }
    
    def _apply_to_global_config(self, scene: str):
        """将配置应用到全局 settings（立即生效）"""
        config_data = self.get_config(scene)
        
        if scene == "knowledge_graph":
            config.settings.kg_llm_binding = config_data["binding"]
            config.settings.kg_llm_model = config_data["model"]
            config.settings.kg_llm_binding_host = config_data["host"]
            config.settings.kg_llm_binding_api_key = config_data["api_key"]
            
            # 清除已缓存的 LightRAG 实例，强制重新创建（使用新配置）
            # 延迟导入避免循环依赖
            try:
                from app.services.lightrag_service import LightRAGService
                lightrag_service = LightRAGService()
                lightrag_service.clear_all_instances()
            except Exception as e:
                config.get_logger("app.config").warning(
                    "清除 LightRAG 实例缓存失败",
                    extra={
                        "event": "config.clear_lightrag_failed",
                        "scene": scene,
                        "error_message": str(e),
                    },
                )
        elif scene == "chat":
            config.settings.chat_llm_binding = config_data["binding"]
            config.settings.chat_llm_model = config_data["model"]
            config.settings.chat_llm_binding_host = config_data["host"]
            config.settings.chat_llm_binding_api_key = config_data["api_key"]
        elif scene == "mindmap":
            config.settings.mindmap_llm_binding = config_data["binding"]
            config.settings.mindmap_llm_model = config_data["model"]
            config.settings.mindmap_llm_binding_host = config_data["host"]
            config.settings.mindmap_llm_binding_api_key = config_data["api_key"]
        elif scene == "embedding":
            config.settings.embedding_binding = config_data["binding"]
            config.settings.embedding_model = config_data["model"]
            config.settings.embedding_binding_host = config_data["host"]
            # embedding API Key 存储在配置服务中，lightrag_service 会直接从配置服务读取
            # 这里只更新全局配置的 binding、model、host，API Key 由配置服务管理
            
            # 清除已缓存的 LightRAG 实例，强制重新创建（使用新配置）
            try:
                from app.services.lightrag_service import LightRAGService
                lightrag_service = LightRAGService()
                lightrag_service.clear_all_instances()
            except Exception as e:
                config.get_logger("app.config").warning(
                    "清除 LightRAG 实例缓存失败",
                    extra={
                        "event": "config.clear_lightrag_failed",
                        "scene": scene,
                        "error_message": str(e),
                    },
                )
    
    def get_all_configs(self) -> Dict:
        """获取所有场景的配置（用于 API 返回，不包含 API Key）"""
        config_data = self._load_config()
        provider_status = self.get_provider_status()
        result = {}
        
        for scene in ["knowledge_graph", "chat", "mindmap", "embedding", "ocr"]:
            scene_config = config_data.get(scene, {})
            result[scene] = {
                "binding": scene_config.get("binding", "siliconflow"),
                "model": scene_config.get("model", ""),
                "host": scene_config.get("host", "https://api.siliconflow.cn/v1"),
                "has_api_key": provider_status.get(scene_config.get("binding", "siliconflow"), {}).get("has_api_key", False),
                # 不返回 API Key（安全考虑）
            }
        
        return result
    
    def reload_all_configs(self):
        """重新加载所有配置到全局 settings（启动时调用）"""
        for scene in ["knowledge_graph", "chat", "mindmap", "embedding"]:
            self._apply_to_global_config(scene)

    async def startup_refresh_models(self):
        """应用启动时尝试刷新一次远程模型列表。"""
        if not self.get_provider_api_key("siliconflow"):
            return
        try:
            await self.refresh_provider_models("siliconflow")
        except Exception:
            # 启动不能因为模型列表刷新失败而中断。
            return


# 全局配置服务实例
config_service = ConfigService()
