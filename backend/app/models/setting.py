from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RuntimeSetting(SQLModel, table=True):
    id: Optional[int] = Field(default=1, primary_key=True)
    overrides_json: str = "{}"
    updated_at: datetime = Field(default_factory=utcnow)
