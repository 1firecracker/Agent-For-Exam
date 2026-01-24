"""
pytest 全局配置和 fixtures
"""
import pytest
from pathlib import Path


@pytest.fixture
def tmp_skill_dir(tmp_path: Path) -> Path:
    """创建临时技能目录"""
    skill_dir = tmp_path / ".agent" / "skills"
    skill_dir.mkdir(parents=True)
    return skill_dir


@pytest.fixture
def sample_skill_content() -> str:
    """示例 SKILL.md 内容"""
    return '''---
name: test_skill
description: 这是一个测试技能
---

# 测试技能

## 用途
用于测试 SkillManager 的功能。

## 示例
```python
test_skill({})
```
'''


@pytest.fixture
def create_skill(tmp_skill_dir: Path, sample_skill_content: str):
    """工厂 fixture，用于创建测试技能"""
    def _create(name: str, content: str = None) -> Path:
        skill_folder = tmp_skill_dir / name
        skill_folder.mkdir(parents=True, exist_ok=True)
        skill_md = skill_folder / "SKILL.md"
        skill_md.write_text(content or sample_skill_content, encoding="utf-8")
        return skill_folder
    
    return _create
