"""
个人经历证据库 API
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional

from src.storage.database import DatabaseManager
from src.helpers import load_config
from src.parsers.pdf import extract_text_from_pdf, parse_resume_text_to_evidence

router = APIRouter()


def get_db():
    config = load_config()
    return DatabaseManager(config['storage']['db_path'])


def _ev_to_dict(ev) -> dict:
    return {
        "id": ev.id,
        "type": ev.type,
        "title": ev.title,
        "content": ev.content,
        "skill_tags": ev.get_skill_tags(),
        "source": ev.source,
        "confidence": ev.confidence,
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
    }


class EvidenceCreateRequest(BaseModel):
    type: str  # skill/project/work_experience/education/achievement/certificate/portfolio
    title: str
    content: Optional[str] = ""
    skill_tags: Optional[list[str]] = []
    source: Optional[str] = "manual"
    confidence: Optional[float] = 0.9


class EvidenceUpdateRequest(BaseModel):
    type: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    skill_tags: Optional[list[str]] = None
    confidence: Optional[float] = None


@router.get("")
async def list_evidence(type: Optional[str] = None):
    """获取证据列表"""
    db = get_db()
    try:
        items = db.get_evidence_list(user_id=1, type_filter=type)
        return {"success": True, "data": [_ev_to_dict(ev) for ev in items]}
    finally:
        db.close()


@router.post("")
async def create_evidence(req: EvidenceCreateRequest):
    """新增证据条目"""
    db = get_db()
    try:
        item = db.add_evidence({
            "user_id": 1,
            "type": req.type,
            "title": req.title,
            "content": req.content or "",
            "skill_tags": req.skill_tags or [],
            "source": req.source or "manual",
            "confidence": req.confidence or 0.9,
        })
        if not item:
            raise HTTPException(status_code=500, detail="保存失败")
        return {"success": True, "data": _ev_to_dict(item)}
    finally:
        db.close()


@router.patch("/{evidence_id}")
async def update_evidence(evidence_id: int, req: EvidenceUpdateRequest):
    """更新证据条目"""
    db = get_db()
    try:
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="无更新内容")
        item = db.update_evidence(evidence_id, **updates)
        if not item:
            raise HTTPException(status_code=404, detail="证据不存在")
        return {"success": True, "data": _ev_to_dict(item)}
    finally:
        db.close()


@router.delete("/{evidence_id}")
async def delete_evidence(evidence_id: int):
    """删除证据条目"""
    db = get_db()
    try:
        ok = db.delete_evidence(evidence_id)
        if not ok:
            raise HTTPException(status_code=404, detail="证据不存在")
        return {"success": True, "message": "已删除"}
    finally:
        db.close()


@router.post("/init")
async def init_evidence_from_profile():
    """从 user_profile.json 初始化证据库"""
    try:
        from src.storage.init_evidence import init_evidence_from_profile as _init
        count = _init()
        return {"success": True, "message": f"初始化完成，导入 {count} 条证据"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-resume-pdf")
async def import_resume_pdf(file: UploadFile = File(...)):
    """上传 PDF 简历，自动抽取文本并导入个人经历证据库。"""
    db = get_db()
    try:
        filename = file.filename or "resume.pdf"
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="文件为空")
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="请上传 PDF 文件")

        try:
            text = extract_text_from_pdf(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF 解析失败: {e}")
        if len(text) < 20:
            raise HTTPException(status_code=400, detail="未能从 PDF 中识别到足够文本")

        evidence_items = parse_resume_text_to_evidence(text, filename)
        saved = []
        for item in evidence_items:
            ev = db.add_evidence(item)
            if ev:
                saved.append(_ev_to_dict(ev))

        if not saved:
            raise HTTPException(status_code=500, detail="未能保存证据")

        return {
            "success": True,
            "message": f"已从 PDF 简历导入 {len(saved)} 条证据",
            "count": len(saved),
            "data": saved,
            "text_preview": text[:500],
        }
    finally:
        db.close()
