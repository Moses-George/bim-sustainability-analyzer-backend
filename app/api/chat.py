"""AI sustainability assistant.

Streams real tokens from an LLM (DeepSeek) over Server-Sent Events so the
frontend can render them incrementally, like a real chatbot. If no
DEEPSEEK_API_KEY is configured, falls back to a small canned-hint responder
so the endpoint still works in a fresh/offline dev environment.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_sync_db
from app.core.deps import get_optional_user
from app.models.project import Project
from app.models.user import User
from app.schemas.schemas import ChatRequest, ChatResponse

router = APIRouter()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are the AI sustainability assistant embedded in a BIM embodied-carbon "
    "analysis tool. You help architects and engineers cut embodied and "
    "operational carbon. Be specific and quantitative when the project context "
    "gives you numbers (material breakdown, totals, energy use). Keep replies "
    "concise - a few short paragraphs or a tight bullet list, not an essay."
)

# Fallback used only when DEEPSEEK_API_KEY is not configured.
HINTS = {
    "reduce": "Focus on the top three carbon hotspots: concrete mix, structural steel grade, and envelope glazing. Replacing 30% cement with GGBS alone can cut ~18% of embodied CO2.",
    "concrete": "Switch to low-carbon concrete (GGBS or fly-ash blends). Also optimize slab thickness - most slabs are over-designed by 10-15%.",
    "steel": "Specify EAF recycled steel (600 vs 1900 kgCO2/ton). Combine with grade optimization for beams.",
    "energy": "Add PV, heat-pump, and improve envelope U-values. Operational carbon usually dominates over 30-year lifecycle.",
}


def _project_context(db: Session, user: User | None, project_id: int | None) -> str:
    if not project_id or not user:
        return ""
    project = db.get(Project, project_id)
    if not project or project.owner_id != user.id:
        return ""
    summary = project.summary_json or {}
    energy = project.energy
    lines = [
        f"Project: {project.name} ({project.building_type}, {project.climate_zone}, "
        f"{project.floor_area} m2, {project.num_floors} floors).",
    ]
    if summary.get("total_kg"):
        lines.append(
            f"Embodied carbon total: {summary['total_kg']/1000:.1f} t CO2e "
            f"across {summary.get('element_count', '?')} elements."
        )
    if summary.get("by_material"):
        top = sorted(summary["by_material"].items(), key=lambda kv: -kv[1])[:5]
        lines.append(
            "Top materials by embodied carbon (kg CO2e): "
            + ", ".join(f"{m}: {v:.0f}" for m, v in top)
        )
    if energy and energy.total_kwh:
        lines.append(
            f"Operational energy: {energy.total_kwh:.0f} kWh/yr "
            f"({energy.eui_kwh_m2:.1f} kWh/m2/yr), "
            f"{energy.operational_carbon_kg:.0f} kg CO2e/yr from grid."
        )
    return "\n".join(lines)


def _fallback_reply(last_message: str) -> str:
    low = last_message.lower()
    for k, v in HINTS.items():
        if k in low:
            return v
    return (
        "I can help evaluate embodied carbon, suggest low-carbon materials, and "
        "identify hotspots. Try asking: 'How can I reduce embodied carbon by 20%?' "
        "(Set DEEPSEEK_API_KEY on the backend for full LLM-powered answers.)"
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# @router.post("/", response_model=ChatResponse)
# def chat(
#     req: ChatRequest,
#     db: Session = Depends(get_sync_db),
#     user: User | None = Depends(get_optional_user),
# ):
#     """Non-streaming fallback (used if a caller can't consume SSE)."""
#     last = req.messages[-1].content if req.messages else ""
#     if not settings.DEEPSEEK_API_KEY:
#         return ChatResponse(reply=_fallback_reply(last))

#     from openai import OpenAI

#     client = OpenAI(
#         api_key=settings.DEEPSEEK_API_KEY,
#         base_url="https://api.deepseek.com",
#     )
#     context = _project_context(db, user, req.project_id)
#     system = SYSTEM_PROMPT + (f"\n\nProject context:\n{context}" if context else "")
#     resp = client.chat.completions.create(
#         model=settings.DEEPSEEK_MODEL,
#         max_tokens=1024,
#         messages=[{"role": "system", "content": system}]
#         + [{"role": m.role, "content": m.content} for m in req.messages],
#     )
#     text = resp.choices[0].message.content or ""
#     return ChatResponse(reply=text or _fallback_reply(last))


# @router.post("/stream")
# def chat_stream(
#     req: ChatRequest,
#     db: Session = Depends(get_sync_db),
#     user: User | None = Depends(get_optional_user),
# ):
#     """Real token-by-token streaming, like a real chatbot, over SSE."""
#     last = req.messages[-1].content if req.messages else ""

#     if not settings.DEEPSEEK_API_KEY:

#         def fallback_gen():
#             reply = _fallback_reply(last)
#             for word in reply.split(" "):
#                 yield _sse("token", {"text": word + " "})
#             yield _sse("done", {})

#         return StreamingResponse(fallback_gen(), media_type="text/event-stream")

#     from openai import OpenAI

#     client = OpenAI(
#         api_key=settings.DEEPSEEK_API_KEY,
#         base_url="https://api.deepseek.com",
#     )
#     context = _project_context(db, user, req.project_id)
#     system = SYSTEM_PROMPT + (f"\n\nProject context:\n{context}" if context else "")
#     messages = [{"role": "system", "content": system}] + [
#         {"role": m.role, "content": m.content} for m in req.messages
#     ]

#     def gen():
#         try:
#             stream = client.chat.completions.create(
#                 model=settings.DEEPSEEK_MODEL,
#                 max_tokens=1024,
#                 messages=messages,
#                 stream=True,
#             )
#             for chunk in stream:
#                 delta = chunk.choices[0].delta
#                 if delta.content:
#                     yield _sse("token", {"text": delta.content})
#             yield _sse("done", {})
#         except Exception as exc:  # pragma: no cover - network/key failures
#             logger.exception("chat stream failed")
#             yield _sse("error", {"message": str(exc)})

#     return StreamingResponse(
#         gen(),
#         media_type="text/event-stream",
#         headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
#     )


from openai import OpenAI


# Non-streaming version
@router.post("/", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    db: Session = Depends(get_sync_db),
    user: User | None = Depends(get_optional_user),
):
    last = req.messages[-1].content if req.messages else ""
    if not settings.OPENROUTER_API_KEY:
        return ChatResponse(reply=_fallback_reply(last))

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENROUTER_API_KEY,
    )
    context = _project_context(db, user, req.project_id)
    system = SYSTEM_PROMPT + (f"\n\nProject context:\n{context}" if context else "")
    resp = client.chat.completions.create(
        model=settings.OPENROUTER_MODEL,
        max_tokens=1024,
        messages=[{"role": "system", "content": system}]
        + [{"role": m.role, "content": m.content} for m in req.messages],
    )
    text = resp.choices[0].message.content or ""
    return ChatResponse(reply=text or _fallback_reply(last))


@router.post("/stream")
def chat_stream(
    req: ChatRequest,
    db: Session = Depends(get_sync_db),
    user: User | None = Depends(get_optional_user),
):
    last = req.messages[-1].content if req.messages else ""

    if not settings.OPENROUTER_API_KEY:

        def fallback_gen():
            reply = _fallback_reply(last)
            for word in reply.split(" "):
                yield _sse("token", {"text": word + " "})
            yield _sse("done", {})

        return StreamingResponse(fallback_gen(), media_type="text/event-stream")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENROUTER_API_KEY,
    )
    context = _project_context(db, user, req.project_id)
    system = SYSTEM_PROMPT + (f"\n\nProject context:\n{context}" if context else "")
    messages = [{"role": "system", "content": system}] + [
        {"role": m.role, "content": m.content} for m in req.messages
    ]

    def gen():
        try:
            stream = client.chat.completions.create(
                model=settings.OPENROUTER_MODEL,
                max_tokens=1024,
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield _sse("token", {"text": delta.content})
            yield _sse("done", {})
        except Exception as exc:
            logger.exception("chat stream failed")
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
