"""Test Equipment drivers and Test Fixture/Jig.

`Instrument` is the interface a real driver (VISA/SCPI, serial, ...) would implement.
The Simulated* classes let the whole station run without hardware.
"""
from __future__ import annotations

import logging
import random
from abc import ABC, abstractmethod

from .spec import TestItem

log = logging.getLogger("npi.instruments")


class InstrumentError(RuntimeError):
    """Communication / measurement error from an instrument."""


class Instrument(ABC):
    name = "instrument"

    def __init__(self) -> None:
        self.connected = False

    def connect(self) -> None:
        self.connected = True
        log.debug("%s connected", self.name)

    def close(self) -> None:
        self.connected = False
        log.debug("%s closed", self.name)

    @abstractmethod
    def measure(self, item: TestItem) -> float: ...


class DeviceUnderTest:
    """True (physical) values of one board. Real hardware would not expose this."""

    def __init__(self, serial: str, true_values: dict[str, float]) -> None:
        self.serial = serial
        self.true_values = true_values


class Fixture:
    """Test Fixture/Jig: clamps the board, checks contact, seats the pogo pins."""

    def __init__(self, rng: random.Random, contact_fault_rate: float = 0.02) -> None:
        self.rng = rng
        self.contact_fault_rate = contact_fault_rate
        self.dut: DeviceUnderTest | None = None
        self.seat_offset: dict[str, float] = {}    # reproducibility error from pin seating
        self.operator_bias: dict[str, float] = {}  # set by the GRR study per operator

    def load(self, dut: DeviceUnderTest) -> None:
        self.dut = dut

    def clamp(self, items: list[TestItem]) -> bool:
        """Clamp and run the contact check. Returns False on a bad contact."""
        if self.dut is None:
            raise RuntimeError("no DUT loaded")
        self.seat_offset = {i.id: self.rng.gauss(0, i.reprod_sigma) for i in items}
        ok = self.rng.random() >= self.contact_fault_rate
        log.debug("clamp %s contact=%s", self.dut.serial, "OK" if ok else "FAIL")
        return ok

    def release(self) -> None:
        self.dut = None
        self.seat_offset = {}


class _SimulatedMeter(Instrument):
    def __init__(self, fixture: Fixture, rng: random.Random, comm_error_rate: float = 0.004) -> None:
        super().__init__()
        self.fixture = fixture
        self.rng = rng
        self.comm_error_rate = comm_error_rate

    def measure(self, item: TestItem) -> float:
        if not self.connected:
            raise InstrumentError(f"{self.name} not connected")
        if self.rng.random() < self.comm_error_rate:
            raise InstrumentError(f"{self.name} timeout at {item.test_point}")
        dut = self.fixture.dut
        if dut is None:
            raise InstrumentError("no DUT in fixture")
        value = dut.true_values[item.id]
        value += self.fixture.seat_offset.get(item.id, 0.0)
        value += self.fixture.operator_bias.get(item.id, 0.0)
        value += self.rng.gauss(0, item.repeat_sigma)  # repeatability
        return value


class SimulatedDMM(_SimulatedMeter):
    name = "DMM"


class SimulatedCounter(_SimulatedMeter):
    name = "FreqCounter"


class SimulatedScope(_SimulatedMeter):
    name = "Scope"


class TestStation:
    """Test Station: PC + equipment + fixture. Maps each item to its instrument."""

    __test__ = False

    def __init__(self, rng: random.Random, contact_fault_rate: float = 0.02,
                 comm_error_rate: float = 0.004) -> None:
        self.fixture = Fixture(rng, contact_fault_rate)
        self.instruments: dict[str, Instrument] = {
            "dmm": SimulatedDMM(self.fixture, rng, comm_error_rate),
            "counter": SimulatedCounter(self.fixture, rng, comm_error_rate),
            "scope": SimulatedScope(self.fixture, rng, comm_error_rate),
        }

    def __enter__(self) -> "TestStation":
        for ins in self.instruments.values():
            ins.connect()
        return self

    def __exit__(self, *exc) -> None:
        for ins in self.instruments.values():
            ins.close()
