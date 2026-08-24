from __future__ import annotations
from typing import Any
from .base import TextProvider, ResearchProvider, MediaProvider


IDEAS = [
    ("POV: You Wake Up 65 Million Years Ago", "survival", "You wake in a Cretaceous forest and realize the sounds around you are not modern animals.", "Dinosaurs + survival + immediate first-person danger."),
    ("POV: You're in Pompeii 10 Minutes Before Vesuvius", "past", "You are walking through Pompeii as the first signs of the eruption begin.", "Famous event with a built-in countdown."),
    ("POV: Earth Loses the Moon Tonight", "impossible", "The Moon suddenly disappears and the first strange effects begin around you.", "Instant curiosity and escalating science consequences."),
    ("POV: You Wake Up in Ancient Egypt", "past", "You step outside into a bustling ancient Egyptian city at sunrise.", "Recognizable world, strong visual novelty."),
    ("POV: You're the First Human on Mars", "space", "Your boots touch Mars as you become the first person to walk outside the lander.", "Aspirational, cinematic and easy to serialize."),
    ("POV: You Have to Survive the Ice Age", "survival", "Night is falling, the temperature is collapsing, and predators are nearby.", "Survival stakes and recognizable megafauna."),
    ("POV: You Wake Up in Los Angeles in 2200", "future", "You walk into a transformed future Los Angeles filled with new transit and architecture.", "Familiar place + radical future contrast."),
    ("POV: You Fall Through Jupiter's Clouds", "space", "You descend into Jupiter and witness the atmosphere change around you.", "Impossible visual spectacle with science framing."),
    ("POV: You Have 5 Minutes Before Earth Stops Rotating", "impossible", "Emergency alerts appear as scientists announce Earth's rotation is about to stop.", "Clear countdown and massive stakes."),
    ("POV: You Enter Rome in 100 AD", "past", "You cross into imperial Rome at its height and experience the city from street level.", "Immersive historical tourism with strong series potential."),
]


class MockTextProvider(TextProvider):
    def generate_ideas(self, *, count: int, category: str | None, config: dict[str, Any]) -> list[dict[str, Any]]:
        rows = [x for x in IDEAS if category is None or x[1] == category]
        if not rows:
            rows = IDEAS
        cost = float(config.get("provider_options", {}).get("runway", {}).get("estimated_cost_per_second", 0.05))
        clip_seconds = config.get("video_defaults", {}).get("clip_seconds", 5)
        scene_count = config.get("video_defaults", {}).get("scene_count", 6)
        est = round(cost * clip_seconds * scene_count, 2)
        return [
            {"title": t, "category": c, "premise": p, "viral_reason": v, "estimated_cost": est}
            for t, c, p, v in rows[:count]
        ]

    def write_script(self, *, title: str, premise: str, research: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        lines = [
            (0, 3, "Don't move.", "POV eyes open; immediate environmental movement."),
            (3, 8, "You went to sleep in 2026.", "Hands push forward into the environment."),
            (8, 14, "But this isn't your world anymore.", "Reveal the impossible location."),
            (14, 20, "And something nearby just noticed you.", "Subtle threat enters frame."),
            (20, 27, "Your first problem isn't getting home.", "Viewer begins moving quickly."),
            (27, 34, "It's surviving the next five minutes.", "Major threat reveal / action beat."),
            (34, 38, "What would you do next?", "Cut toward a cliffhanger / loopable final frame."),
        ]
        return {
            "hook": lines[0][2],
            "narration": " ".join(x[2] for x in lines),
            "segments": [
                {"start": a, "end": b, "narration": n, "visual": v} for a, b, n, v in lines
            ],
            "title": title,
            "description": f"Experience the impossible in first person. {premise}",
            "tags": ["POV", "AI", "Shorts", "Impossible POV"],
        }

    def storyboard(self, *, script: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
        continuity = config.get("content", {}).get("continuity_rules", [])
        scenes = []
        for i, seg in enumerate(script.get("segments", [])[: config.get("video_defaults", {}).get("scene_count", 6)]):
            scenes.append({
                "index": i,
                "narration": seg["narration"],
                "prompt": f"{seg['visual']} | " + "; ".join(continuity),
                "approved": False,
                "regenerations": 0,
                "preview_url": f"https://placehold.co/540x960/111/fff?text=Scene+{i+1}",
            })
        return scenes


class MockResearchProvider(ResearchProvider):
    def research(self, *, title: str, category: str, premise: str, config: dict[str, Any]) -> dict[str, Any]:
        return {
            "summary": f"Mock research pack for {title}.",
            "facts": [
                "Keep factual claims conservative and verifiable.",
                "Avoid presenting speculative visuals as historical footage.",
                "Prioritize details that affect what the viewer would see, hear, or feel.",
            ],
            "risk_notes": ["Mock mode: replace with a research provider before factual production."],
        }


class MockMediaProvider(MediaProvider):
    def __init__(self, kind: str):
        self.kind = kind

    def generate(self, **kwargs) -> dict[str, Any]:
        index = kwargs.get("scene_index")
        suffix = f"-scene-{index + 1}" if isinstance(index, int) else ""
        return {
            "provider": "mock",
            "kind": self.kind,
            "status": "ready",
            "url": f"mock://{self.kind}{suffix}",
            "cost": 0.0,
        }
