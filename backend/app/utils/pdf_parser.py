"""PDF 文档解析器"""
import logging
# 关闭 pdfminer 的警告信息
logging.getLogger('pdfminer.pdfinterp').setLevel(logging.ERROR)
logging.getLogger('pdfminer').setLevel(logging.ERROR)

import pdfplumber
from typing import List, Dict, Any
from pathlib import Path


class PDFParser:
    """PDF 文档解析器"""
    
    def parse(self, file_path: str) -> Dict[str, Any]:
        """解析 PDF 文件，返回结构化数据
        
        Args:
            file_path: PDF 文件路径
            
        Returns:
            包含页面信息的字典
        """
        pages_data = []
        
        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)
            
            for page_num, page in enumerate(pdf.pages, 1):
                page_data = {
                    "page_number": page_num,
                    "text_content": self._extract_text(page),
                    "tables": self._extract_tables(page, page_num),
                    "images": self._extract_images(page, page_num),
                    "structure": self._extract_structure(page),
                }
                pages_data.append(page_data)
            
            # 尝试提取目录/大纲
            outline = self._extract_outline(pdf)
        
        return {
            "filename": Path(file_path).name,
            "total_pages": total_pages,
            "outline": outline,
            "pages": pages_data
        }
    
    def extract_text(self, file_path: str, file_id: str = None) -> str:
        """提取 PDF 的纯文本内容
        
        Args:
            file_path: PDF 文件路径
            file_id: 文档ID（可选，用于嵌入元数据标记）
            
        Returns:
            所有页面文本内容（用换行符分隔，每页前添加 [FILE:{file_id}][PAGE:N] 标记）
        """
        texts = []
        
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text and text.strip():
                    # 构建元数据标记
                    if file_id:
                        texts.append(f"[FILE:{file_id}][PAGE:{page_num}]\n{text.strip()}")
                    else:
                        texts.append(f"[PAGE:{page_num}]\n{text.strip()}")
        
        return "\n\n".join(texts)
    
    def extract_pages(self, file_path: str, file_id: str = None) -> List[Dict[str, Any]]:
        """提取 PDF 的页面内容（页级三元库）
        
        Args:
            file_path: PDF 文件路径
            file_id: 文档ID
            
        Returns:
            页面列表，每个元素包含 page_index 和 content
        """
        pages = []
        
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text and text.strip():
                    pages.append({
                        "page_index": page_num,
                        "content": text.strip()
                    })
        
        return pages
    
    def _extract_text(self, page) -> str:
        """提取页面文本"""
        text = page.extract_text()
        return text.strip() if text else ""
    
    def _extract_tables(self, page, page_number: int) -> List[Dict[str, Any]]:
        """提取页面中的表格
        
        Args:
            page: PDF 页面对象
            page_number: 页面编号
            
        Returns:
            表格数据列表
        """
        tables = []
        extracted_tables = page.extract_tables()
        
        for idx, table in enumerate(extracted_tables):
            if table:
                table_data = {
                    "table_id": f"page_{page_number}_table_{idx}",
                    "rows": len(table),
                    "cols": len(table[0]) if table else 0,
                    "data": table
                }
                tables.append(table_data)
        
        return tables
    
    def _extract_images(self, page, page_number: int) -> List[Dict[str, Any]]:
        """提取页面中的图片元信息
        
        Args:
            page: PDF 页面对象
            page_number: 页面编号
            
        Returns:
            图片信息列表
        """
        images = []
        
        # pdfplumber 可以提取图片信息
        if hasattr(page, 'images') and page.images:
            for idx, img in enumerate(page.images):
                image_info = {
                    "image_id": f"page_{page_number}_img_{idx}",
                    "position": {
                        "x0": img.get("x0", 0),
                        "y0": img.get("y0", 0),
                        "x1": img.get("x1", 0),
                        "y1": img.get("y1", 0),
                        "width": img.get("width", 0),
                        "height": img.get("height", 0),
                    },
                    "name": img.get("name", f"Image {idx + 1}")
                }
                images.append(image_info)
        
        return images
    
    def _extract_structure(self, page) -> Dict[str, Any]:
        """提取页面结构信息"""
        return {
            "width": float(page.width),
            "height": float(page.height),
            "rotation": page.rotation if hasattr(page, "rotation") else 0
        }
    
    def _extract_outline(self, pdf) -> List[Dict[str, Any]]:
        """提取 PDF 目录/大纲结构
        
        Args:
            pdf: PDF 文档对象
            
        Returns:
            目录结构列表
        """
        outline = []
        
        # pdfplumber 可能不支持目录提取，使用简单方法
        # 尝试从前几页提取可能的标题
        try:
            for page_num, page in enumerate(pdf.pages[:5], 1):  # 只检查前5页
                text = page.extract_text()
                if text:
                    # 查找可能是标题的行（通常较短且格式特殊）
                    lines = text.split('\n')[:10]  # 前10行
                    for line in lines:
                        line = line.strip()
                        if line and len(line) < 100 and not line.startswith(' '):
                            outline.append({
                                "title": line,
                                "page": page_num
                            })
                            break
        except:
            pass
        
        return outline

