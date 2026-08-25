from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    category: str = "impossible"
    premise: str = ""
    stage: str = "idea"
    status: str = "needs_review"
    research_json: str = "{}"
    script_json: str = "{}"
    storyboard_json: str = "[]"
    scenes_json: str = "[]"
    voice_json: str = "{}"
    render_json: str = "{}"
    publish_json: str = "{}"
    estimated_cost: float = 0.0
    actual_cost: float = 0.0
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
