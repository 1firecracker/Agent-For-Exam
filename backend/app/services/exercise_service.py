"""样本试题服务，处理样本试题上传、解析、管理"""
import base64
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import UploadFile

import app.config as config
from app.utils.exercise_parser import ExerciseParser


class ExerciseService:
    """样本试题服务"""
    
    def __init__(self):
        self.parser = ExerciseParser()
        self.exercises_dir = Path(config.settings.exercises_dir)
        self.exercises_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_conversation_samples_dir(self, conversation_id: str) -> Path:
        """获取对话的样本试题目录"""
        return self.exercises_dir / conversation_id / "samples"
    
    def _get_sample_dir(self, conversation_id: str, sample_id: str) -> Path:
        """获取样本试题目录"""
        return self._get_conversation_samples_dir(conversation_id) / sample_id
    
    def _get_metadata_file(self, conversation_id: str, sample_id: str) -> Path:
        """获取元数据文件路径"""
        return self._get_sample_dir(conversation_id, sample_id) / "metadata.json"
    
    def _validate_file(self, filename: str) -> tuple[bool, Optional[str]]:
        """验证文件类型"""
        file_ext = Path(filename).suffix.lower().lstrip('.')
        if file_ext not in config.settings.exercise_allowed_extensions:
            return False, f"不支持的文件类型: {file_ext}，仅支持 {', '.join(config.settings.exercise_allowed_extensions)}"
        return True, None
    
    async def _check_file_size(self, file_content: bytes) -> tuple[bool, Optional[str]]:
        """检查文件大小"""
        file_size = len(file_content)
        if file_size > config.settings.max_file_size:
            return False, f"文件大小 {file_size / 1024 / 1024:.2f}MB 超过限制 {config.settings.max_file_size / 1024 / 1024}MB"
        return True, None
    
    async def upload_samples(
        self,
        conversation_id: str,
        files: List[UploadFile]
    ) -> Dict:
        """上传样本试题
        
        Args:
            conversation_id: 对话ID
            files: 文件列表
            
        Returns:
            上传结果字典
        """
        if not files:
            raise ValueError("至少需要上传一个文件")
        
        # 检查样本数量限制
        existing_samples = self.list_samples(conversation_id)
        if len(existing_samples) + len(files) > config.settings.max_samples_per_conversation:
            raise ValueError(
                f"当前已有 {len(existing_samples)} 个样本，再上传 {len(files)} 个将超过限制 "
                f"({config.settings.max_samples_per_conversation} 个)"
            )
        
        uploaded_samples = []
        samples_dir = self._get_conversation_samples_dir(conversation_id)
        samples_dir.mkdir(parents=True, exist_ok=True)
        
        for file in files:
            # 验证文件类型
            is_valid, error_msg = self._validate_file(file.filename)
            if not is_valid:
                raise ValueError(error_msg)
            
            # 读取文件内容
            file_content = await file.read()
            
            # 验证文件大小
            is_valid, error_msg = await self._check_file_size(file_content)
            if not is_valid:
                raise ValueError(error_msg)
            
            # 生成样本ID（使用文件名，去除扩展名）
            original_path = Path(file.filename)
            sample_id = original_path.stem
            
            # 如果已存在同名样本，添加后缀
            sample_dir = samples_dir / sample_id
            counter = 1
            while sample_dir.exists():
                sample_id = f"{original_path.stem}_{counter}"
                sample_dir = samples_dir / sample_id
                counter += 1
            
            # 创建样本目录
            sample_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存原始文件
            original_file_path = sample_dir / file.filename
            with open(original_file_path, 'wb') as f:
                f.write(file_content)
            
            # 创建初始元数据（状态为 pending）
            upload_time = datetime.utcnow().isoformat() + "Z"
            initial_metadata = {
                "sample_id": sample_id,
                "conversation_id": conversation_id,
                "original_filename": file.filename,
                "original_file_path": str(original_file_path.relative_to(sample_dir)),
                "file_type": Path(file.filename).suffix.lower().lstrip('.'),
                "file_size": len(file_content),
                "upload_time": upload_time,
                "status": "pending",
                "parse_start_time": None,
                "parse_end_time": None,
                "error": None
            }
            
            # 保存初始元数据
            metadata_file = self._get_metadata_file(conversation_id, sample_id)
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(initial_metadata, f, ensure_ascii=False, indent=2)
            
            uploaded_samples.append({
                "sample_id": sample_id,
                "filename": file.filename,
                "file_size": len(file_content),
                "file_type": initial_metadata["file_type"],
                "status": "pending",
                "upload_time": upload_time
            })
        
        return {
            "conversation_id": conversation_id,
            "uploaded_samples": uploaded_samples,
            "total_samples": len(uploaded_samples)
        }
    
    def _parse_sample_async(
        self,
        conversation_id: str,
        sample_id: str,
        original_file_path: Path
    ):
        """异步解析样本文件（后台任务）
        
        Args:
            conversation_id: 对话ID
            sample_id: 样本ID
            original_file_path: 原始文件路径
        """
        import logging
        logger = logging.getLogger(__name__)
        
        metadata_file = self._get_metadata_file(conversation_id, sample_id)
        sample_dir = self._get_sample_dir(conversation_id, sample_id)
        
        try:
            # 更新状态为 processing
            self._update_parse_status(
                conversation_id, sample_id,
                status="processing",
                parse_start_time=datetime.utcnow().isoformat() + "Z"
            )
            
            # 使用ExerciseParser解析文件
            content = self.parser.extract_content(
                str(original_file_path),
                save_to=None,
                conversation_id=conversation_id,
                document_id=sample_id,
            )
            
            # 直接保存文本和图片到 sample_dir
            text_file = sample_dir / "text.txt"
            text_file.write_text(content["text"], encoding='utf-8')
            
            # 保存图片
            images_dir = sample_dir / "images"
            images_dir.mkdir(exist_ok=True)
            
            saved_images = []
            for i, img in enumerate(content.get("images", [])):
                try:
                    # 情况1：有 image_base64（本地解析，如 PyMuPDF）
                    if img.get("image_base64"):
                        img_data = base64.b64decode(img["image_base64"])
                        img_index = img.get("image_index", i + 1)
                        img_format = img.get("image_format", "png")
                        page_number = img.get("page_number", 1)
                        img_file = images_dir / f"page_{page_number}_img_{img_index}.{img_format}"
                        img_file.write_bytes(img_data)
                        
                        logger.info(f"保存图片成功: {img_file.name}, 大小: {len(img_data)} 字节")
                        
                        saved_images.append({
                            "page_number": page_number,
                            "image_index": img_index,
                            "file_path": f"images/{img_file.name}",
                            "image_format": img_format,
                            "width": img.get("width", 0),
                            "height": img.get("height", 0)
                        })
                    # 情况2：只有 file_path（Gitee OCR，图片已保存）
                    elif img.get("file_path"):
                        file_path = img.get("file_path")
                        # file_path 可能是相对路径（如 "images/image_4_1.jpg"）或绝对路径
                        if file_path.startswith("images/"):
                            # 相对路径，检查文件是否存在
                            img_file = sample_dir / file_path
                            if img_file.exists():
                                logger.info(f"使用已存在的图片: {file_path}")
                                saved_images.append({
                                    "page_number": img.get("page_number"),
                                    "image_index": img.get("image_index", i + 1),
                                    "file_path": file_path,
                                    "image_format": img.get("image_format", img_file.suffix.lstrip('.')),
                                    "width": img.get("width", 0),
                                    "height": img.get("height", 0)
                                })
                            else:
                                logger.warning(f"图片文件不存在: {file_path}")
                        else:
                            # 绝对路径或其他格式，直接使用
                            logger.info(f"使用图片路径: {file_path}")
                            saved_images.append({
                                "page_number": img.get("page_number"),
                                "image_index": img.get("image_index", i + 1),
                                "file_path": file_path,
                                "image_format": img.get("image_format", "unknown"),
                                "width": img.get("width", 0),
                                "height": img.get("height", 0)
                            })
                    else:
                        logger.warning(f"图片 {i+1} 既没有 base64 数据也没有 file_path，跳过")
                        continue
                except Exception as e:
                    logger.error(f"处理图片 {i+1} 失败: {e}", exc_info=True)
                    continue
            
            # 更新元数据（解析成功）
            parse_end_time = datetime.utcnow().isoformat() + "Z"
            self._update_parse_status(
                conversation_id, sample_id,
                status="completed",
                parse_end_time=parse_end_time,
                file_type=content["file_type"],
                text_length=len(content["text"]),
                image_count=len(saved_images),
                images=saved_images
            )
            
            logger.info(f"样本解析完成: sample_id={sample_id}, image_count={len(saved_images)}")
            
        except Exception as e:
            # 更新状态为 failed
            error_msg = str(e)
            logger.error(f"样本解析失败: sample_id={sample_id}, 错误: {error_msg}", exc_info=True)
            self._update_parse_status(
                conversation_id, sample_id,
                status="failed",
                parse_end_time=datetime.utcnow().isoformat() + "Z",
                error=error_msg
            )
    
    def _update_parse_status(
        self,
        conversation_id: str,
        sample_id: str,
        status: str,
        parse_start_time: Optional[str] = None,
        parse_end_time: Optional[str] = None,
        error: Optional[str] = None,
        file_type: Optional[str] = None,
        text_length: Optional[int] = None,
        image_count: Optional[int] = None,
        images: Optional[List[Dict]] = None
    ):
        """更新解析状态
        
        Args:
            conversation_id: 对话ID
            sample_id: 样本ID
            status: 状态 (pending/processing/completed/failed)
            parse_start_time: 解析开始时间
            parse_end_time: 解析结束时间
            error: 错误信息
            file_type: 文件类型
            text_length: 文本长度
            image_count: 图片数量
            images: 图片列表
        """
        metadata_file = self._get_metadata_file(conversation_id, sample_id)
        
        if not metadata_file.exists():
            return
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            metadata["status"] = status
            if parse_start_time is not None:
                metadata["parse_start_time"] = parse_start_time
            if parse_end_time is not None:
                metadata["parse_end_time"] = parse_end_time
            if error is not None:
                metadata["error"] = error
            if file_type is not None:
                metadata["file_type"] = file_type
            if text_length is not None:
                metadata["text_length"] = text_length
                metadata["text_file"] = "text.txt"
            if image_count is not None:
                metadata["image_count"] = image_count
            if images is not None:
                metadata["images"] = images
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"更新解析状态失败: {e}", exc_info=True)
    
    def list_samples(self, conversation_id: str) -> List[Dict]:
        """获取样本试题列表
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            样本试题列表
        """
        samples_dir = self._get_conversation_samples_dir(conversation_id)
        if not samples_dir.exists():
            return []
        
        samples = []
        for sample_dir in samples_dir.iterdir():
            if not sample_dir.is_dir():
                continue
            
            metadata_file = sample_dir / "metadata.json"
            if not metadata_file.exists():
                continue
            
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    
                    # 获取图片数量：优先使用 metadata 中的值，如果为 0 则从文件系统检查
                    image_count = metadata.get("image_count", 0)
                    if image_count == 0:
                        # 检查 images 数组
                        images_list = metadata.get("images", [])
                        if images_list:
                            image_count = len(images_list)
                        else:
                            # 从文件系统检查实际图片文件数量
                            images_dir = sample_dir / "images"
                            if images_dir.exists() and images_dir.is_dir():
                                image_files = [f for f in images_dir.iterdir() if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']]
                                image_count = len(image_files)
                    
                    samples.append({
                        "sample_id": metadata.get("sample_id", sample_dir.name),
                        "filename": metadata.get("original_filename", metadata.get("filename", sample_dir.name)),
                        "file_type": metadata.get("file_type", "unknown"),
                        "file_size": metadata.get("file_size", 0),
                        "text_length": metadata.get("text_length", 0),
                        "image_count": image_count,
                        "upload_time": metadata.get("upload_time", ""),
                        "status": metadata.get("status", "unknown")
                    })
            except Exception:
                continue
        
        # 按上传时间倒序排列
        samples.sort(key=lambda x: x.get("upload_time", ""), reverse=True)
        return samples
    
    def get_sample(self, conversation_id: str, sample_id: str) -> Optional[Dict]:
        """获取样本试题详情
        
        Args:
            conversation_id: 对话ID
            sample_id: 样本ID
            
        Returns:
            样本试题详情，如果不存在返回None
        """
        metadata_file = self._get_metadata_file(conversation_id, sample_id)
        if not metadata_file.exists():
            return None
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # 确保包含必要字段（兼容旧格式）
            if "sample_id" not in metadata:
                metadata["sample_id"] = sample_id
            if "conversation_id" not in metadata:
                metadata["conversation_id"] = conversation_id
            if "filename" not in metadata:
                # 兼容旧格式：file_id 或 original_filename
                metadata["filename"] = metadata.get("original_filename", metadata.get("file_id", sample_id))
            if "original_filename" not in metadata:
                metadata["original_filename"] = metadata.get("filename", sample_id)
            
            # 确保必需字段有默认值（必须在读取文本前设置）
            metadata.setdefault("file_size", 0)
            metadata.setdefault("upload_time", "")
            metadata.setdefault("images", [])
            
            # 读取文本内容
            sample_dir = self._get_sample_dir(conversation_id, sample_id)
            text_file = sample_dir / metadata.get("text_file", "text.txt")
            text_content = ""
            
            # 如果文件不存在，尝试在子目录中查找（兼容旧的保存结构）
            if not text_file.exists():
                # 检查是否有子目录（旧格式：sample_dir/sample_id/text.txt）
                sub_dir = sample_dir / sample_id
                if sub_dir.exists() and sub_dir.is_dir():
                    alt_text_file = sub_dir / metadata.get("text_file", "text.txt")
                    if alt_text_file.exists():
                        text_file = alt_text_file
            
            if text_file.exists():
                try:
                    with open(text_file, 'r', encoding='utf-8') as f:
                        text_content = f.read()
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"读取文本文件失败: {text_file}, 错误: {e}")
                    text_content = ""
            
            metadata["text_content"] = text_content
            return metadata
        except Exception:
            return None
    
    def delete_sample(self, conversation_id: str, sample_id: str) -> bool:
        """删除样本试题
        
        Args:
            conversation_id: 对话ID
            sample_id: 样本ID
            
        Returns:
            是否删除成功
        """
        sample_dir = self._get_sample_dir(conversation_id, sample_id)
        if not sample_dir.exists():
            return False
        
        try:
            shutil.rmtree(sample_dir)
            return True
        except Exception:
            return False
    
    def get_sample_text(self, conversation_id: str, sample_id: str) -> Optional[str]:
        """获取样本试题文本内容
        
        Args:
            conversation_id: 对话ID
            sample_id: 样本ID
            
        Returns:
            文本内容，如果不存在返回None
        """
        sample = self.get_sample(conversation_id, sample_id)
        if not sample:
            return None
        return sample.get("text_content", "")

