"""
写作 → 审核 → 修订 → 导出 全流程集成测试

这些用例对应设计审查阶段0的四条验收标准：
    1. 重启后能恢复稿件
    2. 每条修订意见都产生可追踪的新版本
    3. 导出文件不含未声明的占位摘要或虚构引用
    4. 写作/审核状态可持久化
"""

import json

from docx import Document

OUTLINE = """1. 摘要
2. 引言
2.1 研究背景
3. 方法
3.1 研究对象
4. 结果
4.1 主要结局
5. 讨论
6. 参考文献"""

ANALYSIS = "共纳入 120 例受试者，主要结局组间差异 3.2（95% 置信区间 1.1 至 5.3，P<0.001）。"


def _client(env):
    return env["client"]


def _new_session(env, mode="review", topic="他汀类药物对老年 ACS 患者预后的影响"):
    response = _client(env).post("/api/mode/select", data={"mode": mode, "research_topic": topic})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _outline(env, session_id, text=OUTLINE):
    response = _client(env).post("/api/chat/outline/modify",
                                 data={"session_id": session_id, "outline_text": text})
    assert response.status_code == 200, response.text
    return response.json()["outline"]


def _find(node, title):
    if node.get("title") == title:
        return node
    for child in node.get("children", []):
        found = _find(child, title)
        if found:
            return found
    return None


def test_write_section_returns_version_and_quality(env, fake_llm):
    """写作返回清洗后的正文、版本号与校验结果，并立即落盘"""
    session_id = _new_session(env)
    outline = _outline(env, session_id)
    section = _find(outline, "主要结局")

    session = env["manager"].get_session(session_id)
    session.analysis_text = ANALYSIS

    response = _client(env).post("/api/chat/section/write", data={
        "session_id": session_id, "section_id": section["id"], "language": "中文",
    })
    data = response.json()
    assert data["success"], data
    assert data["version"] == 1
    assert "120" in data["content"]
    assert "**" not in data["content"]          # Markdown 标记已清洗
    assert data["section_kind"] == "results"
    assert isinstance(data["quality"], list)

    stored = env["manager"].get_session(session_id).get_outline_node(section["id"])
    assert stored.content_zh == data["content"]
    assert stored.status.value == "pending_review"
    assert (env["manager"].data_dir / f"{session_id}.json").exists()


def test_revision_creates_new_version_with_diff(env, fake_llm):
    """修订：旧稿留痕 → 新版本 → 差异可查看"""
    session_id = _new_session(env)
    outline = _outline(env, session_id)
    section = _find(outline, "讨论")
    env["manager"].get_session(session_id).analysis_text = ANALYSIS

    first = _client(env).post("/api/chat/section/write", data={
        "session_id": session_id, "section_id": section["id"], "language": "中文",
    }).json()
    assert first["success"] and first["version"] == 1

    # 换一份内容，确保 diff 有实际变化
    fake_llm.set_response(fake_llm.response + "补充：本研究存在单中心、样本量有限的局限。")

    revised = _client(env).post("/api/review/revision", data={
        "session_id": session_id, "section_id": section["id"], "feedback": "补充局限性说明",
    }).json()

    assert revised["success"], revised
    assert revised["regenerated"] is True
    assert revised["version"] == 2
    assert revised["diff"]["has_changes"] is True
    assert revised["status"] == "pending_review"

    node = env["manager"].get_session(session_id).get_outline_node(section["id"])
    assert node.current_version == 2
    assert node.content_zh == revised["content"]
    assert node.revisions[-1]["feedback"] == "补充局限性说明"

    history = _client(env).get(f"/api/review/versions/{session_id}/{section['id']}").json()
    assert history["current_version"] == 2
    assert len(history["versions"]) == 2


def test_revision_requires_existing_content(env, fake_llm):
    """没有正文时提交修订意见应被拒绝，而不是生成一个空 diff"""
    session_id = _new_session(env)
    outline = _outline(env, session_id)
    section = _find(outline, "研究背景")

    response = _client(env).post("/api/review/revision", data={
        "session_id": session_id, "section_id": section["id"], "feedback": "改一下",
    })
    assert response.status_code == 400
    assert "尚无正文" in response.json()["message"]


def test_review_progress_counts_written_sections(env, fake_llm):
    """审核状态与进度必须真实反映（旧实现用 str(枚举) 比较，永远为 0）"""
    session_id = _new_session(env)
    outline = _outline(env, session_id)
    section = _find(outline, "研究对象")

    _client(env).post("/api/chat/section/write", data={
        "session_id": session_id, "section_id": section["id"], "language": "中文",
    })

    pending = _client(env).get(f"/api/review/pending?session_id={session_id}").json()
    assert pending["pending_count"] == 1
    assert pending["sections"][0]["status"] == "pending_review"

    approved = _client(env).post("/api/review/approve", data={
        "session_id": session_id, "section_id": section["id"],
    }).json()
    assert approved["success"] and approved["status"] == "approved"

    progress = _client(env).get(f"/api/review/progress?session_id={session_id}").json()
    assert progress["total"] == 1
    assert progress["approved"] == 1
    assert progress["progress"] == 100.0

    all_sections = _client(env).get(f"/api/review/all?session_id={session_id}").json()
    assert all_sections["approved_count"] == 1


def test_export_reports_missing_abstract_and_references(env, fake_llm):
    """缺摘要、缺参考文献时必须显式告警，而不是静默输出占位/空列表"""
    session_id = _new_session(env)
    outline = _outline(env, session_id, "1. 引言\n2. 方法")
    intro = _find(outline, "引言")
    env["manager"].get_session(session_id).analysis_text = ANALYSIS

    _client(env).post("/api/chat/section/write", data={
        "session_id": session_id, "section_id": intro["id"], "language": "中文",
    })

    result = _client(env).post("/api/export/docx", data={
        "session_id": session_id, "language": "中文", "ref_style": "vancouver",
    }).json()

    assert result["success"], result
    joined = " ".join(result["warnings"])
    assert "摘要" in joined
    assert "参考文献" in joined
    assert result["references"] == 0

    doc = Document(result["file_path"])
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "待补充" in text                       # 占位是显式声明的，不是空白
    assert "[Abstract content to be generated]" not in text  # 旧的英文占位已移除


def test_export_accepts_hunter_style_reference(env, fake_llm):
    """Hunter 的 pub_date / journal_title / 作者对象可以直接导入并正确渲染年份"""
    session_id = _new_session(env)
    _outline(env, session_id, "1. 引言\n2. 方法")

    payload = [{
        "title": "Statins in elderly acute coronary syndrome",
        "authors": [{"last_name": "Zhang", "initials": "Y"}, {"last_name": "Li", "initials": "M"}],
        "journal_title": "Lancet",
        "pub_date": "2021-05-03",
        "volume": "397",
        "issue": "10288",
        "pages": "1234-1245",
        "doi": "10.1000/example",
        "pmid": "33965000",
    }]
    imported = _client(env).post(f"/api/export/references/{session_id}",
                                  data={"references": json.dumps(payload)}).json()
    assert imported["success"] and imported["added"] == 1
    assert imported["references"][0]["year"] == "2021"

    result = _client(env).post("/api/export/docx", data={
        "session_id": session_id, "language": "中文", "ref_style": "vancouver",
    }).json()
    assert result["success"]
    assert result["references"] == 1

    text = "\n".join(p.text for p in Document(result["file_path"]).paragraphs)
    assert "2021" in text
    assert "10.1000/example" in text
    assert "Zhang Y" in text
    assert "未提供参考文献条目" not in text


def test_quality_report_flags_missing_guideline_items(env, fake_llm):
    """按 PRISMA 声明后，缺注册/检索/偏倚等必报条目要能被指出"""
    session_id = _new_session(env)
    outline = _outline(env, session_id, "1. 引言\n2. 方法")
    intro = _find(outline, "引言")
    session = env["manager"].get_session(session_id)
    session.guideline_id = "prisma_2020"
    session.study_type = "系统评价"
    session.analysis_text = ANALYSIS
    env["manager"].save(session_id)

    _client(env).post("/api/chat/section/write", data={
        "session_id": session_id, "section_id": intro["id"], "language": "中文",
    })

    report = _client(env).get(f"/api/export/quality/{session_id}").json()
    assert report["success"]
    assert report["guideline"]["id"] == "prisma_2020"
    codes = [issue["code"] for issue in report["issues"]]
    assert "guideline_incomplete" in codes
    assert report["summary"]["warning"] >= 1


def test_rct_write_and_revision(env, fake_llm):
    """RCT 模式：写作 → 修订 → 版本递增，且章节状态回到待审核"""
    session_id = _new_session(env, mode="rct", topic="多中心 RCT")
    session = env["manager"].get_session(session_id)
    session.protocol_text = "随机、双盲、安慰剂对照，计划纳入 240 例。"
    session.analysis_text = ANALYSIS
    env["manager"].save(session_id)

    first = _client(env).post("/api/chat/rct/write", data={
        "session_id": session_id, "chapter": "Results", "language": "中文",
    }).json()
    assert first["success"] and first["version"] == 1

    fake_llm.set_response(fake_llm.response + "另需说明样本量的估算依据。")
    revised = _client(env).post("/api/chat/rct/revision", data={
        "session_id": session_id, "chapter": "Results", "feedback": "补一句样本量来源",
    }).json()
    assert revised["success"] and revised["regenerated"] is True
    assert revised["version"] == 2
    assert revised["diff"]["has_changes"] is True

    entry = env["manager"].get_session(session_id).rct_section("Results")
    assert entry["status"] == "pending_review"
    assert len(entry["versions"]) == 2
    assert entry["revisions"][-1]["feedback"] == "补一句样本量来源"

    approved = _client(env).post("/api/chat/rct/approve", data={
        "session_id": session_id, "chapter": "Results",
    }).json()
    assert approved["success"]
    assert env["manager"].get_session(session_id).rct_section("Results")["status"] == "approved"
