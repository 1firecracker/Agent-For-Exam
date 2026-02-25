from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.config import settings
from app.api import conversations, documents, graph, images, mindmap_routes, subjects, cheatsheet
from app.api import settings as settings_api
from app.api import subject_documents
from app.api import exams
from app.services.config_service import config_service

app = FastAPI(
    title="Agent for Exam",
    description="基于 LightRAG 的 Web 应用程序",
    version="1.0.0"
)

# 配置日志
import logging
import sys

# 强制配置基础日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True  # 强制覆盖 Uvicorn 的默认配置
)

# 确保 app 命名空间的日志级别为 INFO
logging.getLogger("app").setLevel(logging.INFO)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # 使用明确配置的端口列表
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # 暴露所有响应头，包括图片相关的
)

# 挂载静态文件服务（用于访问上传的图片）
data_dir = Path(settings.data_dir)
if data_dir.exists():
    app.mount("/uploads", StaticFiles(directory=str(data_dir)), name="uploads")
    # 🆕 添加 /data 路由，方便前端访问图片
    app.mount("/data", StaticFiles(directory=str(data_dir)), name="data")

# 注册路由
app.include_router(conversations.router)
app.include_router(subjects.router)
app.include_router(documents.router)
app.include_router(subject_documents.router)
app.include_router(graph.router)
app.include_router(images.router)
app.include_router(mindmap_routes.router)
app.include_router(settings_api.router)
app.include_router(exams.router)
app.include_router(cheatsheet.router)

# 启动时加载配置
@app.on_event("startup")
async def startup_event():
    """启动时加载配置"""
    config_service.reload_all_configs()

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Agent for Exam API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}
