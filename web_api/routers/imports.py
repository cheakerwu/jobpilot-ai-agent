"""
岗位导入 API（手动粘贴 / CSV 上传）
"""
import sys
import os
import hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel
from typing import Optional

from src.storage.database import DatabaseManager
from src.sources.manual_source import ManualJobSource
from src.sources.csv_source import CsvJobSource
from src.helpers import load_config
from src.parsers.pdf import extract_text_from_pdf, infer_job_from_jd_text
from src.auth.dependencies import get_current_user
from src.storage.models import User

router = APIRouter()

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB


def get_db():
    config = load_config()
    return DatabaseManager(config['storage']['db_path'])


class ManualImportRequest(BaseModel):
    title: str
    company: str
    city: Optional[str] = ""
    salary: Optional[str] = ""
    description: str
    requirements: Optional[str] = ""
    url: Optional[str] = ""


@router.post("/manual")
async def import_manual(req: ManualImportRequest, current_user: User = Depends(get_current_user)):
    """手动粘贴 JD 导入单个岗位"""
    db = get_db()
    try:
        source = ManualJobSource()
        job_data = source.normalize(req.model_dump())
        job_data["user_id"] = current_user.id

        if not job_data["title"] or not job_data["company"]:
            raise HTTPException(status_code=400, detail="职位名称和公司名称必填")

        # 去重检查
        existing = db.get_job_by_platform_id(job_data["job_id"])
        if existing:
            return {"success": False, "message": "该岗位已存在", "job_id": existing.id}

        job = db.add_job(job_data)
        if not job:
            raise HTTPException(status_code=500, detail="保存岗位失败")

        # 记录批次
        db.create_import_batch({
            "user_id": current_user.id,
            "source": "manual",
            "total_count": 1,
            "success_count": 1,
            "failed_count": 0,
        })

        return {
            "success": True,
            "message": "岗位导入成功",
            "job": {"id": job.id, "title": job.title, "company": job.company},
        }
    finally:
        db.close()


@router.post("/csv")
async def import_csv(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    """CSV / Excel 批量导入岗位"""
    db = get_db()
    try:
        filename = file.filename or ""
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="文件为空")
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="文件大小不能超过 10MB")

        source = CsvJobSource()
        success_count = 0
        failed_count = 0
        skipped_count = 0
        results = []

        for raw in source.fetch({"file_content": content, "filename": filename}):
            job_data = source.normalize(raw)
            job_data["user_id"] = current_user.id
            if not job_data.get("title") or not job_data.get("company"):
                failed_count += 1
                continue

            existing = db.get_job_by_platform_id(job_data["job_id"])
            if existing:
                skipped_count += 1
                continue

            job = db.add_job(job_data)
            if job:
                success_count += 1
                results.append({"id": job.id, "title": job.title, "company": job.company})
            else:
                failed_count += 1

        batch = db.create_import_batch({
            "user_id": current_user.id,
            "source": "csv",
            "filename": filename,
            "total_count": success_count + failed_count + skipped_count,
            "success_count": success_count,
            "failed_count": failed_count,
        })

        return {
            "success": True,
            "batch_id": batch.id if batch else None,
            "total": success_count + failed_count + skipped_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "jobs": results,
        }
    finally:
        db.close()


@router.post("/pdf-jd")
async def import_pdf_jd(
    file: UploadFile = File(...),
    title: str = Form(""),
    company: str = Form(""),
    city: str = Form(""),
    salary: str = Form(""),
    url: str = Form(""),
    current_user: User = Depends(get_current_user),
):
    """上传 PDF JD，自动识别并导入岗位池。"""
    db = get_db()
    try:
        filename = file.filename or "jd.pdf"
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="文件为空")
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="文件大小不能超过 10MB")
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="请上传 PDF 文件")

        try:
            text = extract_text_from_pdf(content)
        except Exception:
            raise HTTPException(status_code=400, detail="PDF 解析失败，请确认文件格式正确")
        if len(text) < 20:
            raise HTTPException(status_code=400, detail="未能从 PDF 中识别到足够文本")

        inferred = infer_job_from_jd_text(text, filename)
        raw_job = {
            **inferred,
            "job_id": "pdf_jd_" + hashlib.sha256((filename + text[:4000]).encode("utf-8")).hexdigest()[:12],
            "title": title.strip() or inferred["title"],
            "company": company.strip() or inferred["company"],
            "city": city.strip() or inferred["city"],
            "salary": salary.strip() or inferred["salary"],
            "url": url.strip(),
        }

        source = ManualJobSource()
        job_data = source.normalize(raw_job)
        job_data["source"] = "pdf_jd"
        job_data["platform"] = "pdf_jd"
        job_data["user_id"] = current_user.id

        if not job_data["title"]:
            raise HTTPException(status_code=400, detail="未识别到职位名称")
        if not job_data["company"]:
            job_data["company"] = "未知公司"

        existing = db.get_job_by_platform_id(job_data["job_id"])
        if existing:
            return {
                "success": False,
                "message": "该 PDF JD 已导入过",
                "job_id": existing.id,
            }

        job = db.add_job(job_data)
        if not job:
            raise HTTPException(status_code=500, detail="保存岗位失败")

        batch = db.create_import_batch({
            "user_id": current_user.id,
            "source": "pdf_jd",
            "filename": filename,
            "total_count": 1,
            "success_count": 1,
            "failed_count": 0,
        })

        return {
            "success": True,
            "message": "PDF JD 导入成功",
            "batch_id": batch.id if batch else None,
            "job": {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "city": job.city,
                "salary": job.salary,
            },
        }
    finally:
        db.close()


@router.get("/{batch_id}")
async def get_batch(batch_id: int, current_user: User = Depends(get_current_user)):
    """获取导入批次详情"""
    db = get_db()
    try:
        batch = db.get_import_batch(batch_id)
        if not batch or batch.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="批次不存在")
        return {
            "success": True,
            "data": {
                "id": batch.id,
                "source": batch.source,
                "filename": batch.filename,
                "total_count": batch.total_count,
                "success_count": batch.success_count,
                "failed_count": batch.failed_count,
                "created_at": batch.created_at.isoformat() if batch.created_at else None,
            },
        }
    finally:
        db.close()
