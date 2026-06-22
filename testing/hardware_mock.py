#
# Schlüsselkasten V2 Hardware MOCK
#
# Drop-in replacement for hardware_V2.py for use in automated tests and
# desktop development.  No GPIO, I2C, SPI or RPi-specific packages required.
#
# Usage in main.py:
#   Replace:  import hardware_V2 as hardware
#   With:     import hardware_mock as hardware   (or the path-adjusted import)
#
# The mock exposes the same public interface as hardware_V2.py.  Configurable
# properties (e.g. VBUS, VBAT) allow tests to drive specific scenarios.
#

__version__ = "2.0.0-alpha2"

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Platform / identity stubs
# ---------------------------------------------------------------------------

nfc_serial = "COM1"


def get_cpu_serial():
    return "MOCK-CPU-SERIAL"


def get_cpu_model():
    return "Mock Hardware"


def get_ESSID():
    return "MockNetwork"


def get_RSSI():
    return "-50 dBm"


def get_sys_messages():
    return {}


def get_temp():
    return "40.0"


def uptime():
    return "up 1 day"


def get_memory_info():
    return "512/1024 MB"


# ---------------------------------------------------------------------------
# Backlight mock
# Records duty-cycle changes for test assertions.
# ---------------------------------------------------------------------------

class MockBacklight:
    def __init__(self, initial_dc=50):
        self._duty_cycle = initial_dc
        self._history = []  # list of duty cycles set

    def change_duty_cycle(self, dc):
        self._duty_cycle = dc
        self._history.append(dc)

    def start(self, dc):
        self.change_duty_cycle(dc)

    def stop(self):
        pass


backlight = MockBacklight()


# ---------------------------------------------------------------------------
# Piezo / haptic mocks
# ---------------------------------------------------------------------------

class MockPiezo:
    def __init__(self):
        self.beeps = []  # list of (duration, frequency)

    def change_frequency(self, freq):
        self._freq = freq

    def start(self, dc):
        pass

    def stop(self):
        pass


piezo = MockPiezo()
haptic = None


def beep(duration=0.1, frequency=1000):
    piezo.beeps.append((duration, frequency))


def trigger_haptic():
    pass


# ---------------------------------------------------------------------------
# Sensors
# ---------------------------------------------------------------------------

class MockLightSensor:
    """Configurable light sensor mock."""
    def __init__(self, lux=200.0):
        self.lux = lux


class MockBatteryMonitor:
    """
    Configurable battery-monitor mock.

    Set ``.VBUS`` and ``.VBAT`` to drive specific test scenarios.
    """
    def __init__(self, VBUS=5000, VBAT=3800):
        self.VBUS = VBUS
        self.VBAT = VBAT
        self._batfet_calls = []  # record calls to batfet_control

    def batfet_control(self, mode):
        self._batfet_calls.append(mode)


light_sensor = MockLightSensor()
battery_monitor = MockBatteryMonitor()
accelerometer = None
button = None


# ---------------------------------------------------------------------------
# Compartment mock
# ---------------------------------------------------------------------------

class MockCompartment:
    def __init__(self, is_open=False):
        self.door_status = "closed"
        self.content_status = "unknown"
        self.type = "small"
        self._is_open = is_open
        self._open_calls = 0

    def is_open(self):
        return self._is_open

    def get_inputs(self):
        return self._is_open

    def open(self, on_time=2):
        self._open_calls += 1
        self._is_open = True
        self.door_status = "open"
        return True

    def set_LEDs(self, color):
        pass


# ---------------------------------------------------------------------------
# Port expanders / compartments
# ---------------------------------------------------------------------------

port_expanders = []
compartments = {}


def init_port_expanders(large_compartments, num_small=20):
    """Populate ``compartments`` with mock objects."""
    global compartments
    compartments = {}
    for x in range(1, num_small + 1):
        compartments[str(x)] = MockCompartment()
    for x in range(num_small + 1, num_small + 1 + large_compartments):
        comp = MockCompartment()
        comp.type = "large"
        compartments[str(x)] = comp


def check_all():
    """Return list of compartment keys whose door is open."""
    return [k for k, c in compartments.items() if c.is_open()]


def open_all():
    for comp in compartments.values():
        comp.open()


def open_mounting():
    pass

