from __future__ import annotations
import json
from datetime import datetime, timezone

from sqlmodel import Session

from app.models.project import Project
from app.providers.registry import ProviderRegistry
from app.services.budget import BudgetService, BudgetExceeded


def dump(value): return json.dumps(value, ensure_ascii=False)
def load(value, fallback):
    try: return json.loads(value)
    except Exception: return fallback


def touch(project: Project):
    project.updated_at = datetime.now(timezone.utc)


class WorkflowService:
    def __init__(self, session: Session, config: dict):
        self.session = session
        self.config = config
        self.providers = ProviderRegistry(config)
        self.budget = BudgetService(session, config)

    def generate_ideas(self, count: int | None, category: str | None):
        n = count or self.config.get("content", {}).get("idea_count", 10)
        return self.providers.text().generate_ideas(count=n, category=category, config=self.config)

    def create_project(self, title: str, category: str, premise: str):
        p = Project(title=title, category=category, premise=premise, stage="idea", status="needs_review")
        self.session.add(p); self.session.commit(); self.session.refresh(p)
        return p

    def approve_idea(self, p: Project):
        p.stage = "research"; p.status = "ready_to_generate"; touch(p)
        self.session.add(p); self.session.commit(); self.session.refresh(p)
        return p

    def generate_script(self, p: Project):
        research = self.providers.research().research(title=p.title, category=p.category, premise=p.premise, config=self.config)
        script = self.providers.text().write_script(title=p.title, premise=p.premise, research=research, config=self.config)
        p.research_json = dump(research); p.script_json = dump(script)
        p.stage = "script"; p.status = "needs_review"; touch(p)
        self.session.add(p); self.session.commit(); self.session.refresh(p)
        return p

    def approve_script(self, p: Project):
        p.stage = "storyboard"; p.status = "ready_to_generate"; touch(p)
        self.session.add(p); self.session.commit(); self.session.refresh(p)
        return p

    def generate_storyboard(self, p: Project):
        storyboard = self.providers.text().storyboard(script=load(p.script_json, {}), config=self.config)
        p.storyboard_json = dump(storyboard); p.stage = "storyboard"; p.status = "needs_review"; touch(p)
        self.session.add(p); self.session.commit(); self.session.refresh(p)
        return p

    def set_scene_approval(self, p: Project, idx: int, approved: bool, notes: str = ""):
        scenes = load(p.storyboard_json, [])
        if idx < 0 or idx >= len(scenes): raise ValueError("Invalid scene index")
        scenes[idx]["approved"] = approved
        scenes[idx]["notes"] = notes
        p.storyboard_json = dump(scenes)
        if scenes and all(x.get("approved") for x in scenes):
            p.status = "ready_to_generate"
            p.stage = "video_scenes"
        touch(p); self.session.add(p); self.session.commit(); self.session.refresh(p)
        return p

    def generate_video_scenes(self, p: Project):
        board = load(p.storyboard_json, [])
        if not board or not all(x.get("approved") for x in board):
            raise ValueError("Approve all storyboard scenes before generating video")
        provider_name = self.config.get("providers", {}).get("video", "mock")
        clip_seconds = float(self.config.get("provider_options", {}).get("runway", {}).get("clip_seconds", self.config.get("video_defaults", {}).get("clip_seconds", 5)))
        cps = float(self.config.get("provider_options", {}).get("runway", {}).get("estimated_cost_per_second", 0.0)) if provider_name == "runway" else 0.0
        estimated_total = round(len(board) * clip_seconds * cps, 4)
        self.budget.assert_allowed(estimated_total)
        provider = self.providers.media("video")
        scenes = []
        for scene in board:
            estimated = round(clip_seconds * cps, 4)
            result = provider.generate(prompt=scene["prompt"], scene_index=scene["index"], project_id=p.id, config=self.config)
            actual = float(result.get("cost", estimated if provider_name != "mock" else 0.0) or 0.0)
            self.budget.record(project_id=p.id, provider=provider_name, operation="video_scene", scene_index=scene["index"], estimated_cost=estimated, actual_cost=actual)
            scenes.append({**scene, "video": result, "video_approved": False})
        p.estimated_cost = float(p.estimated_cost or 0) + estimated_total
        p.actual_cost = float(p.actual_cost or 0) + sum(float(s["video"].get("cost", 0) or 0) for s in scenes)
        p.scenes_json = dump(scenes); p.stage = "video_scenes"; p.status = "needs_review"; touch(p)
        self.session.add(p); self.session.commit(); self.session.refresh(p)
        return p

    def approve_all_video_scenes(self, p: Project):
        scenes = load(p.scenes_json, [])
        for s in scenes: s["video_approved"] = True
        p.scenes_json = dump(scenes); p.stage = "voice"; p.status = "ready_to_generate"; touch(p)
        self.session.add(p); self.session.commit(); self.session.refresh(p)
        return p

    def generate_voice(self, p: Project):
        script = load(p.script_json, {})
        text = script.get("narration", "")
        provider_name = self.config.get("providers", {}).get("voice", "mock")
        per_k = float(self.config.get("provider_options", {}).get("elevenlabs", {}).get("estimated_cost_per_1000_chars", 0.0)) if provider_name == "elevenlabs" else 0.0
        estimated = round(len(text) / 1000.0 * per_k, 4)
        self.budget.assert_allowed(estimated)
        result = self.providers.media("voice").generate(text=text, project_id=p.id, config=self.config)
        actual = float(result.get("cost", estimated if provider_name != "mock" else 0.0) or 0.0)
        self.budget.record(project_id=p.id, provider=provider_name, operation="voice", estimated_cost=estimated, actual_cost=actual)
        p.estimated_cost = float(p.estimated_cost or 0) + estimated
        p.actual_cost = float(p.actual_cost or 0) + actual
        p.voice_json = dump(result); p.stage = "voice"; p.status = "needs_review"; touch(p)
        self.session.add(p); self.session.commit(); self.session.refresh(p)
        return p

    def approve_voice(self, p: Project):
        p.stage = "render"; p.status = "ready_to_generate"; touch(p)
        self.session.add(p); self.session.commit(); self.session.refresh(p)
        return p

    def render(self, p: Project):
        result = self.providers.media("renderer").generate(project_id=p.id)
        p.render_json = dump(result); p.stage = "final"; p.status = "needs_review"; touch(p)
        self.session.add(p); self.session.commit(); self.session.refresh(p)
        return p

    def approve_final(self, p: Project):
        p.stage = "publish"; p.status = "ready_to_publish"; touch(p)
        self.session.add(p); self.session.commit(); self.session.refresh(p)
        return p

    def publish(self, p: Project, metadata: dict):
        result = self.providers.media("publisher").generate(project_id=p.id, metadata=metadata)
        p.publish_json = dump(result); p.stage = "published"; p.status = "published"; touch(p)
        self.session.add(p); self.session.commit(); self.session.refresh(p)
        return p
