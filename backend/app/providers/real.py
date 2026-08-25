"""Live provider adapters.

Vendor-specific settings are read from config/app.yaml and secrets from .env.
Only OpenAI text/research is wired in V1.1; media providers remain explicit placeholders.
"""
from __future__ import annotations
import json
import re
from app.core.config import get_env
from typing import Any
import httpx

from .base import TextProvider, ResearchProvider, MediaProvider


def _extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\\s*|\\s*```$", "", text, flags=re.S)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"(\\[.*\\]|\\{.*\\})", text, re.S)
        if not m:
            raise ValueError("Model did not return valid JSON")
        return json.loads(m.group(1))


class _OpenAIBase:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.key = get_env().openai_api_key
        if not self.key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        opts = config.get("provider_options", {}).get("openai", {})
        self.model = opts.get("model", "gpt-5.6-luna")
        self.base_url = str(opts.get("base_url", "https://api.openai.com/v1")).rstrip("/")
        self.timeout = float(opts.get("timeout_seconds", 90))
        self.max_output_tokens = int(opts.get("max_output_tokens", 3500))

    def _json(self, system: str, user: str):
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system + "\\nReturn only valid JSON matching the requested structure."},
                {"role": "user", "content": user},
            ],
            "max_output_tokens": self.max_output_tokens,
        }
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{self.base_url}/responses", headers={
                "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"
            }, json=payload)
            r.raise_for_status()
            data = r.json()
        chunks=[]
        for item in data.get("output", []):
            if item.get("type") == "message":
                for c in item.get("content", []):
                    if c.get("type") == "output_text": chunks.append(c.get("text", ""))
        return _extract_json("".join(chunks)), data.get("usage", {})


class OpenAITextProvider(_OpenAIBase, TextProvider):
    def generate_ideas(self, *, count: int, category: str | None, config: dict[str, Any]):
        system = config.get("prompts", {}).get("idea_system", "Generate POV YouTube ideas.")
        cats = config.get("content", {}).get("categories", [])
        user = f"Generate {count} ideas. Category filter: {category or 'any of '+', '.join(cats)}. JSON: {{\"ideas\":[{{\"title\":str,\"category\":str,\"premise\":str,\"viral_reason\":str}}]}}"
        data, usage = self._json(system, user)
        rows = data.get("ideas", data if isinstance(data, list) else [])
        return rows[:count]

    def write_script(self, *, title: str, premise: str, research: dict[str, Any], config: dict[str, Any]):
        system = config.get("prompts", {}).get("script_system", "Write a POV short.")
        user = f"Title: {title}\\nPremise: {premise}\\nResearch: {json.dumps(research)}\\nReturn JSON with hook, narration, segments (start,end,narration,visual), title, description, tags."
        data, usage = self._json(system, user)
        # Economy default is six 5-second scenes / 30 seconds total.
        # Normalize model-provided timestamps so the UI and downstream scene timing
        # cannot drift past the configured runtime.
        vd = config.get("video_defaults", {})
        scene_count = int(vd.get("scene_count", 6))
        clip_seconds = int(vd.get("clip_seconds", 5))
        duration_seconds = int(vd.get("duration_seconds", scene_count * clip_seconds))
        segments = list(data.get("segments") or [])[:scene_count]
        for i, seg in enumerate(segments):
            seg["start"] = i * clip_seconds
            seg["end"] = min((i + 1) * clip_seconds, duration_seconds)
        data["segments"] = segments
        return data

    def storyboard(self, *, script: dict[str, Any], config: dict[str, Any]):
        system = config.get("prompts", {}).get("scene_system", "Create storyboard prompts.")
        continuity = config.get("content", {}).get("continuity_rules", [])
        n = config.get("video_defaults", {}).get("scene_count", 6)
        user = f"Script: {json.dumps(script)}\\nContinuity rules: {json.dumps(continuity)}\\nCreate exactly {n} scenes. JSON: {{\"scenes\":[{{\"index\":0,\"narration\":str,\"prompt\":str}}]}}"
        data, usage = self._json(system, user)
        scenes = data.get("scenes", [])[:n]
        for i, scene in enumerate(scenes):
            scene["index"] = i
            scene["approved"] = False
            scene["regenerations"] = 0
            scene.setdefault("preview_url", "")
        return scenes


class OpenAIResearchProvider(_OpenAIBase, ResearchProvider):
    def research(self, *, title: str, category: str, premise: str, config: dict[str, Any]):
        system = config.get("prompts", {}).get("research_system", "Create a factual research pack.")
        user = f"Title: {title}\\nCategory: {category}\\nPremise: {premise}\\nJSON: {{\"summary\":str,\"facts\":[str],\"uncertainties\":[str],\"risk_notes\":[str],\"verification_queries\":[str]}}"
        data, usage = self._json(system, user)
        data["note"] = "Model-generated research; verify time-sensitive or disputed factual claims before publishing."
        return data


class GenericRealMediaProvider(MediaProvider):
    def __init__(self, kind: str, provider: str, config: dict[str, Any]):
        self.kind = kind
        self.provider = provider
        self.config = config

    @staticmethod
    def _runway_prompt(prompt: str, limit: int = 950) -> str:
        """Keep Runway promptText safely below the API's 1000 UTF-16-unit limit."""
        text = " ".join(str(prompt or "").split())
        if not text:
            return "Cinematic first-person POV scene."
        out = []
        units = 0
        for ch in text:
            u = len(ch.encode("utf-16-le")) // 2
            if units + u > limit:
                break
            out.append(ch)
            units += u
        clipped = "".join(out).rstrip()
        if len(clipped) < len(text):
            clipped = clipped.rsplit(" ", 1)[0].rstrip(" ,;:-") + "."
        return clipped

    @staticmethod
    def _runway_error(endpoint: str, response: httpx.Response) -> RuntimeError:
        try:
            body = response.json()
            detail = json.dumps(body, ensure_ascii=False)
        except Exception:
            detail = (response.text or "").strip()
        if len(detail) > 1200:
            detail = detail[:1200] + "…"
        return RuntimeError(
            f"Runway {endpoint} failed with HTTP {response.status_code}: "
            f"{detail or response.reason_phrase}"
        )

    def _runway(self, *, prompt: str, scene_index: int, project_id: int, motion: bool = True):
        import time
        key = get_env().runway_api_key
        if not key:
            raise RuntimeError("RUNWAY_API_KEY is not configured")
        opts = self.config.get("provider_options", {}).get("runway", {})
        headers = {"Authorization": f"Bearer {key}", "X-Runway-Version": "2024-11-06", "Content-Type": "application/json"}
        base = "https://api.dev.runwayml.com/v1"
        ratio = "720:1280"
        image_model = opts.get("image_model", "gen4_image_turbo")
        video_model = "gen4_turbo" if opts.get("production_mode") == "economy_hybrid" else opts.get("model", "gen4_turbo")
        duration = int(opts.get("clip_seconds", 5))
        timeout = float(opts.get("max_poll_minutes", 10)) * 60
        safe_prompt = self._runway_prompt(prompt)

        def checked(response: httpx.Response, endpoint: str):
            if response.is_error:
                raise self._runway_error(endpoint, response)
            try:
                return response.json()
            except Exception as exc:
                raise RuntimeError(f"Runway {endpoint} returned invalid JSON: {response.text[:500]}") from exc

        def wait(task_id: str, task_kind: str):
            deadline = time.time() + timeout
            with httpx.Client(timeout=60) as client:
                while time.time() < deadline:
                    data = checked(client.get(f"{base}/tasks/{task_id}", headers=headers), f"task status ({task_kind})")
                    status = data.get("status")
                    if status == "SUCCEEDED":
                        if not data.get("output"):
                            raise RuntimeError(f"Runway {task_kind} task succeeded but returned no output: {json.dumps(data)[:800]}")
                        return data
                    if status in ("FAILED", "CANCELED"):
                        failure = data.get("failure") or data.get("failureCode") or data
                        raise RuntimeError(f"Runway {task_kind} task {status}: {failure}")
                    time.sleep(float(opts.get("polling_interval_seconds", 5)))
            raise TimeoutError(f"Runway {task_kind} generation timed out after {int(timeout)} seconds")

        with httpx.Client(timeout=90) as client:
            image_data = checked(
                client.post(
                    f"{base}/text_to_image",
                    headers=headers,
                    json={"model": image_model, "promptText": safe_prompt, "ratio": ratio},
                ),
                "text_to_image",
            )
            image_task = wait(image_data["id"], "image")
            image_url = image_task["output"][0]
            image_cost = float(opts.get("image_cost", 0.02))
            if not motion:
                return {"provider":"runway","status":"succeeded","asset_type":"animated_still","image_url":image_url,"url":image_url,"cost":image_cost,"scene_index":scene_index,"project_id":project_id}

            video_data = checked(
                client.post(
                    f"{base}/image_to_video",
                    headers=headers,
                    json={"model": video_model, "promptImage": image_url, "promptText": safe_prompt, "duration": duration, "ratio": ratio},
                ),
                "image_to_video",
            )
            video_task = wait(video_data["id"], "video")
            video_url = video_task["output"][0]
            cost = image_cost + duration * float(opts.get("estimated_cost_per_second", 0.05))
            return {"provider":"runway","status":"succeeded","asset_type":"video","image_url":image_url,"url":video_url,"cost":round(cost,4),"scene_index":scene_index,"project_id":project_id}

    def generate(self, **kwargs) -> dict[str, Any]:
        if self.kind == "video" and self.provider == "runway":
            return self._runway(**kwargs)
        raise NotImplementedError(
            f"Live adapter for {self.kind} provider '{self.provider}' is not wired yet. "
            "Credentials belong in environment variables and behavior/model settings belong in config/app.yaml."
        )
