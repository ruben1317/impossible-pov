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
        
    def revise_storyboard_scene(
        self,
        *,
        scene: dict[str, Any],
        instructions: str,
        script: dict[str, Any],
        config: dict[str, Any],
    ):
        system = config.get(
            "prompts",
            {},
        ).get(
            "scene_system",
            "Create storyboard prompts.",
        )

        continuity = (
            config.get("content", {})
            .get("continuity_rules", [])
        )

        original_index = int(
            scene.get("index", 0)
        )

        original_narration = str(
            scene.get("narration", "")
        )

        revision_context = {
            "scene_to_revise": scene,
            "revision_instructions": instructions,
            "full_script": script,
            "continuity_rules": continuity,
            "requirements": [
                "Revise ONLY the supplied storyboard scene.",
                "Do not create or return any other storyboard scenes.",
                "Follow the user's revision instructions precisely.",
                "Preserve the original narration unless the user explicitly asks to change the narration.",
                "Preserve first-person POV.",
                "Preserve visual continuity with the surrounding story.",
                "Preserve recurring hands, sleeves, clothing, lighting, environment, scale, and camera perspective when applicable.",
                "The prompt must be optimized for a vertical 9:16 cinematic AI-generated video.",
                "Make spatial relationships physically understandable from the first-person camera position.",
                "Avoid impossible camera geometry or describing objects behind the viewer as visible in front of the camera.",
                "Avoid duplicated anatomy, duplicated limbs, duplicated teeth, malformed creatures, or contradictory physical descriptions.",
                "Avoid readable AI-generated text, signs, captions, or lettering unless explicitly requested.",
                "Keep the revised scene visually achievable by an AI image/video generation model.",
            ],
        }

        user = (
            "Revise exactly one storyboard scene.\n\n"
            f"{json.dumps(revision_context, ensure_ascii=False)}\n\n"
            "Return JSON using exactly this structure:\n"
            '{"scene":{"narration":str,"prompt":str}}'
        )

        data, usage = self._json(
            system,
            user,
        )

        revised = data.get(
            "scene",
            data if isinstance(data, dict) else {},
        )

        if not isinstance(revised, dict):
            raise RuntimeError(
                "Storyboard scene revision returned invalid data"
            )

        prompt = str(
            revised.get("prompt", "")
        ).strip()

        if not prompt:
            raise RuntimeError(
                "Storyboard scene revision returned an empty prompt"
            )

        narration = str(
            revised.get(
                "narration",
                original_narration,
            )
        ).strip()

        if not narration:
            narration = original_narration

        return {
            **scene,
            "index": original_index,
            "narration": narration,
            "prompt": prompt,
            "approved": False,
            "notes": "",
            "regenerations": int(
                scene.get("regenerations", 0)
            ) + 1,
            "preview_url": "",
        }


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
            clipped = (
                clipped
                .rsplit(" ", 1)[0]
                .rstrip(" ,;:-")
                + "."
            )

        return clipped

    @staticmethod
    def _runway_error(
        endpoint: str,
        response: httpx.Response,
    ) -> RuntimeError:
        try:
            body = response.json()
            detail = json.dumps(
                body,
                ensure_ascii=False,
            )
        except Exception:
            detail = (
                response.text or ""
            ).strip()

        if len(detail) > 1200:
            detail = detail[:1200] + "…"

        return RuntimeError(
            f"Runway {endpoint} failed with HTTP "
            f"{response.status_code}: "
            f"{detail or response.reason_phrase}"
        )

    def _runway(
        self,
        *,
        prompt: str,
        scene_index: int,
        project_id: int,
        motion: bool = True,
    ):
        import time

        key = get_env().runway_api_key

        if not key:
            raise RuntimeError(
                "RUNWAY_API_KEY is not configured"
            )

        opts = (
            self.config
            .get("provider_options", {})
            .get("runway", {})
        )

        headers = {
            "Authorization": f"Bearer {key}",
            "X-Runway-Version": "2024-11-06",
            "Content-Type": "application/json",
        }

        base = "https://api.dev.runwayml.com/v1"
        ratio = "720:1280"

        image_model = opts.get(
            "image_model",
            "gen4_image_turbo",
        )

        video_model = (
            "gen4_turbo"
            if opts.get("production_mode")
            == "economy_hybrid"
            else opts.get(
                "model",
                "gen4_turbo",
            )
        )

        duration = int(
            opts.get(
                "clip_seconds",
                5,
            )
        )

        timeout = (
            float(
                opts.get(
                    "max_poll_minutes",
                    10,
                )
            )
            * 60
        )

        safe_prompt = self._runway_prompt(
            prompt
        )

        def checked(
            response: httpx.Response,
            endpoint: str,
        ):
            if response.is_error:
                raise self._runway_error(
                    endpoint,
                    response,
                )

            try:
                return response.json()
            except Exception as exc:
                raise RuntimeError(
                    f"Runway {endpoint} returned "
                    f"invalid JSON: "
                    f"{response.text[:500]}"
                ) from exc

        def wait(
            task_id: str,
            task_kind: str,
        ):
            deadline = time.time() + timeout

            with httpx.Client(
                timeout=60
            ) as client:
                while time.time() < deadline:
                    data = checked(
                        client.get(
                            f"{base}/tasks/{task_id}",
                            headers=headers,
                        ),
                        f"task status ({task_kind})",
                    )

                    status = data.get("status")

                    if status == "SUCCEEDED":
                        if not data.get("output"):
                            raise RuntimeError(
                                f"Runway {task_kind} task "
                                f"succeeded but returned no output: "
                                f"{json.dumps(data)[:800]}"
                            )

                        return data

                    if status in (
                        "FAILED",
                        "CANCELED",
                    ):
                        failure = (
                            data.get("failure")
                            or data.get("failureCode")
                            or data
                        )

                        raise RuntimeError(
                            f"Runway {task_kind} task "
                            f"{status}: {failure}"
                        )

                    time.sleep(
                        float(
                            opts.get(
                                "polling_interval_seconds",
                                5,
                            )
                        )
                    )

            raise TimeoutError(
                f"Runway {task_kind} generation "
                f"timed out after "
                f"{int(timeout)} seconds"
            )

        with httpx.Client(
            timeout=90
        ) as client:
            image_data = checked(
                client.post(
                    f"{base}/text_to_image",
                    headers=headers,
                    json={
                        "model": image_model,
                        "promptText": safe_prompt,
                        "ratio": ratio,
                    },
                ),
                "text_to_image",
            )

            image_task = wait(
                image_data["id"],
                "image",
            )

            image_url = (
                image_task["output"][0]
            )

            image_cost = float(
                opts.get(
                    "image_cost",
                    0.02,
                )
            )

            if not motion:
                return {
                    "provider": "runway",
                    "status": "succeeded",
                    "asset_type": "animated_still",
                    "image_url": image_url,
                    "url": image_url,
                    "cost": image_cost,
                    "scene_index": scene_index,
                    "project_id": project_id,
                }

            video_data = checked(
                client.post(
                    f"{base}/image_to_video",
                    headers=headers,
                    json={
                        "model": video_model,
                        "promptImage": image_url,
                        "promptText": safe_prompt,
                        "duration": duration,
                        "ratio": ratio,
                    },
                ),
                "image_to_video",
            )

            video_task = wait(
                video_data["id"],
                "video",
            )

            video_url = (
                video_task["output"][0]
            )

            cost = (
                image_cost
                + duration
                * float(
                    opts.get(
                        "estimated_cost_per_second",
                        0.05,
                    )
                )
            )

            return {
                "provider": "runway",
                "status": "succeeded",
                "asset_type": "video",
                "image_url": image_url,
                "url": video_url,
                "cost": round(
                    cost,
                    4,
                ),
                "scene_index": scene_index,
                "project_id": project_id,
            }

    def _elevenlabs(
        self,
        *,
        text: str,
        project_id: int,
    ):
        key = get_env().elevenlabs_api_key

        if not key:
            raise RuntimeError(
                "ELEVENLABS_API_KEY is not configured"
            )

        opts = (
            self.config
            .get("provider_options", {})
            .get("elevenlabs", {})
        )

        voice_id = str(
            opts.get(
                "voice_id",
                "",
            )
        ).strip()

        model_id = str(
            opts.get(
                "model_id",
                "eleven_multilingual_v2",
            )
        ).strip()

        output_format = str(
            opts.get(
                "output_format",
                "mp3_44100_128",
            )
        ).strip()

        if not voice_id:
            raise RuntimeError(
                "ElevenLabs voice_id is not configured"
            )

        url = (
            "https://api.elevenlabs.io/v1/"
            f"text-to-speech/{voice_id}"
            f"?output_format={output_format}"
        )

        payload = {
            "text": text,
            "model_id": model_id,
        }

        headers = {
            "xi-api-key": key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        with httpx.Client(
            timeout=90
        ) as client:
            response = client.post(
                url,
                headers=headers,
                json=payload,
            )

        if response.is_error:
            detail = (
                response.text or ""
            ).strip()

            if len(detail) > 1200:
                detail = (
                    detail[:1200]
                    + "…"
                )

            raise RuntimeError(
                "ElevenLabs text-to-speech "
                f"failed with HTTP "
                f"{response.status_code}: "
                f"{detail or response.reason_phrase}"
            )

        import os

        base_path = (
            self.config
            .get("storage", {})
            .get("local", {})
            .get(
                "base_path",
                "./storage",
            )
        )

        voice_dir = os.path.join(
            base_path,
            "projects",
            str(project_id),
            "voice",
        )

        os.makedirs(
            voice_dir,
            exist_ok=True,
        )

        audio_path = os.path.join(
            voice_dir,
            "narration.mp3",
        )

        with open(
            audio_path,
            "wb",
        ) as f:
            f.write(
                response.content
            )

        per_k = float(
            opts.get(
                "estimated_cost_per_1000_chars",
                0.0,
            )
        )

        cost = round(
            len(text)
            / 1000.0
            * per_k,
            4,
        )

        return {
            "provider": "elevenlabs",
            "status": "succeeded",
            "path": audio_path,
            "cost": cost,
            "project_id": project_id,
        }

    def _azure(
        self,
        *,
        text: str,
        project_id: int,
    ):
        import os

        env = get_env()

        key = env.azure_speech_key
        region = env.azure_speech_region

        if not key:
            raise RuntimeError(
                "AZURE_SPEECH_KEY is not configured"
            )

        if not region:
            raise RuntimeError(
                "AZURE_SPEECH_REGION is not configured"
            )

        opts = (
            self.config
            .get("provider_options", {})
            .get("azure", {})
        )

        voice_name = str(
            opts.get(
                "voice_name",
                "en-US-AndrewMultilingualNeural",
            )
        ).strip()

        rate = str(
            opts.get(
                "rate",
                "0%",
            )
        ).strip()

        pitch = str(
            opts.get(
                "pitch",
                "0%",
            )
        ).strip()

        endpoint = (
            f"https://{region}.tts.speech.microsoft.com/"
            "cognitiveservices/v1"
        )

        escaped_text = (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

        ssml = (
            "<speak version='1.0' "
            "xmlns='http://www.w3.org/2001/10/synthesis' "
            "xmlns:mstts='https://www.w3.org/2001/mstts' "
            "xml:lang='en-US'>"
            f"<voice name='{voice_name}'>"
            "<mstts:express-as "
            "style='terrified' "
            "styledegree='1.25'>"
            f"<prosody rate='{rate}' pitch='{pitch}'>"
            f"{escaped_text}"
            "</prosody>"
            "</mstts:express-as>"
            "</voice>"
            "</speak>"
        )

        headers = {
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-160kbitrate-mono-mp3",
            "User-Agent": "impossible-pov",
        }

        with httpx.Client(
            timeout=90
        ) as client:
            response = client.post(
                endpoint,
                headers=headers,
                content=ssml.encode("utf-8"),
            )

        if response.is_error:
            detail = (
                response.text or ""
            ).strip()

            if len(detail) > 1200:
                detail = (
                    detail[:1200]
                    + "…"
                )

            raise RuntimeError(
                "Azure text-to-speech "
                f"failed with HTTP "
                f"{response.status_code}: "
                f"{detail or response.reason_phrase}"
            )

        base_path = (
            self.config
            .get("storage", {})
            .get("local", {})
            .get(
                "base_path",
                "./storage",
            )
        )

        voice_dir = os.path.join(
            base_path,
            "projects",
            str(project_id),
            "voice",
        )

        os.makedirs(
            voice_dir,
            exist_ok=True,
        )

        audio_path = os.path.join(
            voice_dir,
            "narration.mp3",
        )

        with open(
            audio_path,
            "wb",
        ) as f:
            f.write(
                response.content
            )

        return {
            "provider": "azure",
            "status": "succeeded",
            "path": audio_path,
            "cost": 0.0,
            "project_id": project_id,
            "voice_name": voice_name,
        }
        
    def _ffmpeg(
        self,
        *,
        project_id: int,
        scenes: list,
        voice: dict,
    ):
        import os
        import subprocess

        opts = (
            self.config
            .get("provider_options", {})
            .get("ffmpeg", {})
        )

        vd = self.config.get(
            "video_defaults",
            {},
        )

        binary = str(
            opts.get(
                "binary",
                "ffmpeg",
            )
        )

        codec = str(
            opts.get(
                "codec",
                "libx264",
            )
        )

        audio_codec = str(
            opts.get(
                "audio_codec",
                "aac",
            )
        )

        preset = str(
            opts.get(
                "preset",
                "medium",
            )
        )

        crf = str(
            opts.get(
                "crf",
                18,
            )
        )

        width = int(
            vd.get(
                "width",
                1080,
            )
        )

        height = int(
            vd.get(
                "height",
                1920,
            )
        )

        fps = int(
            vd.get(
                "fps",
                30,
            )
        )

        clip_seconds = float(
            vd.get(
                "clip_seconds",
                5,
            )
        )

        base_path = (
            self.config
            .get("storage", {})
            .get("local", {})
            .get(
                "base_path",
                "./storage",
            )
        )

        project_dir = os.path.join(
            base_path,
            "projects",
            str(project_id),
        )

        render_dir = os.path.join(
            project_dir,
            "render",
        )

        scene_dir = os.path.join(
            project_dir,
            "render_scenes",
        )

        os.makedirs(
            render_dir,
            exist_ok=True,
        )

        os.makedirs(
            scene_dir,
            exist_ok=True,
        )

        voice_path = str(
            voice.get(
                "path",
                "",
            )
        ).strip()

        if (
            not voice_path
            or not os.path.exists(
                voice_path
            )
        ):
            raise RuntimeError(
                f"Narration file not found: "
                f"{voice_path}"
            )

        normalized_clips = []

        with httpx.Client(
            timeout=120,
            follow_redirects=True,
        ) as client:
            for i, scene in enumerate(
                scenes
            ):
                video = (
                    scene.get("video")
                    or {}
                )

                source_url = str(
                    video.get(
                        "url",
                        "",
                    )
                ).strip()

                if not source_url:
                    raise RuntimeError(
                        f"Scene {i + 1} has "
                        f"no generated media URL"
                    )

                production_type = (
                    scene.get(
                        "production_type",
                        "video",
                    )
                )

                ext = (
                    ".mp4"
                    if production_type
                    == "video"
                    else ".jpg"
                )

                source_path = os.path.join(
                    scene_dir,
                    f"source_{i:02d}{ext}",
                )

                response = client.get(
                    source_url
                )

                response.raise_for_status()

                with open(
                    source_path,
                    "wb",
                ) as f:
                    f.write(
                        response.content
                    )

                clip_path = os.path.join(
                    scene_dir,
                    f"clip_{i:02d}.mp4",
                )

                vf = (
                    f"scale={width}:{height}:"
                    "force_original_aspect_ratio="
                    "increase,"
                    f"crop={width}:{height},"
                    f"fps={fps},"
                    "setsar=1"
                )

                if production_type == "video":
                    command = [
                        binary,
                        "-y",
                        "-i",
                        source_path,
                        "-t",
                        str(
                            clip_seconds
                        ),
                        "-vf",
                        vf,
                        "-an",
                        "-c:v",
                        codec,
                        "-preset",
                        preset,
                        "-crf",
                        crf,
                        "-pix_fmt",
                        "yuv420p",
                        clip_path,
                    ]

                else:
                    command = [
                        binary,
                        "-y",
                        "-loop",
                        "1",
                        "-i",
                        source_path,
                        "-t",
                        str(
                            clip_seconds
                        ),
                        "-vf",
                        vf,
                        "-an",
                        "-c:v",
                        codec,
                        "-preset",
                        preset,
                        "-crf",
                        crf,
                        "-pix_fmt",
                        "yuv420p",
                        clip_path,
                    ]

                proc = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                )

                if proc.returncode != 0:
                    raise RuntimeError(
                        "FFmpeg failed preparing "
                        f"scene {i + 1}: "
                        f"{proc.stderr[-2000:]}"
                    )

                normalized_clips.append(
                    clip_path
                )

        concat_file = os.path.join(
            scene_dir,
            "concat.txt",
        )

        with open(
            concat_file,
            "w",
            encoding="utf-8",
        ) as f:
            for clip_path in normalized_clips:
                safe_path = (
                    clip_path.replace(
                        "'",
                        "'\\''",
                    )
                )

                f.write(
                    f"file '{safe_path}'\n"
                )

        silent_video = os.path.join(
            render_dir,
            "silent.mp4",
        )

        concat_command = [
            binary,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file,
            "-c",
            "copy",
            silent_video,
        ]

        proc = subprocess.run(
            concat_command,
            capture_output=True,
            text=True,
        )

        if proc.returncode != 0:
            raise RuntimeError(
                "FFmpeg scene concatenation "
                f"failed: "
                f"{proc.stderr[-2000:]}"
            )

        final_path = os.path.join(
            render_dir,
            "final.mp4",
        )

        final_command = [
            binary,
            "-y",
            "-i",
            silent_video,
            "-i",
            voice_path,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            audio_codec,
            "-shortest",
            "-movflags",
            "+faststart",
            final_path,
        ]

        proc = subprocess.run(
            final_command,
            capture_output=True,
            text=True,
        )

        if proc.returncode != 0:
            raise RuntimeError(
                "FFmpeg final render failed: "
                f"{proc.stderr[-2000:]}"
            )

        return {
            "provider": "ffmpeg",
            "status": "succeeded",
            "path": final_path,
            "project_id": project_id,
            "width": width,
            "height": height,
            "fps": fps,
        }

    def generate(
        self,
        **kwargs,
    ) -> dict[str, Any]:
        if (
            self.kind == "video"
            and self.provider == "runway"
        ):
            return self._runway(
                **kwargs
            )

        if (
            self.kind == "voice"
            and self.provider == "elevenlabs"
        ):
            return self._elevenlabs(
                **kwargs
            )

        if (
            self.kind == "voice"
            and self.provider == "azure"
        ):
            return self._azure(
                **kwargs
            )
            
        if (
            self.kind == "renderer"
            and self.provider == "ffmpeg"
        ):
            return self._ffmpeg(
                **kwargs
            )

        raise NotImplementedError(
            f"Live adapter for {self.kind} "
            f"provider '{self.provider}' "
            "is not wired yet. "
            "Credentials belong in environment "
            "variables and behavior/model settings "
            "belong in config/app.yaml."
        )
