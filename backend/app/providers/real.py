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

    def generate(self, **kwargs) -> dict[str, Any]:
        raise NotImplementedError(
            f"Live adapter for {self.kind} provider '{self.provider}' is not wired yet. "
            "Credentials belong in .env and all behavior/model settings belong in config/app.yaml."
        )
