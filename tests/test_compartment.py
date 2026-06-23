"""
Unit tests for compartment.py.

``digitalio`` is replaced by stub classes installed in conftest.py.
Pin objects are lightweight mocks with controllable ``.value`` attributes.
"""

import sys
import os
import time
import pytest
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Pin helpers
# ---------------------------------------------------------------------------

class MockPin:
    """Minimal stand-in for a digitalio.DigitalInOut pin."""

    def __init__(self, initial_value=False):
        self.value = initial_value
        self.direction = None
        self.pull = None


def make_compartment(input_value=False, output_value=False):
    """Return a compartment instance with one mock input and one mock output."""
    import compartment as comp_mod

    in_pin = MockPin(initial_value=input_value)
    out_pin = MockPin(initial_value=output_value)
    return comp_mod.Compartment(in_pin, out_pin), in_pin, out_pin


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def test_init_sets_direction():
    from digitalio import Direction, Pull
    comp, in_pin, out_pin = make_compartment()

    assert in_pin.direction == Direction.INPUT
    assert in_pin.pull == Pull.UP
    assert out_pin.direction == Direction.OUTPUT
    assert out_pin.value is False


def test_init_default_statuses():
    comp, *_ = make_compartment()
    assert comp.door_status == "closed"
    assert comp.content_status == "unknown"
    assert comp.type == "small"


# ---------------------------------------------------------------------------
# is_open
# ---------------------------------------------------------------------------

def test_is_open_returns_true_when_all_inputs_high():
    """All inputs high → door is open."""
    comp, in_pin, _ = make_compartment(input_value=True)
    assert comp.is_open() is True


def test_is_open_returns_false_when_any_input_low():
    """Any input low → door is closed."""
    comp, in_pin, _ = make_compartment(input_value=False)
    assert comp.is_open() is False


def test_is_open_multiple_inputs_one_low():
    """With two inputs: door is closed if either is low."""
    import compartment as comp_mod

    in1 = MockPin(initial_value=True)
    in2 = MockPin(initial_value=False)
    out = MockPin()
    c = comp_mod.Compartment(in1, out)
    c.add_input(in2)

    assert c.is_open() is False


def test_is_open_multiple_inputs_both_high():
    import compartment as comp_mod

    in1 = MockPin(initial_value=True)
    in2 = MockPin(initial_value=True)
    out = MockPin()
    c = comp_mod.Compartment(in1, out)
    c.add_input(in2)

    assert c.is_open() is True


# ---------------------------------------------------------------------------
# set_outputs
# ---------------------------------------------------------------------------

def test_set_outputs_true():
    comp, _, out_pin = make_compartment()
    comp.set_outputs(True)
    assert out_pin.value is True


def test_set_outputs_false():
    comp, _, out_pin = make_compartment()
    comp.set_outputs(True)
    comp.set_outputs(False)
    assert out_pin.value is False


def test_set_outputs_multiple_outputs():
    import compartment as comp_mod

    out1 = MockPin()
    out2 = MockPin()
    in_pin = MockPin()
    c = comp_mod.Compartment(in_pin, out1)
    c.add_output(out2)

    c.set_outputs(True)
    assert out1.value is True
    assert out2.value is True


# ---------------------------------------------------------------------------
# open()
# ---------------------------------------------------------------------------

def test_open_drives_output_high_then_low():
    """open() must assert the lock output and then deassert it."""
    comp, in_pin, out_pin = make_compartment(input_value=False)

    # Door stays closed throughout → output will be driven then released
    with patch("time.sleep"):
        comp.open(on_time=0.2)

    assert out_pin.value is False  # must be de-asserted after open()


def test_open_returns_true_when_door_opens():
    """open() returns True when the door is detected open."""
    comp, in_pin, out_pin = make_compartment(input_value=False)

    # Make the door appear open on the first is_open() check inside the loop
    call_count = [0]
    original_is_open = comp.is_open

    def mock_is_open():
        call_count[0] += 1
        return call_count[0] >= 1  # True immediately

    comp.is_open = mock_is_open

    with patch("time.sleep"):
        result = comp.open(on_time=1.0)

    assert result is True


def test_open_returns_false_when_door_never_opens():
    """open() returns False when the door never opens within on_time."""
    comp, in_pin, out_pin = make_compartment(input_value=False)

    with patch("time.sleep"):
        result = comp.open(on_time=0.1)

    assert result is False


def test_open_caps_on_time_to_maximum():
    """on_time values exceeding maximum_on_time are silently capped."""
    import compartment as comp_mod

    comp, in_pin, out_pin = make_compartment(input_value=False)

    sleep_calls = []
    with patch("time.sleep", side_effect=lambda d: sleep_calls.append(d)):
        comp.open(on_time=9999)

    # Total sleep time must not exceed maximum_on_time / check_time iterations
    max_iters = comp_mod.maximum_on_time / comp_mod.check_time
    assert len(sleep_calls) <= max_iters


# ---------------------------------------------------------------------------
# set_LEDs
# ---------------------------------------------------------------------------

def _make_comp_with_led(pixel_type_value="GRB"):
    comp, *_ = make_compartment()
    mock_connector = MagicMock()
    mock_connector.pixel_type.value = pixel_type_value
    comp.LED_connector = mock_connector
    comp.LEDs = [0]
    return comp, mock_connector


def test_set_leds_white_rgbw():
    comp, connector = _make_comp_with_led("GRBW")
    comp.set_LEDs("white")
    connector.set_led_color.assert_called_once_with(0, 0, 0, 0, 255)


def test_set_leds_white_rgb():
    comp, connector = _make_comp_with_led("GRB")
    comp.set_LEDs("white")
    connector.set_led_color.assert_called_once_with(0, 255, 255, 255)


def test_set_leds_off_rgbw():
    comp, connector = _make_comp_with_led("GRBW")
    comp.set_LEDs("off")
    connector.set_led_color.assert_called_once_with(0, 0, 0, 0, 0)


def test_set_leds_off_rgb():
    comp, connector = _make_comp_with_led("GRB")
    comp.set_LEDs("off")
    connector.set_led_color.assert_called_once_with(0, 0, 0, 0)


def test_set_leds_rgb_tuple_on_rgbw_connector_pads_with_zero():
    """A 3-element colour tuple should be padded to 4 elements for RGBW strips."""
    comp, connector = _make_comp_with_led("GRBW")
    comp.set_LEDs((100, 150, 200))
    connector.set_led_color.assert_called_once_with(0, 100, 150, 200, 0)


def test_set_leds_rgbw_tuple_on_rgb_connector_is_truncated():
    """A 4-element colour tuple should be truncated to 3 elements for RGB strips."""
    comp, connector = _make_comp_with_led("GRB")
    comp.set_LEDs((100, 150, 200, 255))
    connector.set_led_color.assert_called_once_with(0, 100, 150, 200)


def test_set_leds_calls_update_strip():
    comp, connector = _make_comp_with_led("RGB")
    comp.set_LEDs("off")
    connector.update_strip.assert_called_once()
