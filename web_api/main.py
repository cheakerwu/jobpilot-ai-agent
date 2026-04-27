"""
JobPilot - 个人求职 CRM + Agent Copilot
FastAPI Web API 主入口
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="JobPilot - 求职 CRM + Agent Copilot", version="3.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(os.path.join(BASE_DIR, "templates"))

# ── 核心路由 ──────────────────────────────────────────────────────────────────
from web_api.routers import jobs, analytics

app.include_router(jobs.router, prefix="/api/jobs", tags=["岗位管理"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["数据分析"])

from web_api.routers import imports, evidence, analyses, resume_versions, agent_runs, settings

app.include_router(imports.router, prefix="/api/imports", tags=["岗位导入"])
app.include_router(evidence.router, prefix="/api/evidence", tags=["证据库"])
app.include_router(analyses.router, prefix="/api/analyses", tags=["岗位分析"])
app.include_router(resume_versions.router, prefix="/api/resumes", tags=["简历版本"])
app.include_router(agent_runs.router, prefix="/api/agent-runs", tags=["Agent 运行记录"])
app.include_router(settings.router, prefix="/api/settings", tags=["系统设置"])


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0"}
