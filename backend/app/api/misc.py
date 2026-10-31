"""Voice transcription, Strategist and account-settings endpoints."""

import logging
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from groq import APIError
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.sara import client
from app.api.auth import user_out
from app.audit import audit
from app.config import get_settings
from app.data.destinations import DESTINATIONS, find_destination
from app.db import get_db
from app.models import User
from app.security.deps import get_current_user
from app.security.rate_limit import enforce
from app.strategist.base import TripContext
from app.strategist.runner import advise, avoid_in, best_time, upcoming_peaks, where_to_go

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["misc"])

MAX_AUDIO_BYTES = 10 * 1024 * 1024
# Vocabulary hint so Whisper spells Indian places and travel terms correctly.
WHISPER_PROMPT = ("Sara Explorer, India trip planning. Sara, Ladakh, Leh, Goa, Kerala, Munnar, Alleppey, Kochi, Jaipur, "
                  "Udaipur, Jaisalmer, Varanasi, Rishikesh, Manali, Shimla, Srinagar, Darjeeling, Gangtok, Tawang, "
                  "Shillong, Andaman, Hampi, Rann of Kutch, Amritsar, Puducherry, IRCTC, Tatkal, PNR, waitlist.")

AUDIO_TYPES = {"audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav", "audio/x-wav", "audio/m4a",
               "audio/x-m4a", "video/webm"}


@router.post("/voice/transcribe")
async def transcribe(audio: UploadFile = File(...), user: User = Depends(get_current_user)):
    await enforce(f"voice:{user.id}", 10, 60)
    ctype = (audio.content_type or "").split(";")[0].strip()
    if ctype not in AUDIO_TYPES:
        raise HTTPException(415, "Unsupported audio format")
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Recording is too long (max 10 MB)")
    if len(data) < 1000:
        raise HTTPException(400, "Recording is empty")
    ext = {"audio/mp4": "m4a", "audio/m4a": "m4a", "audio/x-m4a": "m4a", "audio/mpeg": "mp3", "audio/ogg": "ogg",
           "audio/wav": "wav", "audio/x-wav": "wav"}.get(ctype, "webm")
    try:
        result = await client().audio.transcriptions.create(
            file=(f"voice.{ext}", data), model=get_settings().groq_stt_model, temperature=0,
            response_format="verbose_json", prompt=WHISPER_PROMPT,
        )
    except (APIError, RuntimeError) as exc:
        log.warning("transcription failed: %s", exc)
        raise HTTPException(502, "Could not transcribe audio. Please try again.")
    return {"text": (result.text or "").strip(), "language": getattr(result, "language", None)}


# ---------------------------------------------------------------- strategist

@router.get("/strategist/destinations")
async def destinations(user: User = Depends(get_current_user)):
    return [{"slug": d["slug"], "name": d["name"], "state": d["state"], "tags": d["tags"]}
            for d in sorted(DESTINATIONS.values(), key=lambda d: d["name"])]


@router.get("/strategist/best-time/{slug}")
async def strategist_best_time(slug: str, user: User = Depends(get_current_user)):
    d = DESTINATIONS.get(slug)
    if not d:
        raise HTTPException(404, "Unknown destination")
    return best_time(d)


@router.get("/strategist/where")
async def strategist_where(month: int = Query(ge=1, le=12), interest: str | None = None,
                           traveller_type: str | None = Query(default=None, pattern="^(solo|couple|family|friends|seniors|business)$"),
                           user: User = Depends(get_current_user)):
    return {"picks": where_to_go(month, interest, limit=8, traveller_type=traveller_type), "avoid": avoid_in(month),
            "peaks": upcoming_peaks()}


class AdviceIn(BaseModel):
    destination: str = Field(max_length=60)
    origin: str | None = Field(default=None, max_length=60)
    travel_date: date | None = None
    nights: int = Field(default=3, ge=1, le=30)
    adults: int = Field(default=1, ge=1, le=9)
    traveller_type: str | None = Field(default=None, pattern="^(solo|couple|family|friends|seniors|business)$")


@router.post("/strategist/advice")
async def strategist_advice(body: AdviceIn, user: User = Depends(get_current_user)):
    await enforce(f"advice:{user.id}", 30, 60)
    d = find_destination(body.destination)
    if not d:
        raise HTTPException(404, "Unknown destination")
    if body.travel_date and body.travel_date < date.today():
        raise HTTPException(422, "Travel date is in the past")
    ctx = TripContext(destination=d, month=(body.travel_date or date.today()).month, origin=body.origin,
                      travel_date=body.travel_date, nights=body.nights, adults=body.adults,
                      traveller_type=body.traveller_type)
    return {"destination": d["name"], "suggestions": [s.to_dict() for s in advise(ctx, limit=8)]}


# ---------------------------------------------------------------- account settings

class SettingsIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9 ]{10,15}$")
    spend_cap_inr: int | None = Field(default=None, ge=1000)


@router.patch("/account/settings")
async def update_settings(body: SettingsIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if body.name is not None:
        user.name = body.name.strip()
    if body.phone is not None:
        user.phone = body.phone
    if body.spend_cap_inr is not None:
        cap = get_settings().max_spend_cap_inr
        if body.spend_cap_inr > cap:
            raise HTTPException(422, f"Spending limit can be at most ₹{cap:,}")
        user.spend_cap_inr = body.spend_cap_inr
    audit(db, "account.settings_updated", user.id, fields=[k for k, v in body.model_dump().items() if v is not None])
    await db.commit()
    return user_out(user)
