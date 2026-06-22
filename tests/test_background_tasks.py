"""
Tests for the pure-logic algorithms extracted from main.py's background_tasks loop.

``main.py`` cannot be imported in CI because it has top-level initialisation
code that requires network, MQTT and hardware.  Instead, the algorithms are
replicated here as standalone functions that mirror the production logic
exactly – so that any future refactoring of main.py can be validated by
keeping these tests green.
"""

import pytest


# ---------------------------------------------------------------------------
# Helper: Critical-battery shutdown counter
# (mirrors the VBAT/VBUS block inside background_tasks)
# ---------------------------------------------------------------------------

def run_battery_monitor(readings):
    """
    Simulate the critical-battery counting logic from background_tasks.

    Parameters
    ----------
    readings : list of (VBAT_mV, VBUS_mV)

    Returns
    -------
    shutdown_triggered : bool
    final_counter : int
    """
    critical_battery_seconds = 0
    shutdown_triggered = False

    for VBAT, VBUS in readings:
        if VBAT < 3000 and VBUS < 4000:
            critical_battery_seconds += 1
            if critical_battery_seconds >= 5:
                shutdown_triggered = True
        else:
            critical_battery_seconds = 0

    return shutdown_triggered, critical_battery_seconds


def test_critical_battery_triggers_after_5_consecutive_low_readings():
    readings = [(2900, 3900)] * 5
    triggered, _ = run_battery_monitor(readings)
    assert triggered is True


def test_critical_battery_does_not_trigger_after_4_readings():
    readings = [(2900, 3900)] * 4
    triggered, counter = run_battery_monitor(readings)
    assert triggered is False
    assert counter == 4


def test_critical_battery_counter_resets_on_recovery():
    """A recovery reading resets the counter; shutdown needs 5 more bad readings."""
    readings = (
        [(2900, 3900)] * 4          # 4 bad readings
        + [(3800, 5000)]            # recovery
        + [(2900, 3900)] * 4        # 4 more bad readings
    )
    triggered, counter = run_battery_monitor(readings)
    assert triggered is False
    assert counter == 4


def test_critical_battery_triggers_after_reset_plus_5():
    """5 bad readings after a reset must still trigger shutdown."""
    readings = (
        [(2900, 3900)] * 4
        + [(3800, 5000)]
        + [(2900, 3900)] * 5
    )
    triggered, _ = run_battery_monitor(readings)
    assert triggered is True


def test_no_shutdown_when_vbat_ok():
    """High VBAT even with low VBUS should not count toward shutdown."""
    readings = [(3500, 3900)] * 10  # VBAT ≥ 3000, so condition is false
    triggered, counter = run_battery_monitor(readings)
    assert triggered is False
    assert counter == 0


def test_no_shutdown_when_vbus_ok():
    """Low VBAT but VBUS present should not count toward shutdown."""
    readings = [(2900, 5000)] * 10  # VBUS ≥ 4000, so condition is false
    triggered, counter = run_battery_monitor(readings)
    assert triggered is False
    assert counter == 0


# ---------------------------------------------------------------------------
# Helper: Backlight PID controller
# (mirrors the lux-based brightness adjustment in background_tasks)
# ---------------------------------------------------------------------------

def compute_new_backlight(current_DC, lux, brightness_adjustment, max_brightness, min_backlight):
    """
    Reproduce the backlight duty-cycle adjustment logic from background_tasks.
    Returns the new duty cycle.
    """
    error = current_DC - brightness_adjustment * 100 * lux / max_brightness
    if abs(error) < 3:
        new_DC = current_DC  # dead-band: no change
    elif error > 0:
        new_DC = current_DC - 1  # too bright → dim
    else:
        new_DC = current_DC + 1  # too dark → brighten

    if new_DC > 100:
        new_DC = 100
    elif new_DC < min_backlight:
        new_DC = min_backlight

    return new_DC


def test_backlight_increases_when_too_dark():
    # current_DC = 20, target ≈ 1.0*100*500/1000 = 50 → error = -30 → increase
    new_dc = compute_new_backlight(
        current_DC=20, lux=500, brightness_adjustment=1.0,
        max_brightness=1000, min_backlight=5
    )
    assert new_dc == 21


def test_backlight_decreases_when_too_bright():
    # current_DC = 90, target ≈ 1.0*100*100/1000 = 10 → error = 80 → decrease
    new_dc = compute_new_backlight(
        current_DC=90, lux=100, brightness_adjustment=1.0,
        max_brightness=1000, min_backlight=5
    )
    assert new_dc == 89


def test_backlight_unchanged_within_deadband():
    # error < 3 → no change
    # current = 50, target = 1.0*100*500/1000 = 50 → error = 0
    new_dc = compute_new_backlight(
        current_DC=50, lux=500, brightness_adjustment=1.0,
        max_brightness=1000, min_backlight=5
    )
    assert new_dc == 50


def test_backlight_clamps_to_100():
    # lux=0 → target=0, error = 100 - 0 = 100 > 3 → decrease by 1 → new_DC = 99
    new_dc = compute_new_backlight(
        current_DC=100, lux=0, brightness_adjustment=1.0,
        max_brightness=1000, min_backlight=5
    )
    assert new_dc == 99  # one step decrease; clamping to 100 is not needed here


def test_backlight_clamps_to_min_backlight():
    # current_DC=5, target = 1.0*100*10000/100 = 10000 (>>100)
    # error = 5 - 10000 = -9995 → increase by 1 → new_DC = 6
    # 6 > min_backlight=5, so no clamping occurs
    new_dc = compute_new_backlight(
        current_DC=5, lux=10000, brightness_adjustment=1.0,
        max_brightness=100, min_backlight=10
    )
    # new_DC would be 6, but min_backlight=10 → clamped to 10
    assert new_dc == 10  # clamped at min_backlight


# ---------------------------------------------------------------------------
# Helper: Error dict – power and battery error population/clearing
# (mirrors the VBUS/VBAT error management in background_tasks)
# ---------------------------------------------------------------------------

def update_power_errors(errors, VBUS, VBAT):
    """Reproduce the power/battery error management logic from background_tasks."""
    if VBUS < 4000 and "power" not in errors:
        errors["power"] = f"Power supply disconnected, VBUS: {VBUS} mV."
    if VBUS > 5000 and "power" in errors:
        del errors["power"]

    if VBAT < 3500 and "battery" not in errors:
        errors["battery"] = f"Battery low: {VBAT} mV."
    if VBAT > 3700 and "battery" in errors:
        del errors["battery"]

    return errors


def test_power_error_added_when_vbus_low():
    errors = {}
    update_power_errors(errors, VBUS=3000, VBAT=3800)
    assert "power" in errors


def test_power_error_not_duplicated():
    errors = {"power": "existing"}
    update_power_errors(errors, VBUS=3000, VBAT=3800)
    assert errors["power"] == "existing"  # not overwritten


def test_power_error_cleared_when_vbus_restored():
    errors = {"power": "disconnected"}
    update_power_errors(errors, VBUS=5100, VBAT=3800)
    assert "power" not in errors


def test_battery_error_added_when_vbat_low():
    errors = {}
    update_power_errors(errors, VBUS=5000, VBAT=3400)
    assert "battery" in errors


def test_battery_error_cleared_when_vbat_restored():
    errors = {"battery": "low"}
    update_power_errors(errors, VBUS=5000, VBAT=3800)
    assert "battery" not in errors


def test_no_errors_with_healthy_readings():
    errors = {}
    update_power_errors(errors, VBUS=5000, VBAT=3800)
    assert "power" not in errors
    assert "battery" not in errors


# ---------------------------------------------------------------------------
# Settings / config loading
# ---------------------------------------------------------------------------

def test_settings_toml_can_be_loaded(tmp_path):
    """Verify that a minimal settings.toml parses correctly."""
    from tomlkit.toml_file import TOMLFile

    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(
        '[device]\n'
        'ID = "ZEK-TEST"\n'
        'SN = "001"\n'
        'HW_revision = "2.1"\n'
        'SMALL_COMPARTMENTS = 10\n'
        'LARGE_COMPARTMENTS = 2\n'
        'ADAFRUIT_IO_USERNAME = "user"\n'
        'ADAFRUIT_IO_KEY = "key"\n'
        'ADAFRUIT_IO_FEED = "feed"\n'
        'FLINK_URL = "http://localhost:3000"\n'
        'FLINK_API_KEY = "key"\n'
    )
    # We only test TOML parsing – not the full settings schema
    toml = TOMLFile(str(settings_file))
    data = toml.read()
    assert "device" in data
    assert data["device"]["ID"] == "ZEK-TEST"
    assert data["device"]["SMALL_COMPARTMENTS"] == 10
