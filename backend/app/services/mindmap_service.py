"""思维脑图服务，处理文档的思维脑图生成和合并"""
import asyncio
import json
import re
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional
import aiohttp

import app.config as config
from app.utils.document_parser import DocumentParser
from app.services.conversation_service import ConversationService


class MindMapService:
    """思维脑图服务"""
    
    def __init__(self):
        self.document_parser = DocumentParser()
        self.mindmap_dir = Path(config.settings.data_dir) / "mindmaps"
        self.mindmap_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_mindmap_file(self, conversation_id: str) -> Path:
        """获取思维脑图文件路径"""
        return self.mindmap_dir / f"{conversation_id}.md"
    
    def reset_mindmap(self, conversation_id: str):
        """清空指定对话的思维脑图文件内容（用于重新生成时重置）"""
        mindmap_file = self._get_mindmap_file(conversation_id)
        if mindmap_file.exists():
            mindmap_file.write_text("", encoding="utf-8")
            print(f"[🧹 思维脑图已清空] {mindmap_file}")
    
    def _load_existing_mindmap(self, conversation_id: str) -> Optional[str]:
        """加载已有的思维脑图"""
        mindmap_file = self._get_mindmap_file(conversation_id)
        if mindmap_file.exists():
            try:
                return mindmap_file.read_text(encoding="utf-8")
            except Exception as e:
                print(f"[⚠️ 加载已有脑图失败] {e}")
        return None
    
    def _save_mindmap(self, conversation_id: str, mindmap_content: str):
        """保存思维脑图到文件（追加模式：如果文件已存在，则在末尾追加新内容）"""
        mindmap_file = self._get_mindmap_file(conversation_id)

        # 读取已有脑图（如果存在）
        if mindmap_file.exists():
            old_content = mindmap_file.read_text(encoding="utf-8")
            old_content = old_content.rstrip()
            new_content = mindmap_content.lstrip()
            if old_content:
                combined_content = old_content + "\n\n" + new_content
            else:
                combined_content = new_content
        else:
            combined_content = mindmap_content

        mindmap_file.write_text(combined_content, encoding="utf-8")
        print(f"[✅ 思维脑图已保存] {mindmap_file}")

    def _extract_last_document_block(self, full_mindmap: str) -> Optional[str]:
        """从完整脑图内容中提取最后一个文档块（最后一个以 ## 开头的部分）"""
        if not full_mindmap:
            return None

        lines = full_mindmap.splitlines()
        last_index = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("## "):
                last_index = i

        if last_index == -1:
            return None

        block = "\n".join(lines[last_index:]).strip()
        return block if block else None

    def _build_mindmap_prompt(
        self,
        text: str,
        conversation_title: str,
        document_filename: str,
        existing_mindmap: Optional[str] = None,
        sample_mindmap: Optional[str] = None
    ) -> str:
        """构建思维脑图生成的 Prompt
        
        Args:
            text: 文档文本内容
            conversation_title: 对话标题（课程名）
            document_filename: 文档文件名
        """
        # 检测是否包含多个文档（通过 === 文档: 标记）
        import re
        document_markers = re.findall(r'=== 文档: ([^=]+) ===', text)
        has_multiple_documents = len(document_markers) > 1
        
        # 根节点：统一使用课程名，多个文档时根节点保持一致
        root_node = conversation_title
        
        # 构建一级节点说明
        if has_multiple_documents:
            # 多个文档：为每个文档创建独立的一级节点
            document_names_list = "\n".join([f"   - `## {Path(name).stem}`" for name in document_markers])
            level1_instruction = f"""2. 一级节点：用 `##` 标记，对应文档名（**重要：文档内容中包含多个文档，必须为每个文档创建独立的一级节点**）
   - 检测到的文档列表：
{document_names_list}
   - 每个文档必须创建独立的一级节点 `## {Path(document_filename).stem}`（使用文档标记中的文件名）
   - 在每个一级节点下，创建5个二级节点（文件基础信息、核心主题与主旨、内容逻辑拆解、关键要点/规则/约束、补充说明）
   - 如果已有思维脑图，且某个文档名已存在，则在对应文档节点下合并内容
   - 如果某个文档名不存在，则创建新的文档节点"""
        else:
            # 单个文档：使用原有逻辑
            level1_instruction = f"""2. 一级节点：用 `##` 标记，对应文档名（如果已有其他文档，则为新文档创建独立的一级节点）
   - 格式：`## {Path(document_filename).stem}`
   - 如果已有思维脑图，且该文档名已存在，则在对应文档节点下合并内容
   - 如果该文档名不存在，则创建新的文档节点"""
        
        base_prompt = f"""你是一名专业的思维导图生成专家。请根据以下文档内容，生成符合 MindMap 格式的思维导图。

一、核心结构框架（按文档组织，每个文档独立）

1. 根节点：{root_node}
   - 根节点无需标记，工具导入后自动识别为脑图总标题

{level1_instruction}

3. 二级节点：用 `###` 标记，共5个固定大类，不可增减，顺序固定（每个文档下都有这5个二级节点）：

   ### 1. 文件基础信息

   ### 2. 核心主题与主旨

   ### 3. 内容逻辑拆解

   ### 4. 关键要点/规则/约束

   ### 5. 补充说明（参考资料/工具/备注等）

4. 三级节点：用 `-` 标记，对应文件内细分维度（如章节、模块、题型、章节标题等），数量根据文件内容灵活增减

5. 四级节点：用 `  -` （缩进+短横线）标记，对应具体内容（如小题、知识点、条款、数据项等）

6. 五级节点（如需）：用 `    -` （缩进+短横线）标记，仅用于拆分复杂四级节点（如知识点下的子知识点、小题下的具体要求）

二、内容表述格式规范

1. 节点命名：
   - 一级/二级节点：简洁明确，不超过15字，用"名词+名词"或"名词+动词"结构（如"文件基础信息""S&P500 数据爬取"）
   - 三级/四级节点：精炼无冗余，用关键词或短句（不超过20字），避免完整句子

2. 关键信息标注：
   - 量化信息（分值、日期、数量等）：紧跟节点后，用括号标注（如"a) 预测类别（5分）""发布日期（2022-05）"）
   - 核心约束/规则：用【】标注关键词（如"【闭卷】""【需用户代理】"）
   - 重要数据/结论：用 **加粗** 标记（如"**调整后收盘价**""**基尼指数最优分裂**"）

3. 逻辑顺序：
   - 二级/三级节点需贴合文件原有结构（如课件按章节顺序、试题按题号顺序、报告按段落逻辑）
   - 同类节点按"重要性"或"先后顺序"排列，重要内容靠前

三、特殊格式规则

1. 符号使用：
   - 仅允许使用 `##` `###` `-` `  -` 标记层级，禁止其他符号（如*、>、[]等）
   - 括号仅用于标注量化信息/备注，禁止嵌套括号（如"（日期（2022））"错误）

2. 换行与缩进：
   - 每个节点单独一行，不可多行合并
   - 四级节点需在三级节点后缩进1个制表符（或2个空格），确保层级清晰

3. 工具兼容性：
   - 整体用 ```mindmap 和 ``` 包裹（首尾各一行，无多余字符）
   - 禁止使用特殊字符（如emoji、公式、链接），如需链接，仅保留核心网址（如"参考：python.org"）

请严格按照以上格式生成思维导图，只输出 MindMap 格式内容，不要添加任何解释或其他文字。"""
        
        # 首次生成模式（不合并已有脑图）
        # 如果有示例脑图（上一份文档），作为参考结构提供给模型，只用于模仿格式，不参与内容合并
        sample_section = ""
        if sample_mindmap:
            doc_title = Path(document_filename).stem
            sample_section = (
                "\n\n【示例】下面是上一份文档的思维导图，仅用于“格式和层级结构”的参考，禁止修改或重复输出其中内容：\n\n"
                + sample_mindmap
                + "\n\n【你的任务】：\n"
                "1. 仔细模仿上面示例的层级结构和风格。\n"
                f"2. 仅根据“当前文档内容”生成新的思维导图块，从下面这个标题开始：`## {doc_title}`\n"
                "3. 只输出新的这一块内容：\n"
                f"   - 第一行必须是：`## {doc_title}`\n"
                "   - 后续结构参照示例文档\n"
                "   - 不要输出示例中的任何内容\n"
                "   - 不要输出用于包裹整体的 ```mindmap 代码块\n"
            )

        if has_multiple_documents:
            # 多个文档：添加明确的识别说明
            multi_doc_instruction = f"""

【重要】文档内容中包含 {len(document_markers)} 个文档，每个文档用 `=== 文档: 文件名 ===` 标记分隔。
请为每个文档创建独立的一级节点，并在每个一级节点下创建5个二级节点。

文档列表：
"""
            for i, doc_name in enumerate(document_markers, 1):
                multi_doc_instruction += f"{i}. {doc_name}\n"
            multi_doc_instruction += "\n文档内容：\n"
            return base_prompt + sample_section + multi_doc_instruction + text
        else:
            # 单个文档：使用原有格式
            return base_prompt + sample_section + f"\n\n文档内容：\n{text}"
    
    async def generate_mindmap_stream(
        self,
        conversation_id: str,
        document_text: str,
        conversation_title: str,
        document_filename: str,
        document_id: Optional[str] = None,
        merge_existing: bool = True
    ) -> AsyncGenerator[str, None]:
        """流式生成思维脑图
        
        Args:
            conversation_id: 对话ID
            document_text: 文档文本内容
            conversation_title: 对话标题（课程名）
            document_filename: 文档文件名
            document_id: 文档ID（用于日志）
            merge_existing: 已废弃，不再使用。现在采用文件级追加模式，LLM只处理当前文档。
            
        Yields:
            str: 流式输出的 MindMap 内容片段
        """
        # 方案A：LLM只处理当前文档，不再合并已有脑图
        # 已有脑图通过文件级追加保存（_save_mindmap）实现合并
        print(f"📝 [思维脑图] 生成当前文档的思维脑图: {document_filename}")

        # 从已有脑图中提取上一份文档的脑图作为示例（仅用于模仿格式，不参与内容合并）
        existing_full = self._load_existing_mindmap(conversation_id)
        sample_mindmap = None
        if existing_full:
            sample_mindmap = self._extract_last_document_block(existing_full)

        # 构建 Prompt（传入示例脑图，只生成当前文档的脑图块，从 `## 当前文档名` 开始）
        prompt = self._build_mindmap_prompt(
            document_text,
            conversation_title,
            document_filename,
            existing_mindmap=None,
            sample_mindmap=sample_mindmap
        )
        
        # 调用 LLM API（流式）
        api_url = f"{config.settings.llm_binding_host}/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.settings.llm_binding_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": config.settings.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一名专业的思维导图生成专家，严格按照用户要求的格式生成 MindMap 格式的思维导图。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "stream": True,
            "temperature": 0.3,  # 降低温度，提高格式一致性
            "max_tokens": 4000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=config.settings.timeout)) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"LLM API 错误: {response.status}, {error_text}")
                    
                    accumulated_content = ""
                    async for line in response.content:
                        if not line:
                            continue
                        
                        line_text = line.decode('utf-8')
                        for chunk in line_text.split('\n'):
                            if not chunk.strip() or chunk.startswith(':'):
                                continue
                            
                            if chunk.startswith('data: '):
                                chunk = chunk[6:]  # 移除 'data: ' 前缀
                            
                            if chunk.strip() == '[DONE]':
                                # 流式输出结束，保存完整脑图
                                if accumulated_content:
                                    # 提取 mindmap 代码块内容
                                    mindmap_content = self._extract_mindmap_content(accumulated_content)
                                    if mindmap_content:
                                        self._save_mindmap(conversation_id, mindmap_content)
                                return
                            
                            try:
                                data = json.loads(chunk)
                                if 'choices' in data and len(data['choices']) > 0:
                                    delta = data['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    if content:
                                        accumulated_content += content
                                        # 实时流式输出，不等待保存
                                        yield content
                            except json.JSONDecodeError:
                                continue
                            
                            # 注意：不在流式过程中保存，只在流式结束时保存完整内容
                            # 这样可以确保前端能够实时接收和渲染内容
        except Exception as e:
            print(f"[❌ 思维脑图生成失败] {e}")
            raise
    
    def _extract_mindmap_content(self, text: str) -> Optional[str]:
        """从文本中提取 mindmap 代码块内容"""
        # 匹配 ```mindmap ... ``` 代码块
        pattern = r'```mindmap\s*\n(.*?)\n```'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # 如果没有代码块标记，尝试提取整个内容（可能是直接输出的 mindmap）
        # 检查是否包含 ## 标记（一级节点）
        if '##' in text:
            # 找到第一个 ## 之前的内容作为根节点标题
            lines = text.split('\n')
            mindmap_lines = []
            found_first_header = False
            
            for line in lines:
                if line.strip().startswith('##'):
                    found_first_header = True
                if found_first_header or line.strip():
                    mindmap_lines.append(line)
            
            if mindmap_lines:
                return '\n'.join(mindmap_lines).strip()
        
        return None
    
    async def get_mindmap(self, conversation_id: str) -> Optional[str]:
        """获取对话的思维脑图"""
        return self._load_existing_mindmap(conversation_id)
    
    async def delete_mindmap(self, conversation_id: str) -> bool:
        """删除对话的思维脑图"""
        mindmap_file = self._get_mindmap_file(conversation_id)
        if mindmap_file.exists():
            try:
                mindmap_file.unlink()
                return True
            except Exception as e:
                print(f"[⚠️ 删除思维脑图失败] {e}")
        return False

