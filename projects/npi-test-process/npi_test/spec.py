"""Test Specification: Test Items, Test Points, limits and PASS/FAIL rules."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TestItem:
    __test__ = False  # not a pytest class

    id: str
    name: str
    test_point: str
    instrument: str
    unit: str
    lsl: float | None
    usl: float | None
    target: float
    time_s: float
    process_sigma: float
    repeat_sigma: float
    reprod_sigma: float

    def judge(self, value: float) -> bool:
        """PASS when the value is inside the (inclusive) limits."""
        if self.lsl is not None and value < self.lsl:
            return False
        if self.usl is not None and value > self.usl:
            return False
        return True

    @property
    def tolerance(self) -> float:
        """Total tolerance width; for a one-sided limit, twice the distance target-to-limit."""
        if self.lsl is not None and self.usl is not None:
            return self.usl - self.lsl
        limit = self.usl if self.usl is not None else self.lsl
        return 2 * abs(limit - self.target)


@dataclass(frozen=True)
class Spec:
    board: str
    revision: str
    station: str
    cycle_overhead_s: float
    max_contact_retries: int
    max_instrument_retries: int
    pvt_criteria: dict
    items: list[TestItem] = field(default_factory=list)

    def item(self, item_id: str) -> TestItem:
        for it in self.items:
            if it.id == item_id:
                return it
        raise KeyError(item_id)


def load_spec(path: str | Path) -> Spec:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    items = [TestItem(**it) for it in raw.pop("items")]
    ids = [i.id for i in items]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate test item id in spec")
    for it in items:
        if it.lsl is None and it.usl is None:
            raise ValueError(f"{it.id}: at least one limit is required")
        if it.lsl is not None and it.usl is not None and it.lsl >= it.usl:
            raise ValueError(f"{it.id}: LSL must be lower than USL")
    return Spec(items=items, **raw)
