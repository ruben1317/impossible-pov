from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class TextProvider(ABC):
    @abstractmethod
    def generate_ideas(self, *, count: int, category: str | None, config: dict[str, Any]) -> list[dict[str, Any]]: ...
    @abstractmethod
    def write_script(self, *, title: str, premise: str, research: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]: ...
    @abstractmethod
    def storyboard(self, *, script: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]: ...


class ResearchProvider(ABC):
    @abstractmethod
    def research(self, *, title: str, category: str, premise: str, config: dict[str, Any]) -> dict[str, Any]: ...


class MediaProvider(ABC):
    @abstractmethod
    def generate(self, **kwargs) -> dict[str, Any]: ...
