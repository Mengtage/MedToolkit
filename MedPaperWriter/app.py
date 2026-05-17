"""
FastAPI应用入口
MedToolkit - 医学论文自动化写作系统
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
from pathlib import Path

from routers import mode, chat, review, export
from services.session_manager import manager

app = FastAPI(
    title="MedToolkit - 医学论文自动化写作系统",
    description="支持综述模式和RCT模式的医学论文自动生成工具",
    version="1.0.0"
)

# 获取项目根目录
BASE_DIR = Path(__file__).parent

# 挂载静态文件
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# 配置模板
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

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
async def get_session(session_id: str):
    """获取会话状态"""
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
async def get_active_session():
    """获取当前活跃会话"""
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
async def terminate_session(session_id: str):
    """终止会话"""
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
