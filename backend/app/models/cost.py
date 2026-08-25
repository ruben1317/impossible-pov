from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GenerationCost(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: Optional[int] = Field(default=None, index=True)
    provider: str
    operation: str
    scene_index: Optional[int] = None
    estimated_cost: float = 0.0
    actual_cost: float = 0.0
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utcnow, index=True)
