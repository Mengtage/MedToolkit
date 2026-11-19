"""
核心数据模型与持久化测试

覆盖设计审查阶段0的验收标准：
    - 重启后能恢复稿件（正文、修订意见、版本历史、参考资料）
    - 提纲重新解析不会丢正文（id 与内容按标题继承）
"""

import json

from services.session_manager import (
    ConversationManager,
    OutlineNode,
    SectionStatus,
    Session,
    SessionMode,
)


def test_session_roundtrip_preserves_manuscript(tmp_path):
    """会话保存 → 重新加载，正文/版本/修订意见/参考资料都还在"""
    manager = ConversationManager(tmp_path / "sessions")
    session_id = manager.create_session(SessionMode.REVIEW)
    session = manager.get_session(session_id)

    session.research_question = "他汀类药物对老年 ACS 患者的影响"
    session.study_type = "系统评价"
    session.guideline_id = "prisma_2020"
    session.reference_materials.append({
        "filename": "protocol.txt", "content": "样本量 240 例", "upload_time": "2026-01-01",
    })

    root = OutlineNode(0, "论文提纲")
    session.outline = root
    node = OutlineNode(3, "3.1 检索策略", root)
    node.content_zh = "初稿正文"
    node.snapshot(source="generate")
    node.apply_revision("修订后的正文", feedback="补充检索日期")
    node.status = SectionStatus.APPROVED
    manager.save(session_id)

    reloaded = ConversationManager(tmp_path / "sessions").get_session(session_id)
    restored = reloaded.get_outline_node(node.id)

    assert restored is not None
    assert restored.content_zh == "修订后的正文"
    assert restored.current_version == 2
    assert restored.revisions[0]["feedback"] == "补充检索日期"
    assert restored.status == SectionStatus.APPROVED
    assert reloaded.reference_materials[0]["filename"] == "protocol.txt"
    assert reloaded.guideline_id == "prisma_2020"


def test_session_file_is_valid_json(tmp_path):
    """会话文件必须是可解析 JSON（原子写入不能留下半截文件）"""
    manager = ConversationManager(tmp_path / "sessions")
    session_id = manager.create_session(SessionMode.RCT)
    manager.get_session(session_id).sections.append(
        {"chapter": "Methods", "content_zh": "x", "status": "approved"}
    )
    manager.save(session_id)

    path = tmp_path / "sessions" / f"{session_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["sections"][0]["chapter"] == "Methods"


def test_restore_version_keeps_trace():
    """回滚到旧版本时，当前稿先留痕，避免修订链断裂"""
    node = OutlineNode(2, "讨论")
    node.content_zh = "v1 内容"
    node.snapshot(source="generate")
    node.content_zh = "v2 内容"
    node.snapshot(source="generate")

    assert node.restore_version(1)
    assert node.content_zh == "v1 内容"
    # 回滚前的 v2 仍然留在历史里
    assert any(v["content_zh"] == "v2 内容" for v in node.versions)


def test_old_session_format_still_loads():
    """旧格式（无 feedback/versions 字段）的会话文件必须能加载"""
    legacy = {
        "session_id": "legacy-1",
        "mode": "review",
        "outline": {
            "id": "root", "level": 0, "title": "论文提纲", "status": "pending",
            "content_zh": "", "content_en": "",
            "children": [{
                "id": "n1", "level": 1, "title": "引言", "status": "approved",
                "content_zh": "旧稿正文", "content_en": "", "children": [],
            }],
        },
        "reference_materials": [],
    }
    session = Session.from_dict(legacy)
    node = session.get_outline_node("n1")
    assert node is not None and node.content_zh == "旧稿正文"
    assert node.versions == [] and node.revisions == []
    assert node.status == SectionStatus.APPROVED


def test_outline_merge_preserves_ids_and_content():
    """重新解析提纲（改标题不改章节）不得丢正文，前端持有的 id 也不能变"""
    from api.routes_chat import merge_outline_state, parse_outline

    old = parse_outline("1. 引言\n2. 方法\n2.1 研究对象")
    method = old.children[1]
    method.content_zh = "方法正文"
    method.status = SectionStatus.APPROVED
    method_id = method.id

    new = merge_outline_state(parse_outline("1. 引言\n2. 方法\n2.1 研究对象\n3. 结果"), old)
    merged = new.children[1]

    assert merged.id == method_id
    assert merged.content_zh == "方法正文"
    assert merged.status == SectionStatus.APPROVED
    assert new.children[2].title == "结果"


def test_approved_sections_excludes_empty_and_self():
    """已批准上下文只包含有正文的章节，且排除当前章节"""
    session = Session(SessionMode.REVIEW)
    root = OutlineNode(0, "论文提纲")
    session.outline = root
    a = OutlineNode(1, "引言", root)
    b = OutlineNode(1, "方法", root)
    a.content_zh = "引言正文"
    a.status = SectionStatus.APPROVED
    b.content_zh = "方法正文"
    b.status = SectionStatus.APPROVED

    titles = [n.title for n in session.approved_sections(exclude_id=b.id)]
    assert titles == ["引言"]
