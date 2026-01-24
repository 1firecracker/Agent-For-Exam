"""
技能管理器模块

本模块提供了 Agent Skills 的加载、解析和管理功能，支持：
- 扫描 .agent/skills 目录发现技能
- 解析 SKILL.md 的 YAML Frontmatter（仅 name 和 description）
- 按需加载完整技能说明（渐进式披露）

主要类：
    SkillMetadata: 技能元数据模型
    SkillManager: 技能管理器，负责技能的发现和加载

使用示例：
    ```python
    manager = SkillManager()
    
    # Phase 1: Discovery - 获取所有技能的元数据
    skills = manager.discover_skills()
    # {'generate_mindmap': SkillMetadata(name='...', description='...')}
    
    # Phase 2: Activation - 加载指定技能的完整说明
    content = manager.load_skill_instructions('generate_mindmap')
    # 返回完整的 SKILL.md 内容
    ```
"""
from pathlib import Path
from typing import Dict, Optional
import re

from pydantic import BaseModel, Field, field_validator

from app.config import get_logger

logger = get_logger("app.services.skill_manager")

# ============================================================================
# 官方 Agent Skills 规范常量
# 参考: https://agentskills.io, Anthropic Claude Skills Specification
# ============================================================================

# 默认技能目录（相对于 backend 根目录）
DEFAULT_SKILL_DIR = Path(__file__).parent.parent.parent.parent / ".agent" / "skills"

# name 字段限制
MAX_NAME_LENGTH = 64
NAME_PATTERN = re.compile(r"^[a-z0-9_-]+$")  # 只允许小写字母、数字、下划线、连字符

# description 字段限制
MAX_DESCRIPTION_LENGTH = 1024

# 禁止使用的保留词
RESERVED_WORDS = {"anthropic", "claude", "openai", "gpt", "gemini"}


class SkillMetadata(BaseModel):
    """技能元数据模型
    
    符合官方 Agent Skills 规范:
    - name: 最大 64 字符，只能包含小写字母、数字、下划线、连字符
    - description: 最大 1024 字符
    
    这是渐进式披露的第一层，用于 Agent 判断技能是否相关。
    """
    name: str = Field(..., description="技能唯一标识符，对应工具名称")
    description: str = Field(..., description="技能描述，用于 Agent 判断是否相关")
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证 name 字段符合官方规范"""
        if not v:
            raise ValueError("name 不能为空")
        
        if len(v) > MAX_NAME_LENGTH:
            raise ValueError(f"name 长度不能超过 {MAX_NAME_LENGTH} 字符，当前长度: {len(v)}")
        
        if not NAME_PATTERN.match(v):
            raise ValueError(
                f"name 只能包含小写字母、数字、下划线和连字符，当前值: {v}"
            )
        
        # 检查保留词（警告但不阻止）
        if v.lower() in RESERVED_WORDS:
            logger.warning(f"技能名称使用了保留词: {v}")
        
        return v
    
    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        """验证 description 字段符合官方规范"""
        if not v:
            raise ValueError("description 不能为空")
        
        if len(v) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(
                f"description 长度不能超过 {MAX_DESCRIPTION_LENGTH} 字符，当前长度: {len(v)}"
            )
        
        return v
    
    class Config:
        extra = "ignore"  # 忽略其他字段


class SkillParseError(Exception):
    """技能解析错误"""
    def __init__(self, skill_path: Path, message: str):
        self.skill_path = skill_path
        super().__init__(f"解析技能文件失败 [{skill_path}]: {message}")


class SkillNotFoundError(Exception):
    """技能不存在错误"""
    def __init__(self, skill_name: str):
        self.skill_name = skill_name
        super().__init__(f"技能不存在: {skill_name}")


class SkillManager:
    """技能管理器
    
    负责扫描、解析和加载 Agent Skills。
    实现渐进式披露机制：
    1. discover_skills(): 仅加载元数据（name + description）
    2. load_skill_instructions(): 加载完整的技能说明
    
    Attributes:
        skill_dir: 技能目录路径
        _registry: 技能元数据缓存
        _instructions_cache: 技能说明缓存
    """
    
    def __init__(self, skill_dir: Optional[Path] = None):
        """初始化技能管理器
        
        Args:
            skill_dir: 技能目录路径，默认为 backend/.agent/skills
        """
        self.skill_dir = skill_dir or DEFAULT_SKILL_DIR
        self._registry: Dict[str, SkillMetadata] = {}
        self._instructions_cache: Dict[str, str] = {}
        
        logger.debug(
            "SkillManager 初始化",
            extra={
                "event": "skill_manager.init",
                "skill_dir": str(self.skill_dir),
            }
        )
    
    def discover_skills(self) -> Dict[str, SkillMetadata]:
        """发现并加载所有技能的元数据
        
        扫描 skill_dir 目录下的所有子目录，查找并解析 SKILL.md 文件的
        YAML Frontmatter，提取 name 和 description 字段。
        
        Returns:
            技能名称到元数据的映射字典
            
        Example:
            >>> manager = SkillManager()
            >>> skills = manager.discover_skills()
            >>> print(skills.keys())
            dict_keys(['generate_mindmap', 'query_knowledge_graph', 'list_documents'])
        """
        self._registry.clear()
        
        if not self.skill_dir.exists():
            logger.warning(
                "技能目录不存在",
                extra={
                    "event": "skill_manager.dir_not_found",
                    "skill_dir": str(self.skill_dir),
                }
            )
            return {}
        
        # 遍历技能目录下的所有子目录
        for skill_folder in self.skill_dir.iterdir():
            if not skill_folder.is_dir():
                continue
            
            # 跳过隐藏目录和特殊目录
            if skill_folder.name.startswith(".") or skill_folder.name.startswith("_"):
                continue
            
            skill_md = skill_folder / "SKILL.md"
            if not skill_md.exists():
                logger.debug(
                    "技能目录缺少 SKILL.md",
                    extra={
                        "event": "skill_manager.missing_skill_md",
                        "folder": skill_folder.name,
                    }
                )
                continue
            
            try:
                metadata = self._parse_frontmatter(skill_md)
                if metadata:
                    self._registry[metadata.name] = metadata
                    logger.info(
                        "技能已发现",
                        extra={
                            "event": "skill_manager.skill_discovered",
                            "skill_name": metadata.name,
                            "description_preview": metadata.description[:50],
                        }
                    )
            except SkillParseError as e:
                logger.warning(
                    "技能解析失败",
                    extra={
                        "event": "skill_manager.parse_error",
                        "folder": skill_folder.name,
                        "error": str(e),
                    }
                )
        
        logger.info(
            "技能发现完成",
            extra={
                "event": "skill_manager.discovery_complete",
                "skill_count": len(self._registry),
                "skill_names": list(self._registry.keys()),
            }
        )
        
        return self._registry.copy()
    
    def _parse_frontmatter(self, skill_md: Path) -> Optional[SkillMetadata]:
        """解析 SKILL.md 的 YAML Frontmatter
        
        Args:
            skill_md: SKILL.md 文件路径
            
        Returns:
            解析成功返回 SkillMetadata，否则返回 None
            
        Raises:
            SkillParseError: 当文件格式无效时
        """
        try:
            content = skill_md.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            raise SkillParseError(skill_md, f"文件编码错误: {e}")
        
        # 检查是否以 YAML Frontmatter 开头
        if not content.startswith("---"):
            raise SkillParseError(skill_md, "缺少 YAML Frontmatter（文件应以 --- 开头）")
        
        # 提取 Frontmatter 内容
        parts = content.split("---", 2)
        if len(parts) < 3:
            raise SkillParseError(skill_md, "YAML Frontmatter 格式无效（缺少结束标记 ---）")
        
        frontmatter_text = parts[1].strip()
        
        # 简单解析 YAML（避免引入 PyYAML 依赖）
        # 只提取 name 和 description 字段
        name = self._extract_yaml_value(frontmatter_text, "name")
        description = self._extract_yaml_value(frontmatter_text, "description")
        
        if not name:
            raise SkillParseError(skill_md, "缺少 name 字段")
        
        if not description:
            raise SkillParseError(skill_md, "缺少 description 字段")
        
        return SkillMetadata(name=name, description=description)
    
    def _extract_yaml_value(self, yaml_text: str, key: str) -> Optional[str]:
        """从 YAML 文本中提取指定键的值
        
        使用简单的正则匹配，支持单行值。
        
        Args:
            yaml_text: YAML 文本内容
            key: 要提取的键名
            
        Returns:
            键对应的值，如果不存在返回 None
        """
        # 匹配 key: value 或 key: "value" 或 key: 'value'
        pattern = rf"^{key}:\s*['\"]?(.+?)['\"]?\s*$"
        match = re.search(pattern, yaml_text, re.MULTILINE)
        
        if match:
            return match.group(1).strip()
        
        return None
    
    def load_skill_instructions(self, skill_name: str) -> Optional[str]:
        """加载指定技能的完整说明文档
        
        这是渐进式披露的第二层，当 Agent 决定使用某个技能时，
        调用此方法加载完整的 SKILL.md 内容。
        
        Args:
            skill_name: 技能名称（对应 SKILL.md 中的 name 字段）
            
        Returns:
            技能的完整 Markdown 内容，如果技能不存在返回 None
            
        Raises:
            SkillNotFoundError: 当技能不存在时
            
        Example:
            >>> manager = SkillManager()
            >>> manager.discover_skills()
            >>> content = manager.load_skill_instructions("generate_mindmap")
            >>> print(content[:100])
            '---\\nname: generate_mindmap\\ndescription: ...'
        """
        # 检查缓存
        if skill_name in self._instructions_cache:
            logger.debug(
                "从缓存加载技能说明",
                extra={
                    "event": "skill_manager.cache_hit",
                    "skill_name": skill_name,
                }
            )
            return self._instructions_cache[skill_name]
        
        # 查找技能目录
        skill_folder = self._find_skill_folder(skill_name)
        if not skill_folder:
            logger.warning(
                "技能未找到",
                extra={
                    "event": "skill_manager.skill_not_found",
                    "skill_name": skill_name,
                }
            )
            return None
        
        skill_md = skill_folder / "SKILL.md"
        if not skill_md.exists():
            return None
        
        try:
            content = skill_md.read_text(encoding="utf-8")
            self._instructions_cache[skill_name] = content
            
            logger.info(
                "技能说明已加载",
                extra={
                    "event": "skill_manager.instructions_loaded",
                    "skill_name": skill_name,
                    "content_length": len(content),
                }
            )
            
            return content
        except UnicodeDecodeError as e:
            logger.error(
                "加载技能说明失败",
                extra={
                    "event": "skill_manager.load_error",
                    "skill_name": skill_name,
                    "error": str(e),
                }
            )
            return None
    
    def _find_skill_folder(self, skill_name: str) -> Optional[Path]:
        """查找技能对应的目录
        
        首先检查 registry，然后遍历目录查找匹配的技能。
        
        Args:
            skill_name: 技能名称
            
        Returns:
            技能目录路径，如果不存在返回 None
        """
        # 如果 registry 为空，先执行发现
        if not self._registry:
            self.discover_skills()
        
        # 检查技能是否存在于 registry
        if skill_name not in self._registry:
            return None
        
        # 遍历目录查找
        for skill_folder in self.skill_dir.iterdir():
            if not skill_folder.is_dir():
                continue
            
            skill_md = skill_folder / "SKILL.md"
            if skill_md.exists():
                try:
                    metadata = self._parse_frontmatter(skill_md)
                    if metadata and metadata.name == skill_name:
                        return skill_folder
                except SkillParseError:
                    continue
        
        return None
    
    def get_skill_metadata(self, skill_name: str) -> Optional[SkillMetadata]:
        """获取指定技能的元数据
        
        Args:
            skill_name: 技能名称
            
        Returns:
            技能元数据，如果不存在返回 None
        """
        if not self._registry:
            self.discover_skills()
        
        return self._registry.get(skill_name)
    
    def get_system_prompt_snippet(self) -> str:
        """生成 System Prompt 中的技能列表片段
        
        用于在 System Prompt 中列出所有可用技能的简要描述，
        让 Agent 知道有哪些技能可用。
        
        Returns:
            格式化的技能列表字符串
            
        Example:
            >>> manager = SkillManager()
            >>> manager.discover_skills()
            >>> print(manager.get_system_prompt_snippet())
            Available Skills:
            - generate_mindmap: 根据对话中的文档内容生成思维导图
            - query_knowledge_graph: 在对话的知识图谱中查询信息
            - list_documents: 列出当前对话中的所有文档
        """
        if not self._registry:
            self.discover_skills()
        
        if not self._registry:
            return "No skills available."
        
        lines = ["Available Skills:"]
        for skill_name, metadata in sorted(self._registry.items()):
            lines.append(f"- {skill_name}: {metadata.description}")
        
        return "\n".join(lines)
    
    def clear_cache(self) -> None:
        """清空所有缓存
        
        清空元数据 registry 和 instructions 缓存。
        下次调用 discover_skills() 或 load_skill_instructions() 时会重新加载。
        """
        self._registry.clear()
        self._instructions_cache.clear()
        
        logger.debug(
            "缓存已清空",
            extra={"event": "skill_manager.cache_cleared"}
        )
