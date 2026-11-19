"""
pytest 公共夹具

设计依据：MedPaperWriter 设计审查 3.1 / 阶段0 节
    旧测试是"打印 + 手动看"的脚本，路径还停留在 routers/、services/document_generator.py
    等已不存在的结构上，既不会失败也不会报警。这里统一成可断言、可重复的 pytest：

    - 每个测试用独立的临时会话目录，不污染仓库 data/sessions
    - 用 FakeLLM 替代真实模型，测试的是流程与校验，不消耗 API
"""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# LLMClient 在构造时要求 API Key，测试用占位值即可（不会真正发请求）
os.environ.setdefault("LLM_API_KEY", "test-key")


class FakeLLM:
    """可编排返回内容的假 LLM"""

    response: str = "这是用于测试的章节正文。" * 12
    calls: list = []

    def __init__(self, *args, **kwargs):
        from types import SimpleNamespace
        self.token_usage = SimpleNamespace(total_tokens=100)
        FakeLLM.calls.append(kwargs)

    def generate(self, prompt="", system_prompt="", temperature=None, max_tokens=None, use_cache=True):
        FakeLLM.last_system_prompt = system_prompt
        FakeLLM.last_prompt = prompt
        return FakeLLM.response, {"prompt_tokens": 50, "completion_tokens": 50, "total_tokens": 100}

    def chat(self, *args, **kwargs):  # 兼容 QA 流式接口
        raise NotImplementedError

    @classmethod
    def set_response(cls, text: str):
        """路由每次都会新建实例，因此返回内容必须设在类上"""
        cls.response = text


@pytest.fixture
def fake_llm(monkeypatch):
    """把写作服务与路由里的 LLMClient 都替换为 FakeLLM"""
    FakeLLM.response = "这是用于测试的章节正文，包含可核验的数字 120 例与 95% 置信区间。" * 4
    FakeLLM.calls = []

    import services.writing as writing
    import api.routes_chat as routes_chat

    monkeypatch.setattr(writing, "LLMClient", FakeLLM)
    monkeypatch.setattr(routes_chat, "LLMClient", FakeLLM)
    return FakeLLM


@pytest.fixture
def env(tmp_path, monkeypatch):
    """独立会话目录 + 独立导出目录的 TestClient"""
    from fastapi.testclient import TestClient

    from services.session_manager import ConversationManager
    import app as app_module
    import api.routes_chat as routes_chat
    import api.routes_mode as routes_mode
    import api.routes_review as routes_review
    import api.routes_export as routes_export

    manager = ConversationManager(tmp_path / "sessions")
    for module in (app_module, routes_chat, routes_mode, routes_review, routes_export):
        monkeypatch.setattr(module, "manager", manager)

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(routes_export, "OUTPUT_DIR", output_dir)

    # 测试会在一分钟内发几十个请求，放开限流避免 429 干扰断言
    monkeypatch.setattr(app_module.rate_limiter, "max_requests", 10000)
    app_module.rate_limiter.requests.clear()

    client = TestClient(app_module.app)
    return {"client": client, "manager": manager, "output_dir": output_dir}


def make_outline(session, titles):
    """在会话上挂一棵最小提纲（标题 -> 节点），返回 {标题: 节点}"""
    from services.session_manager import OutlineNode

    root = OutlineNode(0, "论文提纲")
    session.outline = root
    nodes = {}
    for level, title in titles:
        node = OutlineNode(level, title, root if level == 1 else nodes.get("__last_l1__", root))
        nodes[title] = node
        if level == 1:
            nodes["__last_l1__"] = node
    return nodes
