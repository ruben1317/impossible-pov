from __future__ import annotations
import shutil
from app.core.config import get_env
from .mock import MockTextProvider, MockResearchProvider, MockMediaProvider


class ProviderRegistry:
    def __init__(self, config: dict):
        self.config = config

    def text(self):
        name = self.config.get("providers", {}).get("text", "mock")
        if name == "mock": return MockTextProvider()
        if name == "openai":
            from .real import OpenAITextProvider
            return OpenAITextProvider(self.config)
        raise ValueError(f"Unknown text provider: {name}")

    def research(self):
        name = self.config.get("providers", {}).get("research", "mock")
        if name == "mock": return MockResearchProvider()
        if name == "openai":
            from .real import OpenAIResearchProvider
            return OpenAIResearchProvider(self.config)
        raise ValueError(f"Unknown research provider: {name}")

    def media(self, kind: str):
        name = self.config.get("providers", {}).get(kind, "mock")
        if name == "mock": return MockMediaProvider(kind)
        from .real import GenericRealMediaProvider
        return GenericRealMediaProvider(kind=kind, provider=name, config=self.config)

    def statuses(self):
        providers = self.config.get("providers", {})
        checks = {
            "text": (providers.get("text", "mock"), "OPENAI_API_KEY" if providers.get("text") == "openai" else None),
            "research": (providers.get("research", "mock"), "OPENAI_API_KEY" if providers.get("research") == "openai" else None),
            "video": (providers.get("video", "mock"), "RUNWAY_API_KEY" if providers.get("video") == "runway" else None),
            "voice": (providers.get("voice", "mock"), "ELEVENLABS_API_KEY" if providers.get("voice") == "elevenlabs" else None),
            "publisher": (providers.get("publisher", "mock"), "YOUTUBE_CLIENT_ID" if providers.get("publisher") == "youtube" else None),
        }
        result = {}
        for kind, (name, env_key) in checks.items():
            env = get_env()
            secret_values = {
                "OPENAI_API_KEY": env.openai_api_key,
                "RUNWAY_API_KEY": env.runway_api_key,
                "ELEVENLABS_API_KEY": env.elevenlabs_api_key,
                "YOUTUBE_CLIENT_ID": env.youtube_client_id,
            }
            configured = True if name == "mock" else bool(secret_values.get(env_key or ""))
            result[kind] = {"provider": name, "configured": configured, "secret_required": env_key, "mode": "demo" if name == "mock" else "live"}
        renderer = providers.get("renderer", "mock")
        result["renderer"] = {"provider": renderer, "configured": True if renderer == "mock" else bool(shutil.which(self.config.get("provider_options",{}).get("ffmpeg",{}).get("binary","ffmpeg"))), "secret_required": None, "mode": "demo" if renderer == "mock" else "live"}
        return result
