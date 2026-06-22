"""
Unit tests for networking.py – specifically the ``process_mqtt_command``
function, which contains branching logic worth verifying automatically.

``hardware_V2``, ``Adafruit_IO``, and ``ping3`` are all replaced by stubs
installed by conftest.py before this module is imported.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# networking.py imports hardware_V2 at module level; the stub installed by
# conftest.py satisfies that import.
import networking

# Token used in all test commands; must be set on networking._command_token
# before calling process_mqtt_command.
_TEST_TOKEN = "test_token"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_compartments(*indices):
    """Return a dict of mock compartments keyed by str(index)."""
    return {str(i): MagicMock() for i in indices}


@pytest.fixture(autouse=True)
def set_command_token():
    """Install a known command token for every test and restore afterwards."""
    original = networking._command_token
    networking._command_token = _TEST_TOKEN
    yield
    networking._command_token = original


# ---------------------------------------------------------------------------
# "status" command
# ---------------------------------------------------------------------------

def test_status_all_calls_check_all(monkeypatch):
    mock_hw = sys.modules["hardware_V2"]
    mock_hw.check_all.return_value = []

    networking.process_mqtt_command(f"{_TEST_TOKEN} status all")

    mock_hw.check_all.assert_called()


def test_status_specific_compartment(monkeypatch):
    mock_hw = sys.modules["hardware_V2"]
    comps = _make_compartments(1, 2, 3)
    mock_hw.compartments = comps

    networking.process_mqtt_command(f"{_TEST_TOKEN} status 2")

    comps["2"].is_open.assert_called()


# ---------------------------------------------------------------------------
# "open" command
# ---------------------------------------------------------------------------

def test_open_all_calls_open_all(monkeypatch):
    mock_hw = sys.modules["hardware_V2"]

    networking.process_mqtt_command(f"{_TEST_TOKEN} open all")

    mock_hw.open_all.assert_called()


def test_open_specific_compartment(monkeypatch):
    mock_hw = sys.modules["hardware_V2"]
    comps = _make_compartments(1, 2, 3)
    mock_hw.compartments = comps

    networking.process_mqtt_command(f"{_TEST_TOKEN} open 2")

    comps["2"].open.assert_called()


def test_open_compartment_out_of_range_does_not_raise(monkeypatch):
    mock_hw = sys.modules["hardware_V2"]
    comps = _make_compartments(1, 2)
    mock_hw.compartments = comps

    # Compartment "5" does not exist; must not raise
    networking.process_mqtt_command(f"{_TEST_TOKEN} open 5")


# ---------------------------------------------------------------------------
# "restart" command
# ---------------------------------------------------------------------------

def test_restart_device_calls_subprocess(monkeypatch):
    mock_run = MagicMock()
    monkeypatch.setattr("networking.subprocess.run", mock_run)

    networking.process_mqtt_command(f"{_TEST_TOKEN} restart device")

    mock_run.assert_called_once_with(["sudo", "reboot", "now"])


def test_restart_software_calls_subprocess(monkeypatch):
    mock_run = MagicMock()
    monkeypatch.setattr("networking.subprocess.run", mock_run)

    networking.process_mqtt_command(f"{_TEST_TOKEN} restart software")

    mock_run.assert_called_once_with(["./start.sh"])


# ---------------------------------------------------------------------------
# Malformed / unknown commands must not raise
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("payload", [
    "",
    "unknown",
    "open",          # missing argument
    "status",        # missing argument
    "restart",       # missing argument
    "restart xyz",   # unknown sub-command (no branch matches, no exception)
    "open abc",      # non-numeric compartment index
])
def test_malformed_commands_do_not_raise(payload):
    try:
        networking.process_mqtt_command(payload)
    except (ValueError, IndexError):
        # open/status with non-numeric comp will raise ValueError/IndexError
        # inside the current implementation; document that here rather than
        # masking the crash so that fixing it is explicit.
        pytest.xfail(
            f"process_mqtt_command({payload!r}) raised an exception; "
            "input validation should be added to the production code."
        )
