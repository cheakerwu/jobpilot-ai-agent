"""
流式输出 API（SSE）
"""
import json

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.auth.dependencies import get_current_user
from src.storage.models import User
from web_api.routers._llm_utils import build_llm_provider, check_ai_trial, consume_ai_trial, get_ai_limit

router = APIRouter()


class StreamRequest(BaseModel):
    prompt: str
    use_ai: bool = True


def _sse_event(data: dict) -> bytes:
    """格式化 SSE 事件。"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


@router.post("/generate")
async def stream_generate(req: StreamRequest, current_user: User = Depends(get_current_user)):
    """流式生成文本（SSE）。前端用 EventSource 或 fetch + ReadableStream 消费。"""
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt 不能为空")

    provider, config = build_llm_provider()
    if provider is None:
        raise HTTPException(status_code=503, detail="AI 服务未配置")

    if req.use_ai:
        check_ai_trial(current_user, config)

    def event_stream():
        try:
            for chunk in provider.generate_stream(req.prompt):
                yield _sse_event({"type": "chunk", "content": chunk})

            # 扣减配额
            if req.use_ai:
                from web_api.deps import get_db
                db = get_db()
                try:
                    consume_ai_trial(current_user.id, db)
                    user = db.get_user_by_id(current_user.id)
                    limit = get_ai_limit(user, config)
                    yield _sse_event({
                        "type": "done",
                        "ai_usage_count": user.ai_usage_count or 0,
                        "ai_limit": limit,
                    })
                finally:
                    db.close()
            else:
                yield _sse_event({"type": "done"})
        except Exception as e:
            import logging
            logging.getLogger("job_agent").error(f"Stream error: {e}", exc_info=True)
            yield _sse_event({"type": "error", "message": str(e)[:200]})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
