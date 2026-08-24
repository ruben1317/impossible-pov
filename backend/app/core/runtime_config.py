from __future__ import annotations

import copy
import json
from typing import Any
from sqlmodel import Session

from app.core.config import get_config
from app.models.setting import RuntimeSetting


def deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def get_overrides(session: Session) -> dict[str, Any]:
    row = session.get(RuntimeSetting, 1)
    if not row:
        return {}
    try:
        value = json.loads(row.overrides_json or "{}")
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def get_effective_config(session: Session) -> dict[str, Any]:
    return deep_merge(get_config().raw, get_overrides(session))


def save_overrides(session: Session, overrides: dict[str, Any]) -> dict[str, Any]:
    row = session.get(RuntimeSetting, 1) or RuntimeSetting(id=1)
    row.overrides_json = json.dumps(overrides, ensure_ascii=False)
    from datetime import datetime, timezone
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    return get_effective_config(session)
