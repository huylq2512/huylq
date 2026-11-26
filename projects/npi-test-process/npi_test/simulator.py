"""Synthetic production: board-to-board variation plus occasional real defects."""
from __future__ import annotations

import random

from .instruments import DeviceUnderTest
from .spec import Spec


def make_unit(spec: Spec, rng: random.Random, serial: str, defect_rate: float = 0.015) -> DeviceUnderTest:
    values = {i.id: rng.gauss(i.target, i.process_sigma) for i in spec.items}
    if rng.random() < defect_rate:
        item = rng.choice(spec.items)
        half = item.tolerance / 2
        sign = 1.0 if item.lsl is None else rng.choice([-1.0, 1.0])
        values[item.id] = item.target + sign * half * rng.uniform(1.2, 2.5)
    return DeviceUnderTest(serial, values)
