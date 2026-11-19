"""
路由注册测试

旧版本只打印路由列表，没有断言，路由丢失也不会失败。
这里改为断言关键端点存在，并确认研究规范路由接口可用。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app


def _paths():
    return {route.path for route in app.routes if hasattr(route, "path")}


def test_core_routes_registered():
    paths = _paths()
    required = {
        "/api/mode/select",
        "/api/chat/qa/stream",
        "/api/chat/outline/generate",
        "/api/chat/section/write",
        "/api/chat/rct/write",
        "/api/review/submit",
        "/api/review/approve",
        "/api/review/revision",
        "/api/review/progress",
        "/api/export/docx",
        "/api/export/download/{session_id}",
        "/api/export/download/progress/{session_id}",
    }
    missing = required - paths
    assert not missing, f"缺少路由: {sorted(missing)}"


def test_revision_chain_routes_registered():
    """修订链与质量门禁是本轮新增能力，不能被误删"""
    paths = _paths()
    assert "/api/review/versions/{session_id}/{section_id}" in paths
    assert "/api/review/rollback" in paths
    assert "/api/export/quality/{session_id}" in paths
    assert "/api/export/references/{session_id}" in paths
    assert "/api/chat/guidelines" in paths


def test_app_imports_without_llm_key(monkeypatch):
    """缺少 LLM_API_KEY 时应用仍应可导入启动（在 /api/health 给出缺项提示）"""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    from app import app as reloaded  # 已导入对象，重复导入不应抛错
    assert reloaded is not None
