from __future__ import annotations
import json
from datetime import datetime, timezone

from sqlmodel import Session

from app.models.project import Project
from app.models.idea_history import IdeaHistory
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
        rows = self.providers.text().generate_ideas(count=n, category=category, config=self.config)
        # Keep every idea the user has already been shown so it can be revisited later
        # without paying to generate the same batch again.
        for row in rows:
            self.session.add(IdeaHistory(
                title=str(row.get("title", "Untitled POV")),
                category=str(row.get("category", category or "impossible")),
                premise=str(row.get("premise", "")),
                viral_reason=str(row.get("viral_reason", "")),
                estimated_cost=float(row.get("estimated_cost", 0.0) or 0.0),
            ))
        self.session.commit()
        return rows

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

    def regenerate_script(self, p: Project):
        research = load(p.research_json, {})
        script = self.providers.text().write_script(
            title=p.title,
            premise=p.premise,
            research=research,
            config=self.config,
        )

        p.script_json = dump(script)

        # A new script invalidates anything downstream.
        p.storyboard_json = "[]"
        p.scenes_json = "[]"
        p.voice_json = "{}"
        p.render_json = "{}"
        p.publish_json = "{}"

        p.stage = "script"
        p.status = "needs_review"
        touch(p)

        self.session.add(p)
        self.session.commit()
        self.session.refresh(p)
        return p

    def revise_script(self, p: Project, instructions: str):
        instructions = (instructions or "").strip()

        if not instructions:
            raise ValueError("Revision instructions are required")

        current_script = load(p.script_json, {})
        if not current_script:
            raise ValueError("Generate a script before editing it")

        research = load(p.research_json, {})

        revision_context = {
            "existing_script": current_script,
            "revision_instructions": instructions,
            "requirements": [
                "Return the complete revised script, not only a list of edits.",
                "Keep the configured total runtime and scene count.",
                "Preserve good material unless the instructions ask to change it.",
                "Avoid readable AI-generated text in visual descriptions unless specifically requested.",
                "Keep the video first-person POV and optimized for YouTube Shorts and TikTok retention.",
            ],
        }

        revision_premise = (
            f"{p.premise}\n\n"
            "REVISION TASK: Revise the existing script using the instructions below. "
            "Do not ignore the existing script. "
            f"{json.dumps(revision_context, ensure_ascii=False)}"
        )

        script = self.providers.text().write_script(
            title=p.title,
            premise=revision_premise,
            research=research,
            config=self.config,
        )

        p.script_json = dump(script)

        # Script edits invalidate downstream creative work.
        p.storyboard_json = "[]"
        p.scenes_json = "[]"
        p.voice_json = "{}"
        p.render_json = "{}"
        p.publish_json = "{}"

        p.stage = "script"
        p.status = "needs_review"
        touch(p)

        self.session.add(p)
        self.session.commit()
        self.session.refresh(p)
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
            p.stage = "voice"
        touch(p); self.session.add(p); self.session.commit(); self.session.refresh(p)
        return p

    def _scene_plan(self, board):
        opts = self.config.get("provider_options", {}).get("runway", {})
        motion = set(int(x) for x in opts.get("motion_scene_indexes", [0, 2, 4]))
        return [(scene, int(scene.get("index", i)) in motion) for i, scene in enumerate(board)]

    def _generate_one_video_scene(self, p: Project, scene: dict, motion: bool):
        provider_name = self.config.get("providers", {}).get("video", "mock")
        opts = self.config.get("provider_options", {}).get("runway", {})
        clip_seconds = float(opts.get("clip_seconds", self.config.get("video_defaults", {}).get("clip_seconds", 5)))
        image_cost = float(opts.get("image_cost", 0.02)) if provider_name == "runway" else 0.0
        estimated = image_cost + (clip_seconds * float(opts.get("estimated_cost_per_second", 0.0)) if motion and provider_name == "runway" else 0.0)
        self.budget.assert_allowed(estimated)
        result = self.providers.media("video").generate(prompt=scene["prompt"], scene_index=scene["index"], project_id=p.id, motion=motion)
        actual = float(result.get("cost", estimated if provider_name != "mock" else 0.0) or 0.0)
        self.budget.record(project_id=p.id, provider=provider_name, operation="video_scene" if motion else "scene_image", scene_index=scene["index"], estimated_cost=estimated, actual_cost=actual)
        return result, estimated, actual

    def generate_video_scenes(self, p: Project):
        board = load(p.storyboard_json, [])
        if not board or not all(x.get("approved") for x in board):
            raise ValueError("Approve all storyboard scenes before generating video")
        plan = self._scene_plan(board)
        opts = self.config.get("provider_options", {}).get("runway", {})
        clip = float(opts.get("clip_seconds", 5)); cps=float(opts.get("estimated_cost_per_second",0)); img=float(opts.get("image_cost",0))
        provider_is_runway = self.config.get("providers",{}).get("video") == "runway"
        full_estimate = round(sum(img + (clip*cps if motion else 0) for _, motion in plan), 4) if provider_is_runway else 0
        hard_cap=float(opts.get("hard_video_generation_cap",1.25))
        if full_estimate > hard_cap:
            raise BudgetExceeded(f"Planned scene generation ${full_estimate:.2f} exceeds the ${hard_cap:.2f} economy cap")

        # Resume protection: persist each successful scene immediately. If a later
        # Runway task fails or the browser disconnects, retrying skips completed scenes.
        existing = {int(s.get("index", i)): s for i, s in enumerate(load(p.scenes_json, []))}
        scenes=[]
        pending_estimate = 0.0
        for scene, motion in plan:
            idx = int(scene.get("index", len(scenes)))
            previous = existing.get(idx)
            video = (previous or {}).get("video") or {}
            if video.get("status") == "succeeded" and video.get("url"):
                scenes.append(previous)
            else:
                pending_estimate += img + (clip*cps if motion and provider_is_runway else 0)
        self.budget.assert_allowed(round(pending_estimate, 4))

        completed = {int(s.get("index", i)): s for i, s in enumerate(scenes)}
        for scene, motion in plan:
            idx = int(scene.get("index", 0))
            if idx in completed:
                continue
            result, estimated, actual = self._generate_one_video_scene(p, scene, motion)
            generated = {**scene,"production_type":"video" if motion else "animated_still","video":result,"video_approved":False}
            completed[idx] = generated
            p.estimated_cost = float(p.estimated_cost or 0) + estimated
            p.actual_cost = float(p.actual_cost or 0) + actual
            p.scenes_json = dump([completed[i] for i in sorted(completed)])
            p.stage = "video_scenes"
            p.status = "generating" if len(completed) < len(plan) else "needs_review"
            touch(p)
            self.session.add(p); self.session.commit(); self.session.refresh(p)

        p.scenes_json = dump([completed[i] for i in sorted(completed)])
        p.stage="video_scenes"; p.status="needs_review"; touch(p)
        self.session.add(p); self.session.commit(); self.session.refresh(p); return p

    def approve_video_scene(self, p: Project, idx: int):
        scenes=load(p.scenes_json,[])
        if idx<0 or idx>=len(scenes): raise ValueError("Invalid scene index")
        scenes[idx]["video_approved"]=True; p.scenes_json=dump(scenes); touch(p)
        self.session.add(p); self.session.commit(); self.session.refresh(p); return p

    def regenerate_video_scene(self, p: Project, idx: int):
        scenes=load(p.scenes_json,[])
        if idx<0 or idx>=len(scenes): raise ValueError("Invalid scene index")
        max_regens=int(self.config.get("budgets",{}).get("max_scene_regenerations",2)); count=int(scenes[idx].get("video_regenerations",0))
        if count>=max_regens: raise ValueError(f"Scene regeneration limit reached ({max_regens})")
        motion=scenes[idx].get("production_type")=="video"
        result,estimated,actual=self._generate_one_video_scene(p,scenes[idx],motion)
        scenes[idx]["video"]=result; scenes[idx]["video_approved"]=False; scenes[idx]["video_regenerations"]=count+1
        p.estimated_cost=float(p.estimated_cost or 0)+estimated; p.actual_cost=float(p.actual_cost or 0)+actual; p.scenes_json=dump(scenes); touch(p)
        self.session.add(p); self.session.commit(); self.session.refresh(p); return p

    def approve_all_video_scenes(self, p: Project):
        scenes = load(p.scenes_json, [])
        if not scenes or not all(s.get("video_approved") for s in scenes):
            raise ValueError("Approve every generated scene before continuing")
        p.scenes_json = dump(scenes)
        p.stage = "render"
        p.status = "ready_to_generate"
        touch(p)
        self.session.add(p); self.session.commit(); self.session.refresh(p)
        return p

    def generate_voice(self, p: Project):
        script = load(p.script_json, {})
        text = script.get("narration", "")

        if not text:
            segments = script.get("segments", [])
            text = " ".join(
                str(segment.get("narration", "")).strip()
                for segment in segments
                if segment.get("narration")
            ).strip()

        if not text:
            raise ValueError("No narration found in the approved script")

        provider_name = self.config.get("providers", {}).get("voice", "mock")

        per_k = (
            float(
                self.config.get("provider_options", {})
                .get("elevenlabs", {})
                .get("estimated_cost_per_1000_chars", 0.0)
            )
            if provider_name == "elevenlabs"
            else 0.0
        )

        estimated = round(len(text) / 1000.0 * per_k, 4)
        self.budget.assert_allowed(estimated)

        result = self.providers.media("voice").generate(
            text=text,
            project_id=p.id,
        )

        actual = float(
            result.get(
                "cost",
                estimated if provider_name != "mock" else 0.0,
            )
            or 0.0
        )

        self.budget.record(
            project_id=p.id,
            provider=provider_name,
            operation="voice",
            estimated_cost=estimated,
            actual_cost=actual,
        )

        p.estimated_cost = float(p.estimated_cost or 0) + estimated
        p.actual_cost = float(p.actual_cost or 0) + actual
        p.voice_json = dump(result)
        p.stage = "voice"
        p.status = "needs_review"
        touch(p)

        self.session.add(p)
        self.session.commit()
        self.session.refresh(p)
        return p

    def approve_voice(self, p: Project):
        p.stage = "video_scenes"
        p.status = "ready_to_generate"
        touch(p)
        self.session.add(p)
        self.session.commit()
        self.session.refresh(p)
        return p

    def render(self, p: Project):
        scenes = load(p.scenes_json, [])
        voice = load(p.voice_json, {})

        if not scenes:
            raise ValueError("No generated scenes found")

        if not voice.get("path"):
            raise ValueError("No generated narration found")

        result = self.providers.media("renderer").generate(
            project_id=p.id,
            scenes=scenes,
            voice=voice,
        )
        p.render_json = dump(result)
        p.stage = "final"
        p.status = "needs_review"
        touch(p)

        self.session.add(p)
        self.session.commit()
        self.session.refresh(p)
        return p

    def approve_final(self, p: Project):
        p.stage = "publish"; p.status = "ready_to_publish"; touch(p)
        self.session.add(p); self.session.commit(); self.session.refresh(p)
        return p

    def publish(self, p: Project, metadata: dict):
        requested_platforms = metadata.get(
            "platforms",
            ["youtube", "tiktok"],
        )

        allowed_platforms = {"youtube", "tiktok"}
        platforms = []

        for platform in requested_platforms:
            name = str(platform).lower().strip()

            if name in allowed_platforms and name not in platforms:
                platforms.append(name)

        if not platforms:
            raise ValueError("Select at least one publishing platform")

        existing = load(p.publish_json, {})
        results = existing.get("platforms", {})

        for platform in platforms:
            platform_metadata = {
                **metadata,
                "platform": platform,
            }

            result = self.providers.media("publisher").generate(
                project_id=p.id,
                metadata=platform_metadata,
            )

            results[platform] = result

        p.publish_json = dump({
            "platforms": results,
        })

        youtube_published = bool(results.get("youtube"))
        tiktok_published = bool(results.get("tiktok"))

        if youtube_published and tiktok_published:
            p.stage = "published"
            p.status = "published"
        else:
            p.stage = "publish"
            p.status = "partially_published"

        touch(p)

        self.session.add(p)
        self.session.commit()
        self.session.refresh(p)
        return p
