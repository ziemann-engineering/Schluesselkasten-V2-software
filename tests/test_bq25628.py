"""
Unit tests for bq25628.py.

A ``MockI2CDevice`` replaces ``adafruit_bus_device.i2c_device.I2CDevice`` so
that register reads and writes can be inspected without real I2C hardware.

Note on getter tests
--------------------
Several getter methods (e.g. ``get_charge_current``) contain a bug where they
try to right-shift a ``bytearray`` directly (``val >> n``), which raises a
``TypeError``.  Those getters are explicitly skipped here; the tests focus on
the setter encoding logic and on error-raising helpers.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Mock I2C device
# ---------------------------------------------------------------------------

class MockI2CDevice:
    """
    Simulates adafruit_bus_device.i2c_device.I2CDevice.

    The BQ25628 driver calls:
        with self._i2c as i2c:
            i2c.write(buf, start=0, end=n)   # write register address (len 1)
                                               # or register + data (len > 1)
            i2c.readinto(buf, start=0, end=n) # fill buf from register map
    """

    def __init__(self, register_map=None):
        # register_map: {reg_addr (int): bytearray}
        self.register_map = dict(register_map or {})
        self._last_reg = None
        self.writes = []  # list of (reg_addr, data_bytearray)

    # Context-manager support
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def write(self, buf, start=0, end=None):
        data = bytes(buf[start:end])
        if len(data) == 1:
            # Register-address preamble for upcoming read
            self._last_reg = data[0]
        else:
            # Register address followed by payload → store in register map
            reg = data[0]
            payload = bytearray(data[1:])
            self.register_map[reg] = payload
            self.writes.append((reg, payload))

    def readinto(self, buf, start=0, end=None):
        length = (end if end is not None else len(buf)) - start
        reg_data = self.register_map.get(self._last_reg, bytearray(length))
        for i in range(min(length, len(reg_data))):
            buf[start + i] = reg_data[i]
        for i in range(len(reg_data), length):
            buf[start + i] = 0


# Part-information register value that satisfies __init__ validation:
#   part_id = (0b00010010 >> 3) & 0b111 = 2  → valid
#   part_rev = 0b00010010 & 0b111 = 2         → valid
_VALID_PART_INFO = bytearray([0b00010010])


@pytest.fixture
def mock_device():
    """Return a fresh MockI2CDevice with a valid part-info register."""
    return MockI2CDevice({0x38: _VALID_PART_INFO})


@pytest.fixture
def bq(mock_device, monkeypatch):
    """Return a BQ25628 instance backed by *mock_device*."""
    import bq25628 as bq_mod

    # Replace i2c_device.I2CDevice so that BQ25628.__init__ receives our mock
    fake_i2c_mod = MagicMock()
    fake_i2c_mod.I2CDevice.return_value = mock_device
    monkeypatch.setattr(bq_mod, "i2c_device", fake_i2c_mod)

    return bq_mod.BQ25628(None)  # i2c_bus arg is irrelevant; mock intercepts it


# ---------------------------------------------------------------------------
# __init__ validation
# ---------------------------------------------------------------------------

def test_init_succeeds_with_valid_part_id(bq):
    """BQ25628 instantiation succeeds when part_id ∈ {2, 4, 6} and rev == 2."""
    assert bq is not None


def test_init_raises_for_invalid_part_id(monkeypatch):
    """__init__ raises RuntimeError when the part-ID register is wrong."""
    import bq25628 as bq_mod

    # part_id = (0 >> 3) & 7 = 0, rev = 0 & 7 = 0 → both invalid
    bad_device = MockI2CDevice({0x38: bytearray([0x00])})
    fake_i2c_mod = MagicMock()
    fake_i2c_mod.I2CDevice.return_value = bad_device
    monkeypatch.setattr(bq_mod, "i2c_device", fake_i2c_mod)

    with pytest.raises(RuntimeError):
        bq_mod.BQ25628(None)


# ---------------------------------------------------------------------------
# set_charge_current – REG0x02, step 40 mA, encoding: (mA/40) << 5
# ---------------------------------------------------------------------------

def test_set_charge_current_1000mA(bq, mock_device):
    bq.set_charge_current(1000)
    reg, data = mock_device.writes[-1]
    assert reg == 0x02
    expected = int(1000 / 40) << 5  # = 800 = 0x0320
    written_val = int.from_bytes(data, "little")
    assert written_val == expected


def test_set_charge_current_40mA_minimum(bq, mock_device):
    bq.set_charge_current(40)
    _, data = mock_device.writes[-1]
    assert int.from_bytes(data, "little") == (1 << 5)


def test_set_charge_current_2000mA_maximum(bq, mock_device):
    bq.set_charge_current(2000)
    _, data = mock_device.writes[-1]
    assert int.from_bytes(data, "little") == (50 << 5)


# ---------------------------------------------------------------------------
# set_charge_voltage – REG0x04, step 10 mV, encoding: (mV//10) << 3
# ---------------------------------------------------------------------------

def test_set_charge_voltage_4000mV(bq, mock_device):
    bq.set_charge_voltage(4000)
    reg, data = mock_device.writes[-1]
    assert reg == 0x04
    expected = (4000 // 10) << 3
    assert int.from_bytes(data, "little") == expected


def test_set_charge_voltage_3500mV_minimum(bq, mock_device):
    bq.set_charge_voltage(3500)
    _, data = mock_device.writes[-1]
    assert int.from_bytes(data, "little") == (350 << 3)


def test_set_charge_voltage_4800mV_maximum(bq, mock_device):
    bq.set_charge_voltage(4800)
    _, data = mock_device.writes[-1]
    assert int.from_bytes(data, "little") == (480 << 3)


# ---------------------------------------------------------------------------
# set_input_current_limit – REG0x06, step 20 mA, encoding: (mA//20) << 4
# ---------------------------------------------------------------------------

def test_set_input_current_limit_1000mA(bq, mock_device):
    bq.set_input_current_limit(1000)
    reg, data = mock_device.writes[-1]
    assert reg == 0x06
    assert int.from_bytes(data, "little") == (50 << 4)


# ---------------------------------------------------------------------------
# set_input_voltage_limit – REG0x08, step 40 mV, encoding: (mV//40) << 5
# ---------------------------------------------------------------------------

def test_set_input_voltage_limit_5000mV(bq, mock_device):
    bq.set_input_voltage_limit(5000)
    reg, data = mock_device.writes[-1]
    assert reg == 0x08
    assert int.from_bytes(data, "little") == (125 << 5)


# ---------------------------------------------------------------------------
# set_votg_regulation – REG0x0C, step 80 mV, encoding: (mV//80) << 6
# ---------------------------------------------------------------------------

def test_set_votg_regulation_4960mV(bq, mock_device):
    bq.set_votg_regulation(4960)
    reg, data = mock_device.writes[-1]
    assert reg == 0x0C
    assert int.from_bytes(data, "little") == (62 << 6)


# ---------------------------------------------------------------------------
# set_minimal_system_voltage – REG0x0E, step 80 mV, encoding: (mV//80) << 6
# ---------------------------------------------------------------------------

def test_set_minimal_system_voltage_3200mV(bq, mock_device):
    bq.set_minimal_system_voltage(3200)
    reg, data = mock_device.writes[-1]
    assert reg == 0x0E
    assert int.from_bytes(data, "little") == (40 << 6)


# ---------------------------------------------------------------------------
# set_precharge_current – REG0x10, step 10 mA, encoding: (mA//10) << 3
# ---------------------------------------------------------------------------

def test_set_precharge_current_100mA(bq, mock_device):
    bq.set_precharge_current(100)
    reg, data = mock_device.writes[-1]
    assert reg == 0x10
    assert int.from_bytes(data, "little") == (10 << 3)


# ---------------------------------------------------------------------------
# set_termination_current – REG0x12, step 10 mA, encoding: (mA//10) << 3
# ---------------------------------------------------------------------------

def test_set_termination_current_50mA(bq, mock_device):
    bq.set_termination_current(50)
    reg, data = mock_device.writes[-1]
    assert reg == 0x12
    assert int.from_bytes(data, "little") == (5 << 3)


# ---------------------------------------------------------------------------
# batfet_control – invalid mode raises ValueError
# ---------------------------------------------------------------------------

def test_batfet_control_invalid_mode_raises(bq):
    with pytest.raises(ValueError):
        bq.batfet_control("invalid")


def test_batfet_control_shipmode_raises(bq):
    """
    'shipmode' is NOT a valid mode string.
    main.py calls batfet_control("shipmode") which is a bug –
    the correct string is "ship".  This test documents that.
    """
    with pytest.raises(ValueError):
        bq.batfet_control("shipmode")


def test_batfet_control_valid_modes_do_not_raise(bq):
    for mode in ("normal", "shutdown", "ship", "reset"):
        bq.batfet_control(mode)  # must not raise


# ---------------------------------------------------------------------------
# adc_mode – invalid mode raises ValueError
# ---------------------------------------------------------------------------

def test_adc_mode_invalid_raises(bq):
    with pytest.raises(ValueError):
        bq.adc_mode("burst")


def test_adc_mode_valid_modes_do_not_raise(bq):
    for mode in ("continuous", "one-shot"):
        bq.adc_mode(mode)


# ---------------------------------------------------------------------------
# adc_bits – invalid resolution raises ValueError
# ---------------------------------------------------------------------------

def test_adc_bits_invalid_raises(bq):
    with pytest.raises(ValueError):
        bq.adc_bits(8)


def test_adc_bits_valid_resolutions_do_not_raise(bq):
    for bits in (9, 10, 11, 12):
        bq.adc_bits(bits)
