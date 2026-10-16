"""槽位清单。唯一真相在 runtime/context.py 的 SLOT_REGISTRY，这里只做投影 ——
前端不必再硬编一份，否则又会出现「两份清单互相不一致」的老问题。"""

from __future__ import annotations

from fastapi import APIRouter

from app.runtime.context import SLOT_REGISTRY

router = APIRouter(prefix="/api/slots", tags=["slots"])


@router.get("")
def list_slots() -> list[dict]:
    return [
        {"key": spec.key, "label": spec.label, "priority": spec.priority, "over_budget": spec.over_budget}
        for spec in sorted(SLOT_REGISTRY.values(), key=lambda s: -s.priority)
    ]
