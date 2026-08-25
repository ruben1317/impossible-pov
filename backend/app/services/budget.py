from __future__ import annotations
import json
from datetime import datetime, timezone
from sqlmodel import Session, select
from app.models.cost import GenerationCost


class BudgetExceeded(RuntimeError):
    pass


class BudgetService:
    def __init__(self, session: Session, config: dict):
        self.session = session
        self.config = config

    def month_spend(self) -> float:
        now = datetime.now(timezone.utc)
        start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        rows = self.session.exec(select(GenerationCost).where(GenerationCost.created_at >= start)).all()
        return round(sum(float(r.actual_cost or 0) for r in rows), 4)

    def assert_allowed(self, estimated_cost: float):
        b = self.config.get("budgets", {})
        if not b.get("hard_stop_on_cap", True):
            return
        cap = float(b.get("monthly_cap", 0) or 0)
        if cap > 0 and self.month_spend() + estimated_cost > cap:
            raise BudgetExceeded(f"Monthly budget cap would be exceeded (${self.month_spend():.2f} spent / ${cap:.2f} cap).")

    def record(self, *, project_id: int | None, provider: str, operation: str, estimated_cost: float = 0.0,
               actual_cost: float = 0.0, scene_index: int | None = None, metadata: dict | None = None):
        row = GenerationCost(project_id=project_id, provider=provider, operation=operation, scene_index=scene_index,
                             estimated_cost=estimated_cost, actual_cost=actual_cost,
                             metadata_json=json.dumps(metadata or {}, ensure_ascii=False))
        self.session.add(row)
        self.session.commit()
        return row
