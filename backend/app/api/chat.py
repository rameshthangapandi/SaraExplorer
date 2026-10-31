import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from groq import APIError, RateLimitError
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.sara import graph
from app.agents.tools import ToolContext
from app.db import SessionLocal, aware, get_db, utcnow
from app.models import Conversation, Message, User
from app.security.deps import get_current_user, owned
from app.security.rate_limit import enforce

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

HISTORY_LIMIT = 16


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=32)


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


@router.post("/stream")
async def chat_stream(body: ChatIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await enforce(f"chat:{user.id}", 20, 60)
    await enforce(f"chat-day:{user.id}", 400, 86400)

    if body.conversation_id:
        conv = await owned(db, Conversation, body.conversation_id, user)
    else:
        conv = Conversation(user_id=user.id, title=body.message.strip()[:60])
        db.add(conv)
        await db.flush()

    rows = (await db.scalars(select(Message).where(Message.conversation_id == conv.id)
                             .order_by(Message.created_at.desc()).limit(HISTORY_LIMIT))).all()
    history = [{"role": m.role, "content": m.model_content or m.content} for m in reversed(rows)]
    db.add(Message(conversation_id=conv.id, role="user", content=body.message.strip()))
    conv.updated_at = utcnow()
    await db.commit()
    conv_id, user_id = conv.id, user.id

    async def events():
        yield _sse({"type": "conversation", "conversation_id": conv_id})
        text, cards, notes = "", [], []
        state = {"messages": [*history, {"role": "user", "content": body.message.strip()}],
                 "steps": 0, "cards": [], "notes": []}
        try:
            async for ev in graph.astream(state, {"configurable": {"ctx": ToolContext(user_id=user_id)},
                                                  "recursion_limit": 20}, stream_mode="custom"):
                if ev["type"] == "token":
                    text += ev["text"]
                elif ev["type"] == "step" and text:
                    text += "\n\n"
                elif ev["type"] == "card":
                    cards.append(ev["card"])
                elif ev["type"] == "status":
                    notes.append(ev["text"])
                elif ev["type"] == "replace":
                    text = ev["text"]
                elif ev["type"] == "grounding":
                    continue
                yield _sse(ev)
        except RateLimitError:
            msg = "I'm getting a lot of requests right now. Please try again in a minute."
            text += ("\n\n" if text else "") + msg
            yield _sse({"type": "error", "text": msg})
        except (APIError, RuntimeError) as exc:
            log.warning("LLM error: %s", exc)
            msg = "Sorry, I couldn't reach my planning brain just now. Please try again."
            text += ("\n\n" if text else "") + msg
            yield _sse({"type": "error", "text": msg})
        except Exception:
            log.exception("chat failed")
            msg = "Something went wrong on my side. Please try again."
            text += ("\n\n" if text else "") + msg
            yield _sse({"type": "error", "text": msg})

        if not text.strip():
            text = "Here's what I found." if cards else "I couldn't finish that. Could you rephrase?"
        # Keep option IDs / consent IDs visible to the model next turn.
        tool_digest = "\n".join(f"[{c.get('type')}] " + json.dumps(_digest(c), default=str)[:900] for c in cards)
        async with SessionLocal() as s:
            msg_row = Message(conversation_id=conv_id, role="assistant", content=text, cards=cards,
                              model_content=text + (f"\n\n(Tool results shown to the user:\n{tool_digest})" if tool_digest else ""))
            s.add(msg_row)
            await s.commit()
            yield _sse({"type": "done", "message_id": msg_row.id})

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


def _digest(card: dict) -> dict:
    t = card.get("type")
    if t in ("flights", "trains", "hotels"):
        keys = {"flights": ("id", "airline", "flight_no", "depart", "price_total"),
                "trains": ("id", "train_no", "class", "depart", "availability", "price_total"),
                "hotels": ("id", "hotel", "price_per_night", "price_total")}[t]
        return {"options": [{k: o.get(k) for k in keys} for o in card.get("options", [])]}
    if t == "consent":
        return {"consent_id": card["consent_id"], "total_inr": card["total_inr"], "status": card["status"]}
    return {"title": card.get("title")}


@router.get("/conversations")
async def conversations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Conversation).where(Conversation.user_id == user.id)
                             .order_by(Conversation.updated_at.desc()).limit(50))).all()
    return [{"id": c.id, "title": c.title, "updated_at": aware(c.updated_at)} for c in rows]


@router.get("/conversations/{conv_id}")
async def conversation(conv_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    conv = await owned(db, Conversation, conv_id, user)
    rows = (await db.scalars(select(Message).where(Message.conversation_id == conv.id)
                             .order_by(Message.created_at))).all()
    return {"id": conv.id, "title": conv.title,
            "messages": [{"id": m.id, "role": m.role, "content": m.content, "cards": m.cards or []} for m in rows]}


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    conv = await owned(db, Conversation, conv_id, user)
    await db.execute(delete(Message).where(Message.conversation_id == conv.id))
    await db.delete(conv)
    await db.commit()
    return {"ok": True}
