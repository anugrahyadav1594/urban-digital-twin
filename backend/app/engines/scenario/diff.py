"""Scenario diffing. ARCHITECTURE §16, §24."""
from __future__ import annotations

from typing import Any, Sequence

from ..contracts import Operation


def change_summary(changes: Sequence[Any]) -> dict[str, Any]:
    """Counts by operation and entity type."""
    by_op: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for c in changes:
        by_op[c.operation] = by_op.get(c.operation, 0) + 1
        by_type[c.entity_type] = by_type.get(c.entity_type, 0) + 1
    return {
        "total_changes": len(changes),
        "by_operation": by_op,
        "by_entity_type": by_type,
    }


def diff_scenarios(
    changes_a: Sequence[Any], changes_b: Sequence[Any]
) -> dict[str, Any]:
    """Compare two change sets by (entity_type, entity_id, operation)."""
    def key(c: Any) -> tuple[str, str, str]:
        return (c.entity_type, str(c.entity_id), c.operation)

    ka = {key(c) for c in changes_a}
    kb = {key(c) for c in changes_b}
    only_a = sorted(ka - kb)
    only_b = sorted(kb - ka)
    shared = sorted(ka & kb)

    return {
        "only_in_a": [
            {"entity_type": t, "entity_id": i, "operation": o} for t, i, o in only_a
        ],
        "only_in_b": [
            {"entity_type": t, "entity_id": i, "operation": o} for t, i, o in only_b
        ],
        "in_both": [
            {"entity_type": t, "entity_id": i, "operation": o} for t, i, o in shared
        ],
        "summary": {
            "a_total": len(ka), "b_total": len(kb),
            "shared": len(shared),
            "divergent": len(only_a) + len(only_b),
        },
    }
