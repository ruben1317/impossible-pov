from __future__ import annotations
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.config import get_config
from app.core.db import get_session
from app.models.project import Project
from app.models.idea_history import IdeaHistory
from app.models.schemas import IdeaRequest, ProjectCreate, SceneDecision, SceneVideoDecision, PublishRequest, RuntimeSettingsUpdate
from app.services.workflow import WorkflowService
from app.services.budget import BudgetService, BudgetExceeded
from app.providers.registry import ProviderRegistry
from app.core.runtime_config import get_effective_config, get_overrides, save_overrides

router = APIRouter(prefix="/api")


def serialize(p: Project):
    def j(v, fallback):
        try: return json.loads(v)
        except Exception: return fallback
    return {
        "id": p.id, "title": p.title, "category": p.category, "premise": p.premise,
        "stage": p.stage, "status": p.status,
        "research": j(p.research_json, {}), "script": j(p.script_json, {}),
        "storyboard": j(p.storyboard_json, []), "scenes": j(p.scenes_json, []),
        "voice": j(p.voice_json, {}), "render": j(p.render_json, {}),
        "publish": j(p.publish_json, {}), "estimated_cost": p.estimated_cost,
        "actual_cost": p.actual_cost, "created_at": p.created_at, "updated_at": p.updated_at,
    }



def serialize_idea_history(row: IdeaHistory):
    return {
        "id": row.id, "title": row.title, "category": row.category, "premise": row.premise,
        "viral_reason": row.viral_reason, "estimated_cost": row.estimated_cost,
        "used": row.used, "project_id": row.project_id, "created_at": row.created_at,
    }

def svc(session): return WorkflowService(session, get_effective_config(session))

def project_or_404(session, pid):
    p = session.get(Project, pid)
    if not p: raise HTTPException(404, "Project not found")
    return p

@router.get("/health")
def health(): return {"ok": True}

@router.get("/config/public")
def public_config(session: Session = Depends(get_session)):
    cfg = get_effective_config(session)
    return {
        "channel": cfg.get("channel", {}), "video_defaults": cfg.get("video_defaults", {}),
        "content": cfg.get("content", {}), "budgets": cfg.get("budgets", {}),
        "providers": cfg.get("providers", {}), "provider_options": cfg.get("provider_options", {}),
        "storage": cfg.get("storage", {}), "captions": cfg.get("captions", {}), "branding": cfg.get("branding", {})
    }


@router.get("/providers/status")
def provider_status(session: Session = Depends(get_session)):
    return ProviderRegistry(get_effective_config(session)).statuses()


@router.get("/budget/status")
def budget_status(session: Session = Depends(get_session)):
    cfg = get_effective_config(session)
    service = BudgetService(session, cfg)
    cap = float(cfg.get("budgets", {}).get("monthly_cap", 0) or 0)
    spent = service.month_spend()
    return {"spent": spent, "cap": cap, "remaining": max(0, round(cap-spent, 4)), "currency": cfg.get("budgets", {}).get("currency", "USD")}


@router.get("/settings/runtime")
def runtime_settings(session: Session = Depends(get_session)):
    return {"effective": get_effective_config(session), "overrides": get_overrides(session)}


@router.put("/settings/runtime")
def update_runtime_settings(req: RuntimeSettingsUpdate, session: Session = Depends(get_session)):
    current = get_overrides(session)
    def put(path, value):
        if value is None: return
        node=current
        keys=path.split(".")
        for k in keys[:-1]: node=node.setdefault(k,{})
        node[keys[-1]]=value
    put("budgets.monthly_cap", req.monthly_cap)
    put("budgets.target_cost_per_video", req.target_cost_per_video)
    put("budgets.hard_stop_on_cap", req.hard_stop_on_cap)
    put("video_defaults.duration_seconds", req.duration_seconds)
    put("video_defaults.scene_count", req.scene_count)
    put("video_defaults.clip_seconds", req.clip_seconds)
    put("content.idea_count", req.idea_count)
    put("provider_options.youtube.privacy_status", req.privacy_status)
    put("providers.text", req.text_provider)
    put("providers.research", req.research_provider)
    put("providers.video", req.video_provider)
    put("providers.voice", req.voice_provider)
    put("providers.renderer", req.renderer_provider)
    put("providers.publisher", req.publisher_provider)
    put("provider_options.openai.model", req.openai_model)
    put("provider_options.runway.model", req.runway_model)
    put("provider_options.elevenlabs.voice_id", req.elevenlabs_voice_id)
    put("provider_options.elevenlabs.model_id", req.elevenlabs_model_id)
    effective=save_overrides(session,current)
    return {"ok": True, "effective": effective, "overrides": current}


@router.post("/ideas")
def ideas(req: IdeaRequest, session: Session = Depends(get_session)):
    return svc(session).generate_ideas(req.count, req.category)


@router.get("/ideas/history")
def idea_history(session: Session = Depends(get_session)):
    rows = session.exec(select(IdeaHistory).order_by(IdeaHistory.created_at.desc())).all()
    return [serialize_idea_history(x) for x in rows]


@router.post("/ideas/history/{idea_id}/use")
def use_history_idea(idea_id: int, session: Session = Depends(get_session)):
    idea = session.get(IdeaHistory, idea_id)
    if not idea:
        raise HTTPException(404, "Idea not found")
    project = svc(session).create_project(idea.title, idea.category, idea.premise)
    idea.used = True
    idea.project_id = project.id
    session.add(idea); session.commit(); session.refresh(idea)
    return serialize(project)

@router.get("/projects")
def projects(session: Session = Depends(get_session)):
    rows = session.exec(select(Project).order_by(Project.updated_at.desc())).all()
    return [serialize(x) for x in rows]

@router.post("/projects")
def create(req: ProjectCreate, session: Session = Depends(get_session)):
    return serialize(svc(session).create_project(req.title, req.category, req.premise))

@router.get("/projects/{pid}")
def get_project(pid: int, session: Session = Depends(get_session)):
    return serialize(project_or_404(session, pid))

@router.post("/projects/{pid}/approve-idea")
def approve_idea(pid: int, session: Session = Depends(get_session)):
    return serialize(svc(session).approve_idea(project_or_404(session, pid)))

@router.post("/projects/{pid}/generate-script")
def generate_script(pid: int, session: Session = Depends(get_session)):
    return serialize(svc(session).generate_script(project_or_404(session, pid)))

@router.post("/projects/{pid}/approve-script")
def approve_script(pid: int, session: Session = Depends(get_session)):
    return serialize(svc(session).approve_script(project_or_404(session, pid)))

@router.post("/projects/{pid}/generate-storyboard")
def generate_storyboard(pid: int, session: Session = Depends(get_session)):
    return serialize(svc(session).generate_storyboard(project_or_404(session, pid)))

@router.post("/projects/{pid}/scene-decision")
def scene_decision(pid: int, req: SceneDecision, session: Session = Depends(get_session)):
    try: return serialize(svc(session).set_scene_approval(project_or_404(session, pid), req.scene_index, req.approved, req.notes))
    except ValueError as e: raise HTTPException(400, str(e))

@router.post("/projects/{pid}/generate-video-scenes")
def generate_video(pid: int, session: Session = Depends(get_session)):
    try: return serialize(svc(session).generate_video_scenes(project_or_404(session, pid)))
    except (ValueError, BudgetExceeded) as e: raise HTTPException(400, str(e))

@router.post("/projects/{pid}/regenerate-video-scene")
def regenerate_video_scene(pid: int, req: SceneVideoDecision, session: Session = Depends(get_session)):
    try: return serialize(svc(session).regenerate_video_scene(project_or_404(session, pid), req.scene_index))
    except (ValueError, BudgetExceeded) as e: raise HTTPException(400, str(e))

@router.post("/projects/{pid}/approve-video-scene")
def approve_video_scene(pid: int, req: SceneVideoDecision, session: Session = Depends(get_session)):
    try: return serialize(svc(session).approve_video_scene(project_or_404(session, pid), req.scene_index))
    except ValueError as e: raise HTTPException(400, str(e))

@router.post("/projects/{pid}/approve-video-scenes")
def approve_video(pid: int, session: Session = Depends(get_session)):
    return serialize(svc(session).approve_all_video_scenes(project_or_404(session, pid)))

@router.post("/projects/{pid}/generate-voice")
def generate_voice(pid: int, session: Session = Depends(get_session)):
    try: return serialize(svc(session).generate_voice(project_or_404(session, pid)))
    except BudgetExceeded as e: raise HTTPException(400, str(e))

@router.post("/projects/{pid}/approve-voice")
def approve_voice(pid: int, session: Session = Depends(get_session)):
    return serialize(svc(session).approve_voice(project_or_404(session, pid)))

@router.post("/projects/{pid}/render")
def render(pid: int, session: Session = Depends(get_session)):
    return serialize(svc(session).render(project_or_404(session, pid)))

@router.post("/projects/{pid}/approve-final")
def approve_final(pid: int, session: Session = Depends(get_session)):
    return serialize(svc(session).approve_final(project_or_404(session, pid)))

@router.post("/projects/{pid}/publish")
def publish(pid: int, req: PublishRequest, session: Session = Depends(get_session)):
    p = project_or_404(session, pid)
    script = json.loads(p.script_json or "{}")
    metadata = {
        "title": req.title or script.get("title") or p.title,
        "description": req.description or script.get("description") or "",
        "privacy_status": req.privacy_status or get_effective_config(session).get("provider_options", {}).get("youtube", {}).get("privacy_status", "private"),
        "scheduled_at": req.scheduled_at,
        "altered_content_disclosure": get_effective_config(session).get("channel", {}).get("disclosure_altered_content", True),
    }
    return serialize(svc(session).publish(p, metadata))
