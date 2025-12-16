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
from typing import Dict, Optional
from cryptography.fernet import Fernet
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
            
            self._config_cache = {
                "knowledge_graph": {
                    "binding": config.settings.kg_llm_binding or default_binding,
                    "model": config.settings.kg_llm_model or config.settings.llm_model or "",
                    "host": config.settings.kg_llm_binding_host or config.settings.llm_binding_host or default_host,
                    "api_key_encrypted": kg_api_key_encrypted or (_encrypt_api_key(config.settings.llm_binding_api_key) if config.settings.llm_binding_api_key else "")
                },
                "chat": {
                    "binding": config.settings.chat_llm_binding or default_binding,
                    "model": config.settings.chat_llm_model or config.settings.llm_model or "",
                    "host": config.settings.chat_llm_binding_host or config.settings.llm_binding_host or default_host,
                    "api_key_encrypted": chat_api_key_encrypted or (_encrypt_api_key(config.settings.llm_binding_api_key) if config.settings.llm_binding_api_key else "")
                },
                "mindmap": {
                    "binding": config.settings.mindmap_llm_binding or default_binding,
                    "model": config.settings.mindmap_llm_model or config.settings.llm_model or "",
                    "host": config.settings.mindmap_llm_binding_host or config.settings.llm_binding_host or default_host,
                    "api_key_encrypted": mindmap_api_key_encrypted or (_encrypt_api_key(config.settings.llm_binding_api_key) if config.settings.llm_binding_api_key else "")
                },
                "embedding": {
                    "binding": config.settings.embedding_binding or "siliconflow",
                    "model": config.settings.embedding_model or "Qwen/Qwen3-Embedding-0.6B",
                    "host": config.settings.embedding_binding_host or config.settings.llm_binding_host or default_host,
                    "api_key_encrypted": embedding_api_key_encrypted
                }
            }
            self._save_config()
        
        return self._config_cache
    
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
        
        # 如果提供了 API Key，则加密存储
        if api_key is not None:
            if api_key.strip():
                config_data[scene]["api_key_encrypted"] = _encrypt_api_key(api_key)
            else:
                # 如果传入空字符串，保留原有密钥（不更新）
                pass
        
        # 更新缓存并保存
        self._config_cache = config_data
        self._save_config()
        
        # 立即更新全局配置（立即生效）
        self._apply_to_global_config(scene)
    
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
        result = {}
        
        for scene in ["knowledge_graph", "chat", "mindmap", "embedding"]:
            scene_config = config_data.get(scene, {})
            result[scene] = {
                "binding": scene_config.get("binding", "siliconflow"),
                "model": scene_config.get("model", ""),
                "host": scene_config.get("host", "https://api.siliconflow.cn/v1"),
                # 不返回 API Key（安全考虑）
            }
        
        return result
    
    def reload_all_configs(self):
        """重新加载所有配置到全局 settings（启动时调用）"""
        for scene in ["knowledge_graph", "chat", "mindmap", "embedding"]:
            self._apply_to_global_config(scene)


# 全局配置服务实例
config_service = ConfigService()

