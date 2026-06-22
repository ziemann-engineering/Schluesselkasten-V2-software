"""
Shared pytest configuration and fixtures.

This module installs stub versions of hardware-specific packages into
sys.modules *at import time* so that every test module can safely import the
production code (flink, compartment, bq25628, networking) without needing
real Raspberry Pi hardware.
"""

import sys
import types
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Hardware-stub installation
# Must happen at module level so that the stubs are present before any test
# file does its top-level imports.
# ---------------------------------------------------------------------------

def _make_stub(name: str) -> types.ModuleType:
    """Return a new MagicMock-based stub registered under *name*."""
    stub = MagicMock(name=name)
    stub.__name__ = name
    stub.__spec__ = None
    return stub


def _install_hardware_stubs() -> None:
    # digitalio – used by compartment.py for pin direction / pull constants
    if "digitalio" not in sys.modules:
        dio = types.ModuleType("digitalio")

        class _Direction:
            INPUT = "INPUT"
            OUTPUT = "OUTPUT"

        class _Pull:
            UP = "UP"
            DOWN = "DOWN"

        dio.Direction = _Direction
        dio.Pull = _Pull
        dio.DigitalInOut = MagicMock(name="digitalio.DigitalInOut")
        sys.modules["digitalio"] = dio

    # adafruit_bus_device – used by bq25628.py
    if "adafruit_bus_device" not in sys.modules:
        sys.modules["adafruit_bus_device"] = _make_stub("adafruit_bus_device")
    if "adafruit_bus_device.i2c_device" not in sys.modules:
        sys.modules["adafruit_bus_device.i2c_device"] = _make_stub(
            "adafruit_bus_device.i2c_device"
        )

    # hardware_V2 – imported at module level by networking.py
    if "hardware_V2" not in sys.modules:
        hw = _make_stub("hardware_V2")
        hw.compartments = {}
        sys.modules["hardware_V2"] = hw

    # Adafruit_IO – imported by networking.py
    if "Adafruit_IO" not in sys.modules:
        sys.modules["Adafruit_IO"] = _make_stub("Adafruit_IO")

    # ping3 – imported by networking.py
    if "ping3" not in sys.modules:
        sys.modules["ping3"] = _make_stub("ping3")

    # board – used by hardware_V2 (not tested directly, but may appear as
    # transitive import in some edge cases)
    if "board" not in sys.modules:
        sys.modules["board"] = _make_stub("board")


_install_hardware_stubs()
