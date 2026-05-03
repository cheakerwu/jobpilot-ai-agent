from src.parsers.jd_text import build_jd_confidence, parse_jd_text


def test_parse_jd_text_extracts_labeled_fields_and_url():
    text = """
公司：星河智能科技有限公司
职位：AI Agent 后端工程师
工作地点：上海
薪资：25-40K
岗位链接：https://example.com/jobs/agent-backend?from=test

岗位职责：
负责 Agent 应用后端服务设计，使用 Python、FastAPI、Redis。

任职要求：
熟悉 LLM 应用开发，有 RAG 或 LangGraph 经验。
"""
    parsed = parse_jd_text(text)

    assert parsed["title"] == "AI Agent 后端工程师"
    assert parsed["company"] == "星河智能科技有限公司"
    assert parsed["city"] == "上海"
    assert parsed["salary"] == "25-40K"
    assert parsed["url"] == "https://example.com/jobs/agent-backend?from=test"
    assert "Agent 应用后端服务" in parsed["description"]
    assert "LangGraph" in parsed["requirements"]


def test_parse_jd_text_falls_back_to_pdf_inference_rules():
    text = """
ACME科技有限公司
全栈开发工程师
base 深圳
18-30K
职位描述：负责企业内部系统开发。
"""
    parsed = parse_jd_text(text)

    assert parsed["title"] == "全栈开发工程师"
    assert parsed["company"] == "ACME科技有限公司"
    assert parsed["city"] == "深圳"
    assert parsed["salary"] == "18-30K"


def test_build_jd_confidence_marks_missing_fields():
    parsed = parse_jd_text("这是一段很短的说明，没有公司、城市、薪资或链接。")
    confidence = build_jd_confidence(parsed)

    assert confidence["description"] == "auto_extracted"
    assert confidence["url"] == "unrecognized"
    assert confidence["salary"] == "unrecognized"
