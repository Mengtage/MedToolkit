"""
FastAPI应用入口
MedToolkit - 医学论文自动化写作系统
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os
from pathlib import Path
import secrets
import re
import time

from routers import mode, chat, review, export
from services.session_manager import manager

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000,http://localhost:8001").split(",")
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

_request_counts: dict[str, list[float]] = {}

app = FastAPI(
    title="MedToolkit - 医学论文自动化写作系统",
    description="支持综述模式和RCT模式的医学论文自动生成工具",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit."""
    current_time = time.time()
    if client_ip not in _request_counts:
        _request_counts[client_ip] = []
    _request_counts[client_ip] = [
        t for t in _request_counts[client_ip]
        if current_time - t < RATE_LIMIT_WINDOW
    ]
    if len(_request_counts[client_ip]) >= RATE_LIMIT_REQUESTS:
        return False
    _request_counts[client_ip].append(current_time)
    return True


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, considering proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks."""
    filename = re.sub(r'[^\w\s\-\.]', '', filename)
    filename = re.sub(r'\.\.', '', filename)
    return filename[:255]

# 注册路由
app.include_router(mode.router, prefix="/api/mode", tags=["模式选择"])
app.include_router(chat.router, prefix="/api/chat", tags=["对话交互"])
app.include_router(review.router, prefix="/api/review", tags=["审核流程"])
app.include_router(export.router, prefix="/api/export", tags=["文档导出"])


@app.get("/", response_class=HTMLResponse)
async def home():
    """主界面"""
    return FileResponse(str(BASE_DIR / "templates" / "index.html"))


@app.get("/app")
async def app_page():
    """返回主应用页面"""
    return FileResponse(str(BASE_DIR / "templates" / "index.html"))


@app.get("/review")
async def review_page():
    """返回审核页面"""
    return FileResponse(str(BASE_DIR / "templates" / "review.html"))


@app.get("/export")
async def export_page():
    """返回导出页面"""
    return FileResponse(str(BASE_DIR / "templates" / "export.html"))


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "MedToolkit"}


@app.get("/api/session/{session_id}")
async def get_session(request: Request, session_id: str):
    """获取会话状态"""
    client_ip = _get_client_ip(request)
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")

    session = manager.get_session(session_id)
    if session:
        return JSONResponse({
            "success": True,
            "data": session.to_dict()
        })
    return JSONResponse({
        "success": False,
        "message": "会话不存在"
    }, status_code=404)


@app.get("/api/session/active")
async def get_active_session(request: Request):
    """获取当前活跃会话"""
    client_ip = _get_client_ip(request)
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")

    session = manager.get_active_session()
    if session:
        return JSONResponse({
            "success": True,
            "data": session.to_dict()
        })
    return JSONResponse({
        "success": False,
        "message": "无活跃会话"
    })


@app.post("/api/session/terminate/{session_id}")
async def terminate_session(request: Request, session_id: str):
    """终止会话"""
    client_ip = _get_client_ip(request)
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")

    session = manager.get_session(session_id)
    if session:
        manager.complete_session(session_id)
        return JSONResponse({
            "success": True,
            "message": "会话已终止"
        })
    return JSONResponse({
        "success": False,
        "message": "会话不存在"
    }, status_code=404)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
