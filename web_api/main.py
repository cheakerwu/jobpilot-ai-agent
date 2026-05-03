"""
JobPilot - 个人求职 CRM + Agent Copilot
FastAPI Web API 主入口
"""
from fastapi import FastAPI, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os

from src.helpers import load_config

app = FastAPI(title="JobPilot - 求职 CRM + Agent Copilot", version="3.0")

# CORS 配置：环境变量 > 配置文件 > 默认 *
_config = load_config()
_env_origins = os.environ.get("ALLOWED_ORIGINS")
if _env_origins:
    _origins = [o.strip() for o in _env_origins.split(",")]
else:
    _origins = _config.get("server", {}).get("allowed_origins", ["*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials="*" not in _origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(os.path.join(BASE_DIR, "templates"))

# ── 认证路由（无需登录） ──────────────────────────────────────────────────────
from web_api.routers import auth

app.include_router(auth.router, prefix="/api/auth", tags=["认证"])

# ── 核心路由 ──────────────────────────────────────────────────────────────────
from web_api.routers import jobs, analytics

app.include_router(jobs.router, prefix="/api/jobs", tags=["岗位管理"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["数据分析"])

from web_api.routers import imports, evidence, analyses, resume_versions, agent_runs, settings, kanban, cover_letters, interview_prep, onboarding, stats

app.include_router(imports.router, prefix="/api/imports", tags=["岗位导入"])
app.include_router(evidence.router, prefix="/api/evidence", tags=["证据库"])
app.include_router(analyses.router, prefix="/api/analyses", tags=["岗位分析"])
app.include_router(resume_versions.router, prefix="/api/resumes", tags=["简历版本"])
app.include_router(agent_runs.router, prefix="/api/agent-runs", tags=["Agent 运行记录"])
app.include_router(settings.router, prefix="/api/settings", tags=["系统设置"])
app.include_router(kanban.router, prefix="/api/kanban", tags=["看板"])
app.include_router(stats.router, prefix="/api/stats", tags=["统计"])
app.include_router(cover_letters.router, prefix="/api/cover-letters", tags=["求职信"])
app.include_router(interview_prep.router, prefix="/api/interview-prep", tags=["面试准备"])
app.include_router(onboarding.router, prefix="/api/onboarding", tags=["新手进度"])


@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="auth.html")


@app.get("/app")
async def app_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse(request=request, name="landing.html")


_health_bearer = HTTPBearer(auto_error=False)


@app.get("/health")
async def health(credentials: HTTPAuthorizationCredentials = Depends(_health_bearer)):
    """健康检查：未认证仅返回状态，认证后返回详细信息"""
    if not credentials:
        return {"status": "ok"}

    # 验证 token 有效性
    from src.auth.security import decode_access_token
    payload = decode_access_token(credentials.credentials)
    if not payload:
        return {"status": "ok"}

    from src.storage.database import DatabaseManager
    db_status = "ok"
    try:
        from sqlalchemy import text
        db = DatabaseManager(_config['storage']['db_path'])
        db.session.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_status = "error"

    resume_cfg = _config.get("resume", {})
    llm_configured = bool(os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"))

    return {
        "status": "ok",
        "version": "3.0",
        "db": db_status,
        "llm_provider": resume_cfg.get("provider", "none"),
        "llm_key_configured": llm_configured,
    }
