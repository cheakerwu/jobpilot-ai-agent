"""
个人经历证据库 API
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel, Field
from typing import Literal, Optional

from web_api.deps import get_db
from src.parsers.pdf import extract_text_from_pdf, parse_resume_text_to_evidence
from src.auth.dependencies import get_current_user
from src.storage.models import User

router = APIRouter()

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB


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


EVIDENCE_TYPES = Literal[
    "skill", "project", "work_experience", "education",
    "achievement", "certificate", "portfolio",
]


class EvidenceCreateRequest(BaseModel):
    type: EVIDENCE_TYPES
    title: str = Field(..., min_length=1, max_length=200)
    content: Optional[str] = Field("", max_length=10000)
    skill_tags: Optional[list[str]] = Field(default_factory=list, max_length=20)
    source: Optional[str] = "manual"
    confidence: Optional[float] = Field(0.9, ge=0.0, le=1.0)


class EvidenceUpdateRequest(BaseModel):
    type: Optional[EVIDENCE_TYPES] = None
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, max_length=10000)
    skill_tags: Optional[list[str]] = Field(None, max_length=20)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


@router.get("")
async def list_evidence(
    type: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(get_current_user),
):
    """获取证据列表（分页）"""
    page = max(1, page)
    per_page = max(1, min(per_page, 100))
    db = get_db()
    try:
        items = db.get_evidence_list(user_id=current_user.id, type_filter=type)
        total = len(items)
        start = (page - 1) * per_page
        paged = items[start:start + per_page]
        return {
            "success": True,
            "data": [_ev_to_dict(ev) for ev in paged],
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    finally:
        db.close()


@router.post("")
async def create_evidence(req: EvidenceCreateRequest, current_user: User = Depends(get_current_user)):
    """新增证据条目"""
    db = get_db()
    try:
        item = db.add_evidence({
            "user_id": current_user.id,
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
async def update_evidence(evidence_id: int, req: EvidenceUpdateRequest, current_user: User = Depends(get_current_user)):
    """更新证据条目"""
    db = get_db()
    try:
        existing = db.get_evidence_by_id(evidence_id)
        if not existing:
            raise HTTPException(status_code=404, detail="证据不存在")
        if existing.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

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
async def delete_evidence(evidence_id: int, current_user: User = Depends(get_current_user)):
    """删除证据条目"""
    db = get_db()
    try:
        existing = db.get_evidence_by_id(evidence_id)
        if not existing:
            raise HTTPException(status_code=404, detail="证据不存在")
        if existing.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

        ok = db.delete_evidence(evidence_id)
        if not ok:
            raise HTTPException(status_code=404, detail="证据不存在")
        return {"success": True, "message": "已删除"}
    finally:
        db.close()


@router.post("/init")
async def init_evidence_from_profile(current_user: User = Depends(get_current_user)):
    """从 user_profile.json 初始化证据库"""
    try:
        from src.storage.init_evidence import init_evidence_from_profile as _init
        count = _init(user_id=current_user.id)
        return {"success": True, "message": f"初始化完成，导入 {count} 条证据"}
    except Exception:
        raise HTTPException(status_code=500, detail="初始化证据库失败")


@router.post("/import-resume-pdf")
async def import_resume_pdf(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    """上传 PDF 简历，自动抽取文本并导入个人经历证据库。"""
    db = get_db()
    try:
        filename = file.filename or "resume.pdf"
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="文件为空")
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="文件大小不能超过 10MB")
        is_pdf_content = content.startswith(b'%PDF-')
        if not filename.lower().endswith(".pdf") and not is_pdf_content:
            raise HTTPException(status_code=400, detail="请上传 PDF 文件")
        if not is_pdf_content:
            raise HTTPException(status_code=400, detail="文件内容不是有效的 PDF 格式")

        try:
            text = extract_text_from_pdf(content)
        except Exception:
            raise HTTPException(status_code=400, detail="PDF 解析失败，请确认文件格式正确")
        if len(text) < 20:
            raise HTTPException(status_code=400, detail="未能从 PDF 中识别到足够文本")

        evidence_items = parse_resume_text_to_evidence(text, filename)
        saved = []
        for item in evidence_items:
            item["user_id"] = current_user.id
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
        }
    finally:
        db.close()
