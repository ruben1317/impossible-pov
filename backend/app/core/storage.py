from __future__ import annotations
from pathlib import Path
from typing import Protocol


class StorageProvider(Protocol):
    def project_dir(self, project_id: int) -> Path: ...
    def path(self, project_id: int, category: str, filename: str) -> Path: ...


class LocalStorage:
    def __init__(self, base_path: str):
        root = Path(base_path)
        if not root.is_absolute():
            root = (Path(__file__).resolve().parents[3] / root).resolve()
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def project_dir(self, project_id: int) -> Path:
        p = self.root / "projects" / str(project_id)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def path(self, project_id: int, category: str, filename: str) -> Path:
        p = self.project_dir(project_id) / category
        p.mkdir(parents=True, exist_ok=True)
        return p / filename


def build_storage(config: dict):
    storage = config.get("storage", {})
    provider = storage.get("provider", "local")
    if provider == "local":
        return LocalStorage(storage.get("local", {}).get("base_path", "./storage"))
    raise NotImplementedError(f"Storage provider '{provider}' is configured but not implemented yet")
