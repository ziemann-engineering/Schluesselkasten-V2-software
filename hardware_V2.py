#
# Schlüsselkasten V2 Hardware SETUP
#

import board
import digitalio
from adafruit_extended_bus import ExtendedI2C as I2C

from adafruit_mcp230xx.mcp23017 import MCP23017 # port expander
import adafruit_lis3dh # accelerometer
import adafruit_veml7700 # light sensor
import adafruit_drv2605 # haptic driver
import bq25628 # battery charger / fuel gauge

import subprocess  # For executing a shell command
import logging
import time

import compartment

from pi5neo import Pi5Neo as SPIneo

from rpi_hardware_pwm import HardwarePWM

from math import floor

from version import __version__

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardware revision configuration table
#
# Each key is the HW_revision string from settings.toml.
# Add a new entry here when a new hardware revision is introduced.
# ---------------------------------------------------------------------------
HW_CONFIGS = {
    "2.0": {
        "i2c_sys":    4,
        "i2c_ext1":   1,
        "i2c_ext2":   5,
        "hapt_pin":   board.D23,
        "lock_pin":   board.D22,
        "nfc_serial": "/dev/ttyAMA3",
    },
    "2.1": {
        "i2c_sys":    1,
        "i2c_ext1":   5,
        "i2c_ext2":   6,
        "hapt_pin":   board.D17,
        "lock_pin":   board.D27,
        "nfc_serial": "/dev/ttyAMA4",
    },
}

# ---------------------------------------------------------------------------
# Module-level globals — all set by setup(hw_revision).
# ---------------------------------------------------------------------------
backlight       = None
piezo           = None
haptic          = None
accelerometer   = None
light_sensor    = None
battery_monitor = None
button          = None
nfc_int         = None
nfc_rst         = None
hapt_int        = None
lock_int        = None
CD              = None
LED_connector_1 = None
LED_connector_3 = None
nfc_serial      = None

port_expanders = []
compartments   = {}


def setup(hw_revision):
    """Initialise all hardware peripherals.

    Must be called once from main.py after logging is configured, passing the
    HW_revision string read from settings.toml.  Falls back to revision "2.1"
    if an unknown revision string is given.
    """
    global backlight, piezo, haptic, accelerometer, light_sensor, battery_monitor
    global button, nfc_int, nfc_rst, hapt_int, lock_int, CD
    global LED_connector_1, LED_connector_3, nfc_serial

    cfg = HW_CONFIGS.get(hw_revision)
    if cfg is None:
        logger.warning(f"Unknown HW revision '{hw_revision}', falling back to '2.1'.")
        cfg = HW_CONFIGS["2.1"]

    nfc_serial = cfg["nfc_serial"]

    # I2C buses
    i2c_sys  = I2C(cfg["i2c_sys"])
    i2c_ext1 = I2C(cfg["i2c_ext1"])
    # i2c_ext2 = I2C(cfg["i2c_ext2"])  # second connector — not wired yet
    # i2c_ee   = I2C(0)                # EEPROM bus

    # PWM — display backlight
    backlight = HardwarePWM(pwm_channel=1, hz=10000, chip=0)
    backlight.start(50)

    # PWM — piezo buzzer
    piezo = HardwarePWM(pwm_channel=0, hz=1000, chip=0)

    # NFC interrupt pin
    nfc_int = digitalio.DigitalInOut(board.D25)
    nfc_int.direction = digitalio.Direction.INPUT

    # NFC reset pin (does not exist on HW 2.0)
    nfc_rst = digitalio.DigitalInOut(board.D24)
    nfc_rst.direction = digitalio.Direction.OUTPUT
    nfc_rst.value = True

    # Haptic trigger pin (revision-specific)
    hapt_int = digitalio.DigitalInOut(cfg["hapt_pin"])
    hapt_int.direction = digitalio.Direction.OUTPUT
    hapt_int.value = False

    # Lock interrupt pin (revision-specific)
    lock_int = digitalio.DigitalInOut(cfg["lock_pin"])
    lock_int.direction = digitalio.Direction.INPUT

    # On-hat button (does not exist on HW 2.0)
    button = digitalio.DigitalInOut(board.D26)
    button.direction = digitalio.Direction.INPUT
    button.pull = digitalio.Pull.UP

    # Charge disable pin (does not exist on HW 2.0)
    CD = digitalio.DigitalInOut(board.D16)
    CD.direction = digitalio.Direction.OUTPUT
    CD.value = False  # enable charging

    # LED connectors
    LED_connector_1 = SPIneo('/dev/spidev0.0', 40, 1200)
    # LED_connector_2 = SPIneo('/dev/spidev4.0', 40, 1000)
    LED_connector_3 = SPIneo('/dev/spidev1.0', 3, 1000, "RGBW")

    LED_connector_1.clear_strip()
    LED_connector_1.update_strip(sleep_duration=0.001)
    LED_connector_3.clear_strip()
    LED_connector_3.update_strip(sleep_duration=0.001)

    # Optional peripherals — log errors but continue if absent
    try:
        haptic = adafruit_drv2605.DRV2605(i2c_sys)  # 0x5A
        haptic.use_LRM()
        haptic.library = adafruit_drv2605.LIBRARY_LRA
        haptic.sequence[0] = adafruit_drv2605.Effect(26)
        haptic.mode = adafruit_drv2605.MODE_EXTTRIGEDGE
    except Exception as e:
        haptic = None
        logger.error(f"Error setting up haptic engine: {e}")

    try:
        accelerometer = adafruit_lis3dh.LIS3DH_I2C(i2c_sys, address=0x19)
    except Exception as e:
        accelerometer = None
        logger.error(f"Error setting up accelerometer: {e}")

    try:
        light_sensor = adafruit_veml7700.VEML7700(i2c_sys)  # 0x10
        light_sensor.light_integration_time = light_sensor.ALS_400MS
        light_sensor.light_gain = light_sensor.ALS_GAIN_2
    except Exception as e:
        light_sensor = None
        logger.error(f"Error setting up brightness sensor: {e}")

    try:
        battery_monitor = bq25628.BQ25628(i2c_sys)  # 0x6A
        battery_monitor.set_charge_current(500)   # mA
        battery_monitor.set_charge_voltage(4000)  # mV
        battery_monitor.adc_enable(True)
    except Exception as e:
        battery_monitor = None
        logger.error(f"Error setting up battery monitor: {e}")

    # Port expanders (addresses 0x20–0x27) on the first external I2C bus
    global port_expanders
    port_expanders = []
    for addr in range(0x20, 0x28):
        try:
            port_expanders.append(MCP23017(i2c_ext1, address=addr))
        except ValueError:  # device not present at this address
            pass

    logger.info(
        f"Hardware setup complete (revision {hw_revision}). "
        f"{len(port_expanders)} compartment PCB(s) detected."
    )


def init_port_expanders(large_compartments):
    """Initialise port expanders and create Compartment objects.

    Must be called after setup().
    """
    compartments_per_row = 5
    global compartments

    compartments = {}
    counter = 1

    # Standard compartments: 5 per port expander
    for index, expander in enumerate(port_expanders):
        LED_pin = expander.get_pin(15)
        LED_pin.direction = digitalio.Direction.OUTPUT
        LED_pin.value = True
        for compartment_per_expander in range(compartments_per_row):
            input_pin  = expander.get_pin(compartment_per_expander * 2)
            output_pin = expander.get_pin(compartment_per_expander * 2 + 1)
            new_compartment = compartment.Compartment(input_pin, output_pin)
            new_compartment.LEDs = [index * compartments_per_row + compartment_per_expander]
            new_compartment.LED_connector = LED_connector_1
            compartments[f"{counter}"] = new_compartment
            counter += 1

    # Large compartments: one per port expander row, connector 6
    for index in range(large_compartments):
        if len(port_expanders) > index:
            expander   = port_expanders[index]
            input_pin  = expander.get_pin(compartments_per_row * 2)
            output_pin = expander.get_pin(compartments_per_row * 2 + 1)
            new_compartment = compartment.Compartment(input_pin, output_pin)
            new_compartment.LEDs = [index]
            new_compartment.LED_connector = LED_connector_3
            compartments[f"{counter}"] = new_compartment
            counter += 1


def check_all():
    """Return a list of compartment keys whose door is currently open."""
    open_comps = []
    for index in range(len(compartments)):
        if compartments[str(index + 1)].is_open():
            open_comps.append(str(index + 1))
    return open_comps


def open_all():
    """Open every compartment."""
    for index in range(len(compartments)):
        compartments[str(index + 1)].open()


def open_mounting():
    """Open corner compartments used as mounting aids."""
    for block in range(floor(len(compartments) / 20)):
        compartments[f"{1  + 20 * block}"].open()
        compartments[f"{5  + 20 * block}"].open()
        compartments[f"{16 + 20 * block}"].open()
        compartments[f"{20 + 20 * block}"].open()


def get_cpu_serial():
    try:
        with open("/sys/firmware/devicetree/base/serial-number") as f:
            return f.read().strip('\x00')
    except Exception as e:
        logger.warning(f"Error reading RPi serial: {e}")
        return "None"


def get_cpu_model():
    try:
        with open("/sys/firmware/devicetree/base/model") as f:
            return f.read().strip('\x00')
    except Exception as e:
        logger.warning(f"Error reading cpu model: {e}")
        return "None"


def get_ESSID():
    try:
        result = subprocess.run(
            ["iw", "dev", "wlan0", "link"],
            capture_output=True, text=True,
        )
        for line in result.stdout.splitlines():
            if "SSID" in line:
                return line.strip()[6:]
    except Exception:
        pass
    return None


def get_RSSI():
    try:
        result = subprocess.run(
            ["iw", "dev", "wlan0", "link"],
            capture_output=True, text=True,
        )
        for line in result.stdout.splitlines():
            if "signal" in line:
                return line.strip()[8:]
    except Exception:
        pass
    return None


def get_sys_messages():
    try:
        result = subprocess.run(
            ["vcgencmd", "get_throttled"],
            capture_output=True, text=True,
        )
        hex_value = result.stdout.strip().split("=")[1]
        throttled = int(hex_value, 16)
        status_bits = {
            0:  "Under-voltage detected",
            1:  "Arm frequency capped",
            2:  "Currently throttled",
            3:  "Soft temperature limit active",
            16: "Under-voltage occurred since last reboot",
            17: "Arm frequency capped since last reboot",
            18: "Throttling occurred since last reboot",
            19: "Soft temperature limit occurred",
        }
        messages = {}
        for bit, message in status_bits.items():
            if throttled & (1 << bit):
                messages[bit] = message
        return messages
    except Exception:
        return None


def get_temp():
    try:
        result = subprocess.run(
            ["vcgencmd", "measure_temp"],
            capture_output=True, text=True,
        )
        return result.stdout.strip().split("=")[1][:-2]
    except Exception:
        return None


def uptime():
    try:
        result = subprocess.run(["uptime"], capture_output=True, text=True)
        return result.stdout.strip()
    except Exception:
        return None


def beep(duration=0.1, frequency=1000):
    piezo.change_frequency(frequency)
    piezo.start(50)
    time.sleep(duration)
    piezo.stop()


def get_memory_info():
    try:
        with open('/proc/meminfo') as f:
            mem_info = {}
            for line in f:
                key, value = line.split(':')
                mem_info[key.strip()] = int(value.strip().split()[0])
            return f"{mem_info['MemAvailable'] // 1024}/{mem_info['MemTotal'] // 1024} MB"
    except Exception as e:
        logger.warning(f"Error reading memory info: {e}")
        return "N/A"


def trigger_haptic():
    """Pulse the haptic trigger pin."""
    hapt_int.value = True
    time.sleep(0.00001)
    hapt_int.value = False
