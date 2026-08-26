from typing import Any
from pydantic import BaseModel, Field


class Idea(BaseModel):
    title: str
    category: str
    premise: str
    viral_reason: str
    estimated_cost: float = 0.0


class IdeaRequest(BaseModel):
    count: int | None = None
    category: str | None = None


class ProjectCreate(BaseModel):
    title: str
    category: str
    premise: str = ""


class ActionResponse(BaseModel):
    ok: bool = True
    project_id: int
    stage: str
    status: str
    data: dict[str, Any] = Field(default_factory=dict)


class SceneDecision(BaseModel):
    scene_index: int
    approved: bool
    notes: str = ""


class SceneVideoDecision(BaseModel):
    scene_index: int

class ScriptRevisionRequest(BaseModel):
    instructions: str = Field(min_length=1, max_length=6000)

class PublishRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    privacy_status: str | None = None
    scheduled_at: str | None = None
    platforms: list[str] = Field(
        default_factory=lambda: ["youtube", "tiktok"]
    )


class RuntimeSettingsUpdate(BaseModel):
    monthly_cap: float | None = Field(default=None, ge=0, le=100000)
    target_cost_per_video: float | None = Field(default=None, ge=0, le=10000)
    duration_seconds: int | None = Field(default=None, ge=10, le=600)
    scene_count: int | None = Field(default=None, ge=1, le=30)
    clip_seconds: int | None = Field(default=None, ge=1, le=30)
    idea_count: int | None = Field(default=None, ge=1, le=30)
    privacy_status: str | None = None
    text_provider: str | None = None
    research_provider: str | None = None
    video_provider: str | None = None
    voice_provider: str | None = None
    renderer_provider: str | None = None
    publisher_provider: str | None = None
    openai_model: str | None = None
    runway_model: str | None = None
    elevenlabs_voice_id: str | None = None
    elevenlabs_model_id: str | None = None
    hard_stop_on_cap: bool | None = None
