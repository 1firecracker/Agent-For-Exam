"""试题解析工具 - 提取文本和图片，题目识别由AI agent处理"""
from typing import Dict, Any, Optional, List
from pathlib import Path
import pdfplumber
import base64
import hashlib
from io import BytesIO
import json
import logging

import app.config as config
from app.services.paddle_ocr_client import get_gitee_client

logger = logging.getLogger(__name__)
try:
    import fitz  # PyMuPDF
    # 验证fitz是否真的可用
    _test_doc = fitz.open()  # 创建一个空文档测试
    _test_doc.close()
    PYMUPDF_AVAILABLE = True
except (ImportError, Exception) as e:
    # 记录导入失败的原因
    logger.warning(f"PyMuPDF不可用: {e}")
    PYMUPDF_AVAILABLE = False


class ExerciseParser:
    """试题解析器 - 提取文本和图片，供AI agent处理"""
    
    def __init__(self):
        self.remote_client = get_gitee_client()

    def extract_content(
        self,
        file_path: str,
        save_to: Optional[str] = None,
        conversation_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """提取文件内容（文本和图片），供AI agent处理
        
        Args:
            file_path: 文件路径
            
        Returns:
            {
                "text": "完整文本内容",
                "images": [
                    {
                        "page_number": 1,
                        "image_base64": "base64编码的图片",
                        "image_format": "png"
                    }
                ],
                "file_type": "pdf|docx|txt"
            }
        """
        path = Path(file_path)
        suffix = path.suffix.lower()
        
        remote_allowed = (
            suffix == '.pdf'
            and config.settings.enable_gitee_ocr
            and conversation_id
            and document_id
            and getattr(self.remote_client, "enabled", False)
        )

        if remote_allowed:
            try:
                content = self.remote_client.parse_pdf(file_path, conversation_id, document_id)
            except Exception as exc:
                logger.warning(
                    "Gitee PaddleOCR-VL 调用失败，回退到本地解析。 (%s)",
                    exc,
                    exc_info=True,
                )
                content = self._extract_pdf_content(file_path)
        else:
            if suffix == '.pdf':
                content = self._extract_pdf_content(file_path)
            elif suffix == '.docx':
                content = self._extract_docx_content(file_path)
            elif suffix == '.txt' or suffix == '':
                content = self._extract_txt_content(file_path)
            else:
                raise ValueError(f"不支持的文件类型: {suffix}，支持 .pdf, .docx, .txt")
            
        # 如果需要保存，保存到指定目录
        if save_to:
            self._save_content(content, save_to, path.stem)
        
        return content
    
    def _save_content(self, content: Dict[str, Any], save_dir: str, file_id: str):
        """保存提取的内容到文件系统
        
        Args:
            content: 提取的内容
            save_dir: 保存目录
            file_id: 文件ID（用于命名）
        """
        save_path = Path(save_dir) / file_id
        save_path.mkdir(parents=True, exist_ok=True)
        
        # 保存文本
        text_file = save_path / "text.txt"
        text_file.write_text(content["text"], encoding='utf-8')
        
        # 保存图片
        images_dir = save_path / "images"
        images_dir.mkdir(exist_ok=True)
        
        saved_images = []
        for img in content["images"]:
            # 解码base64并保存为PNG
            img_data = base64.b64decode(img["image_base64"])
            # 使用更精确的文件名：page_X_img_Y.png
            img_index = img.get("image_index", 1)
            img_file = images_dir / f"page_{img['page_number']}_img_{img_index}.png"
            img_file.write_bytes(img_data)
            
            saved_images.append({
                "page_number": img["page_number"],
                "image_index": img_index,
                "file_path": str(img_file.relative_to(save_path)),
                "image_format": img["image_format"],
                "width": img.get("width"),
                "height": img.get("height")
            })
        
        # 保存元数据
        metadata = {
            "file_id": file_id,
            "file_type": content["file_type"],
            "text_file": "text.txt",
            "images": saved_images,
            "text_length": len(content["text"]),
            "image_count": len(content["images"])
        }
        
        metadata_file = save_path / "metadata.json"
        metadata_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    
    def _extract_pdf_content(self, file_path: str) -> Dict[str, Any]:
        """提取PDF文本和嵌入的图片（只提取真正的图片对象，不提取整页截图）"""
        # 重新检查PyMuPDF是否可用（可能在运行时环境不同）
        try:
            import fitz
            pymupdf_available = True
        except ImportError:
            pymupdf_available = False
        
        print(f"[DEBUG] 开始提取PDF内容: {file_path}")
        print(f"[DEBUG] 模块级 PYMUPDF_AVAILABLE={PYMUPDF_AVAILABLE}, 运行时检查={pymupdf_available}")
        
        if pymupdf_available:
            result = self._extract_with_pymupdf(file_path)
            print(f"[DEBUG] PyMuPDF提取完成，返回图片数量: {len(result.get('images', []))}")
            return result
        else:
            print(f"[DEBUG] PyMuPDF不可用，使用pdfplumber")
            return self._extract_with_pdfplumber(file_path)
    
    def _extract_with_pymupdf(self, file_path: str) -> Dict[str, Any]:
        """使用PyMuPDF提取文本和图片，根据图片实际位置在文本中标注"""
        texts = []
        images = []
        
        try:
            doc = fitz.open(file_path)
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text_blocks = page.get_text("dict")
                page_text = page.get_text()
                image_list = page.get_images(full=True)
                
                # 提取图片并获取位置
                page_images = []
                image_markers = []
                
                for img_idx, img_info in enumerate(image_list):
                    try:
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        
                        img_ext = base_image.get("ext", "png")
                        if img_ext.lower() == "jpeg":
                            img_ext = "jpg"
                        
                        image_base64 = base64.b64encode(base_image["image"]).decode('utf-8')
                        img_name = f"page_{page_num + 1}_img_{img_idx + 1}.{img_ext}"
                        
                        page_images.append({
                            "page_number": page_num + 1,
                            "image_index": img_idx + 1,
                            "image_base64": image_base64,
                            "image_format": img_ext,
                            "width": base_image.get("width", 0),
                            "height": base_image.get("height", 0)
                        })
                        
                        # 获取图片位置（用于文本标记）
                        img_y_pos = None
                        try:
                            image_rects = page.get_image_rects(xref)
                            if image_rects:
                                img_y_pos = image_rects[0].y0
                        except Exception:
                            for block in text_blocks.get("blocks", []):
                                if block.get("type") == 1:
                                    bbox = block.get("bbox", [])
                                    if bbox:
                                        img_y_pos = bbox[1]
                                        break
                        
                        image_markers.append({
                            "name": img_name,
                            "y_pos": img_y_pos if img_y_pos is not None else float('inf'),
                            "index": img_idx
                        })
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"提取图片失败 (page {page_num + 1}, img {img_idx + 1}): {e}", exc_info=True)
                        continue
                
                image_markers.sort(key=lambda x: x["y_pos"])
                if page_text.strip() and image_markers:
                    annotated_text = self._insert_markers_by_position(
                        page_text, text_blocks, image_markers
                    )
                    texts.append(annotated_text)
                elif page_text.strip():
                    texts.append(page_text.strip())
                
                images.extend(page_images)
            
            doc.close()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"PyMuPDF提取失败，回退到pdfplumber: {e}", exc_info=True)
            return self._extract_with_pdfplumber(file_path)
        
        return {
            "text": "\n\n".join(texts),
            "images": images,
            "file_type": "pdf"
        }
    
    def _insert_markers_by_position(self, text: str, text_blocks: Dict, image_markers: List[Dict]) -> str:
        """根据图片和文本的实际位置，在文本中插入图片标记"""
        if not image_markers:
            return text.strip()
        
        # 获取文本块的位置信息
        text_lines = text.split('\n')
        lines_with_pos = []  # 存储每行文本及其Y坐标
        
        for block in text_blocks.get("blocks", []):
            if block.get("type") == 0:  # 文本块
                bbox = block.get("bbox", [])
                if bbox:
                    block_y = bbox[1]  # 文本块的Y坐标
                    block_text = block.get("lines", [])
                    for line in block_text:
                        line_text = "".join([span.get("text", "") for span in line.get("spans", [])])
                        if line_text.strip():
                            lines_with_pos.append({
                                "text": line_text,
                                "y": block_y
                            })
        
        # 如果没有位置信息，使用简单方法
        if not lines_with_pos:
            markers = " ".join([f"[IMAGE: {img['name']}]" for img in image_markers])
            return text.strip() + f"\n{markers}"
        
        # 根据图片Y坐标，在最近的文本行后插入标记
        result_lines = []
        marker_idx = 0
        
        for line_info in lines_with_pos:
            result_lines.append(line_info["text"])
            
            # 检查是否有图片应该插入在这一行之后
            while marker_idx < len(image_markers):
                marker = image_markers[marker_idx]
                # 如果图片Y坐标在当前行附近（允许一定误差），插入标记
                if marker["y_pos"] <= line_info["y"] + 50:  # 50点的容差
                    result_lines.append(f"[IMAGE: {marker['name']}]")
                    marker_idx += 1
                else:
                    break
        
        # 剩余的图片标记添加到末尾
        while marker_idx < len(image_markers):
            result_lines.append(f"[IMAGE: {image_markers[marker_idx]['name']}]")
            marker_idx += 1
        
        return "\n".join(result_lines) if result_lines else text.strip()
    
    def _extract_with_pdfplumber(self, file_path: str) -> Dict[str, Any]:
        """使用pdfplumber提取（备选方案）"""
        texts = []
        images = []
        
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text and text.strip():
                    texts.append(text.strip())
        
        return {
            "text": "\n\n".join(texts),
            "images": images,
            "file_type": "pdf"
        }
    
    def _extract_docx_content(self, file_path: str) -> Dict[str, Any]:
        """提取DOCX文本和图片，根据图片在段落中的实际位置标注"""
        try:
            from docx import Document
            import zipfile
            
            # 完全基于XML解析，确保索引一致性
            texts = []
            images = []
            xml_para_to_text_idx = {}  # XML段落索引 -> texts列表索引
            
            # 从DOCX文件中提取图片（直接解析XML结构）
            try:
                with zipfile.ZipFile(file_path, 'r') as docx_zip:
                    from xml.etree import ElementTree as ET
                    
                    # 读取关系文件
                    rels_xml = docx_zip.read('word/_rels/document.xml.rels')
                    rels_root = ET.fromstring(rels_xml)
                    r_id_to_image = {}
                    
                    for rel in rels_root.findall('.//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
                        r_id = rel.get('Id')
                        target = rel.get('Target')
                        if target and 'media' in target:
                            # 统一路径格式
                            image_path = target.replace('../', 'word/')
                            r_id_to_image[r_id] = image_path
                    
                    # 读取document.xml，解析文档结构
                    doc_xml = docx_zip.read('word/document.xml')
                    doc_root = ET.fromstring(doc_xml)
                    
                    # 提取所有图片文件（按文件名排序，确保顺序一致）
                    image_files = sorted([f for f in docx_zip.namelist() if f.startswith('word/media/') and 
                                  any(f.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp'])])
                    
                    # 建立图片文件到索引的映射（基于r_id_to_image的顺序）
                    image_file_to_idx = {}
                    # 先按r_id顺序建立映射
                    for idx, (r_id, image_path) in enumerate(sorted(r_id_to_image.items()), 1):
                        image_file_to_idx[image_path] = idx
                    
                    # 对于不在r_id_to_image中的图片文件，继续编号
                    current_idx = len(r_id_to_image) + 1
                    for img_path in image_files:
                        if img_path not in image_file_to_idx:
                            image_file_to_idx[img_path] = current_idx
                            current_idx += 1
                    
                    # 解析document.xml，按文档顺序找到每个图片及其所在段落
                    # 使用body下的所有元素（段落、表格等）
                    body = doc_root.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}body')
                    if body is None:
                        body = doc_root
                    
                    # 按顺序遍历body下的直接子元素（段落）
                    # 注意：使用body的直接子元素，而不是所有后代元素
                    para_image_map_xml = {}  # para_idx -> [r_id列表]
                    
                    # 获取body的直接子元素中的段落，同时提取文本
                    body_children = list(body)
                    para_count = 0
                    text_idx = 0
                    
                    # 定义命名空间
                    ns = {
                        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
                        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
                        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
                        'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
                        'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture'
                    }
                    
                    for elem in body_children:
                        # 只处理段落元素
                        if elem.tag.endswith('}p'):
                            # 按段落中元素的顺序提取（包括文本和图片）
                            para_text_parts = []
                            para_r_ids = []
                            
                            # 获取段落的所有直接子元素（按顺序）
                            para_children = list(elem)
                            
                            for child in para_children:
                                # 处理run元素（包含文本或图片）
                                if child.tag.endswith('}r'):
                                    # 先检查run中是否有图片（VML格式：v:imagedata）
                                    has_image = False
                                    
                                    # 方法1: 检查VML格式的图片（v:imagedata）
                                    imagedata_elems = child.findall('.//{urn:schemas-microsoft-com:vml}imagedata')
                                    for imagedata in imagedata_elems:
                                        r_embed = imagedata.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                                        if r_embed and r_embed in r_id_to_image:
                                            para_text_parts.append(f"[IMAGE_PLACEHOLDER:{r_embed}]")
                                            para_r_ids.append(r_embed)
                                            has_image = True
                                    
                                    # 方法2: 检查drawing格式的图片（a:blip）
                                    if not has_image:
                                        drawings = child.findall('.//w:drawing', ns)
                                        for drawing in drawings:
                                            blip = drawing.find('.//a:blip', ns)
                                            if blip is not None:
                                                r_embed = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                                                if r_embed and r_embed in r_id_to_image:
                                                    para_text_parts.append(f"[IMAGE_PLACEHOLDER:{r_embed}]")
                                                    para_r_ids.append(r_embed)
                                                    has_image = True
                                    
                                    # 提取run中的文本
                                    t_elems = child.findall('.//w:t', ns)
                                    for t_elem in t_elems:
                                        if t_elem.text:
                                            para_text_parts.append(t_elem.text)
                                
                                # 处理其他可能包含文本的元素（如hyperlink等）
                                elif child.tag.endswith('}hyperlink'):
                                    t_elems = child.findall('.//w:t', ns)
                                    for t_elem in t_elems:
                                        if t_elem.text:
                                            para_text_parts.append(t_elem.text)
                            
                            para_text = ''.join(para_text_parts).strip()
                            
                            # 如果段落有文本或图片，添加到texts列表
                            if para_text or para_r_ids:
                                if para_text:
                                    texts.append(para_text)
                                else:
                                    # 如果只有图片没有文本，创建一个空文本占位
                                    texts.append('')
                                xml_para_to_text_idx[para_count] = text_idx
                                text_idx += 1
                            else:
                                xml_para_to_text_idx[para_count] = -1
                            
                            # 记录段落中的图片引用（如果还没有记录）
                            if para_r_ids and para_count not in para_image_map_xml:
                                para_image_map_xml[para_count] = para_r_ids
                            
                            para_count += 1
                    
                    # 提取图片并建立映射
                    extracted_images = {}  # para_idx -> [img_name列表]
                    r_id_to_img_name = {}  # r_id -> img_name
                    
                    # 按照文档中图片出现的顺序来提取和编号
                    # 通过遍历文本中的占位符来确定图片出现顺序
                    r_id_order = []  # 按文档顺序存储r_id（首次出现）
                    seen_r_ids = set()
                    
                    # 遍历所有段落，按照段落顺序和段落内顺序收集r_id
                    for para_idx in sorted(para_image_map_xml.keys()):
                        for r_id in para_image_map_xml[para_idx]:
                            if r_id not in seen_r_ids:
                                r_id_order.append(r_id)
                                seen_r_ids.add(r_id)
                    
                    # 对于不在段落中的图片，按r_id顺序添加
                    for r_id in sorted(r_id_to_image.keys()):
                        if r_id not in seen_r_ids:
                            r_id_order.append(r_id)
                            seen_r_ids.add(r_id)
                    
                    # 按照文档中的出现顺序提取图片
                    for r_id in r_id_order:
                        if r_id not in r_id_to_image:
                            continue
                        image_path = r_id_to_image[r_id]
                        # 尝试读取图片（支持多种路径格式）
                        img_data = None
                        actual_path = None
                        
                        # 尝试不同的路径格式
                        path_variants = [
                            image_path,
                            image_path.replace('word/', ''),
                            f"word/{image_path}",
                            image_path.replace('../', 'word/'),
                            f"word/media/{Path(image_path).name}"
                        ]
                        
                        for path_variant in path_variants:
                            try:
                                if path_variant in docx_zip.namelist():
                                    img_data = docx_zip.read(path_variant)
                                    actual_path = path_variant
                                    break
                            except Exception:
                                continue
                        
                        if img_data:
                            image_base64 = base64.b64encode(img_data).decode('utf-8')
                            img_hash = hashlib.md5(image_base64.encode()).hexdigest()
                            
                            # 检查是否已经提取过（通过hash）
                            already_extracted = False
                            for existing_img in images:
                                existing_hash = hashlib.md5(existing_img['image_base64'].encode()).hexdigest()
                                if existing_hash == img_hash:
                                    # 如果已提取，使用已存在的图片名称
                                    r_id_to_img_name[r_id] = f"img_{existing_img['image_index']}.{existing_img['image_format']}"
                                    already_extracted = True
                                    break
                            
                            if not already_extracted:
                                # 确定图片索引（按提取顺序连续编号）
                                img_idx = len(images) + 1
                                img_ext = Path(actual_path).suffix.lower().lstrip('.') or "png"
                                img_name = f"img_{img_idx}.{img_ext}"
                                
                                r_id_to_img_name[r_id] = img_name
                                
                                images.append({
                                    "page_number": 1,
                                    "image_index": img_idx,
                                    "image_base64": image_base64,
                                    "image_format": img_ext,
                                    "width": 0,
                                    "height": 0
                                })
                    
                    # 建立段落到图片的映射
                    for para_idx, r_ids in para_image_map_xml.items():
                        for r_id in r_ids:
                            if r_id in r_id_to_img_name:
                                if para_idx not in extracted_images:
                                    extracted_images[para_idx] = []
                                extracted_images[para_idx].append(r_id_to_img_name[r_id])
                    
                    # 在对应段落中替换图片占位符为实际标记
                    for xml_para_idx, img_names in extracted_images.items():
                        text_idx = xml_para_to_text_idx.get(xml_para_idx, -1)
                        if text_idx >= 0 and text_idx < len(texts):
                            # 获取段落对应的r_ids
                            r_ids = para_image_map_xml.get(xml_para_idx, [])
                            
                            # 替换占位符
                            text = texts[text_idx]
                            for r_id in r_ids:
                                if r_id in r_id_to_img_name:
                                    img_name = r_id_to_img_name[r_id]
                                    placeholder = f"[IMAGE_PLACEHOLDER:{r_id}]"
                                    text = text.replace(placeholder, f"[IMAGE: {img_name}]")
                            
                            texts[text_idx] = text
                            
                            # 如果还有未替换的图片（可能不在占位符中），添加到段落末尾
                            remaining_in_para = [name for name in img_names if f"[IMAGE: {name}]" not in texts[text_idx]]
                            if remaining_in_para:
                                markers = " ".join([f"[IMAGE: {name}]" for name in remaining_in_para])
                                texts[text_idx] = texts[text_idx] + f"\n{markers}"
                    
                    # 对所有段落进行全局替换（处理可能遗漏的占位符）
                    # 使用正则表达式替换所有占位符
                    import re
                    for text_idx in range(len(texts)):
                        text = texts[text_idx]
                        # 使用正则表达式匹配并替换所有占位符
                        for r_id, img_name in r_id_to_img_name.items():
                            pattern = re.escape(f"[IMAGE_PLACEHOLDER:{r_id}]")
                            text = re.sub(pattern, f"[IMAGE: {img_name}]", text)
                        texts[text_idx] = text
                    
                    # 记录已提取的图片路径（避免重复提取）
                    extracted_paths = set()
                    for img in images:
                        # 通过base64 hash来识别已提取的图片
                        extracted_paths.add(hashlib.md5(img['image_base64'].encode()).hexdigest())
                    
                    # 处理未关联到段落的图片（只处理真正未提取的图片）
                    remaining_images = []
                    for img_path in image_files:
                        # 检查这个路径是否已经在r_id_to_image中处理过
                        already_extracted = False
                        for r_id, mapped_path in r_id_to_image.items():
                            # 检查路径是否匹配（支持多种格式）
                            path_variants = [
                                mapped_path,
                                mapped_path.replace('word/', ''),
                                f"word/{mapped_path}",
                                mapped_path.replace('../', 'word/'),
                                f"word/media/{Path(mapped_path).name}"
                            ]
                            if img_path in path_variants:
                                already_extracted = True
                                break
                        
                        if not already_extracted:
                            try:
                                img_data = docx_zip.read(img_path)
                                img_base64 = base64.b64encode(img_data).decode('utf-8')
                                img_hash = hashlib.md5(img_base64.encode()).hexdigest()
                                
                                # 检查是否已经通过hash提取过（避免重复）
                                if img_hash not in extracted_paths:
                                    img_ext = Path(img_path).suffix.lower().lstrip('.') or "png"
                                    # 使用新的索引（从已提取的最大索引+1开始）
                                    max_idx = max([img['image_index'] for img in images], default=0)
                                    img_idx = max_idx + 1
                                    img_name = f"img_{img_idx}.{img_ext}"
                                    remaining_images.append(img_name)
                                    
                                    images.append({
                                        "page_number": 1,
                                        "image_index": img_idx,
                                        "image_base64": img_base64,
                                        "image_format": img_ext,
                                        "width": 0,
                                        "height": 0
                                    })
                                    extracted_paths.add(img_hash)
                            except Exception:
                                continue
                    
                    if remaining_images:
                        markers = " ".join([f"[IMAGE: {name}]" for name in remaining_images])
                        if texts:
                            texts[-1] = texts[-1] + f"\n{markers}"
                        else:
                            texts.append(markers)
            except Exception as e:
                import traceback
                traceback.print_exc()
                pass
            
            return {
                "text": "\n".join(texts),
                "images": images,
                "file_type": "docx"
            }
        except ImportError:
            raise ImportError("需要安装 python-docx: pip install python-docx")
    
    def _extract_txt_content(self, file_path: str) -> Dict[str, Any]:
        """提取TXT文本"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='gbk') as f:
                text = f.read()
        
        return {
            "text": text,
            "images": [],
            "file_type": "txt"
        }
