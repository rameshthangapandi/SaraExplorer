from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def audit(db: AsyncSession, action: str, user_id: str | None = None, entity_id: str | None = None,
          ip: str = "", **meta) -> None:
    """Queue an audit row on the caller's transaction. Never put secrets or tokens in meta."""
    db.add(AuditLog(user_id=user_id, action=action, entity_id=entity_id, meta=meta, ip=ip))
