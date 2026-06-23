import time
import platform
from tomlkit.toml_file import TOMLFile
import logging
import logging.handlers
import os
import threading

import ui
import hardware_V2 as hardware
#import hardware_mock as hardware
import flink as flink_module
import networking
from nfc import NFC

from version import __version__

# ---------------------------------------------------------------------------
# LOAD SETTINGS
# ---------------------------------------------------------------------------

toml = TOMLFile("assets/settings/settings.toml")
settings = toml.read()

secrets_toml = TOMLFile("assets/settings/secrets.toml")
secrets = secrets_toml.read()

ID               = settings["ID"]
SN               = settings["SN"]
HW_revision      = settings["HW_revision"]

small_compartments = settings["SMALL_COMPARTMENTS"]
large_compartments = settings["LARGE_COMPARTMENTS"]

localization = {}
lang_path = "assets/settings/"
lang_files = [f for f in os.listdir(lang_path) if f.startswith("lang_") and f.endswith(".toml")]

for lang_file in lang_files:
    lang_code = lang_file[5:-5]  # "lang_en.toml" -> "en"
    try:
        localization[lang_code] = TOMLFile(os.path.join(lang_path, lang_file)).read()
        print(f"Loaded language file: {lang_file}")
    except Exception as e:
        print(f"Error loading language file {lang_file}: {e}")

# ---------------------------------------------------------------------------
# LOGGING SETUP
# ---------------------------------------------------------------------------

# Filter consecutive duplicates to keep the log readable.
class DuplicateFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.counter = 0
        self.last_log = None

    def filter(self, record):
        current_log = (record.module, record.levelno, record.msg)
        if current_log != self.last_log:
            if self.counter > 0:
                logger.log(self.last_log[1], f"Last message repeated {self.counter} times.")
            self.last_log = current_log
            self.counter = 0
            return True
        self.counter += 1
        if self.counter % 100 == 0:
            logger.log(self.last_log[1], f"Last message repeated {self.counter} times.")
        return False

errors      = {}
errors_lock = threading.Lock()

logger = logging.getLogger()
logger.addFilter(DuplicateFilter())

# Rotating file handler — max 1 MB per file, keep 5 backups.
file_handler = logging.handlers.RotatingFileHandler(
    'schlüsselkasten.log',
    maxBytes=1_000_000,
    backupCount=5,
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)-8s %(name)-16s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
))
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)

logger.addHandler(flink_module.FlinkLogHandler(
    logging.ERROR, ID, secrets["FLINK_URL"], secrets["FLINK_API_KEY"]
))

networking.init_mqtt(
    secrets["ADAFRUIT_IO_USERNAME"],
    secrets["ADAFRUIT_IO_KEY"],
    secrets["ADAFRUIT_IO_FEED"],
    secrets["MQTT_command_token"],
)
logger.addHandler(networking.AIOLogHandler(logging.INFO))

flink = flink_module.Flink(ID, secrets["FLINK_URL"], secrets["FLINK_API_KEY"])

# ---------------------------------------------------------------------------
# INFO MESSAGES
# ---------------------------------------------------------------------------
logger.info("-------------")
logger.info(f"Ziemann Engineering Schlüsselkasten {ID}")
logger.info(f"Serial number {SN}, standard compartments: {small_compartments}, large compartments: {large_compartments}")
logger.info(f"Software: {__version__}, Python: {platform.python_version()}, OS: {platform.platform()}")
logger.info(f"Hardware revision: {HW_revision}")

# ---------------------------------------------------------------------------
# HARDWARE SETUP  (after logging so errors are captured in the log)
# ---------------------------------------------------------------------------

hardware.setup(HW_revision)

logger.info(f"CPU version: {hardware.get_cpu_model()}, CPU SN: {hardware.get_cpu_serial()}")
logger.info(f"CPU temperature: {hardware.get_temp()}°C")
logger.info(f"Network: {hardware.get_ESSID()}, Signal: {hardware.get_RSSI()}")

if hardware.battery_monitor is not None:
    logger.info(f"VBUS: {hardware.battery_monitor.VBUS:.0f} mV, VBAT {hardware.battery_monitor.VBAT:.0f} mV")

logger.info(f"{len(hardware.port_expanders)} compartment PCBs / rows detected.")
if len(hardware.port_expanders) * 5 < small_compartments:
    logger.error("Insufficient compartment PCBs detected.")
    with errors_lock:
        errors["compartments"] = "Insufficient compartment PCBs detected."

hardware.init_port_expanders(large_compartments)

try:
    nfc = NFC(secrets["NFC"], hardware.nfc_serial)
except Exception as e:
    nfc = None
    logger.error(f"Error setting up NFC: {e}")
    with errors_lock:
        errors["NFC"] = f"Error setting up NFC: {e}"

open_comps = hardware.check_all()
if len(open_comps) != 0:
    logger.warning(f"Open compartments: {open_comps}")

# ---------------------------------------------------------------------------
# HARDWARE WATCHDOG
#
# A daemon thread pets /dev/watchdog every 10 seconds.  If the process hangs
# completely (all threads stuck) the kernel will reboot the device after the
# watchdog's hardware timeout expires.
# ---------------------------------------------------------------------------

def _watchdog_loop(fd, interval=10):
    while True:
        try:
            os.write(fd, b'1')
        except OSError as e:
            logger.error(f"Watchdog write failed: {e}")
            break
        time.sleep(interval)

_watchdog_fd = None
if settings.get("hardware_watchdog", False):
    try:
        _watchdog_fd = os.open('/dev/watchdog', os.O_WRONLY)
        _watchdog_thread = threading.Thread(
            target=_watchdog_loop, args=(_watchdog_fd,), daemon=True, name="watchdog"
        )
        _watchdog_thread.start()
        logger.info("Hardware watchdog enabled.")
    except OSError as e:
        logger.warning(f"Could not open hardware watchdog (running without it): {e}")
else:
    logger.info("Hardware watchdog disabled (hardware_watchdog = false in settings.toml).")

# ---------------------------------------------------------------------------
# BACKGROUND TASKS
# ---------------------------------------------------------------------------

def background_tasks(ui):
    last_1s  = 0
    last_5s  = 0
    last_30s = 0
    next_5min = 0

    critical_battery_seconds = 0

    while True:
        while last_1s + 1 > time.time():
            time.sleep(0.1)
        last_1s = time.time()

        ### runs roughly every 5 minutes ###
        if next_5min < time.time():
            status_code = flink.put_status(time.monotonic(), SN, __version__, small_compartments, large_compartments)
            if status_code == 200:
                if next_5min == 0 or "flink" in errors:
                    logger.info(f"Response from Flink: {status_code}.")
                with errors_lock:
                    errors.pop("flink", None)
                next_5min = time.time() + 300
            else:
                logger.warning(f"Response from Flink: {status_code}.")
                with errors_lock:
                    errors["flink"] = f"Connection to flink failed: {status_code}."
                next_5min = time.time() + 30

        ### runs roughly every 30 s ###
        if time.time() > last_30s + 30:
            sys_messages = hardware.get_sys_messages()
            if sys_messages:
                with errors_lock:
                    changed = errors.get("rpi") != sys_messages
                    if changed:
                        errors["rpi"] = sys_messages
                if changed:
                    logger.warning(f"System messages: {sys_messages}.")
            else:
                with errors_lock:
                    errors.pop("rpi", None)

            ping = networking.ping()
            if isinstance(ping, float) and ping < 1000:
                if "ping" in errors or last_30s == 0:
                    logger.info(f"Ping to google: {ping:.1f} ms.")
                with errors_lock:
                    errors.pop("ping", None)
            else:
                logger.warning(f"Ping to google failed: {ping} ms.")
                with errors_lock:
                    errors["ping"] = f"Ping to google failed: {ping} ms."

            if networking.mqtt is None or not networking.mqtt.is_connected():
                networking.init_mqtt(
                    secrets["ADAFRUIT_IO_USERNAME"],
                    secrets["ADAFRUIT_IO_KEY"],
                    secrets["ADAFRUIT_IO_FEED"],
                    secrets["MQTT_command_token"],
                )
                if networking.mqtt is None or not networking.mqtt.is_connected():
                    with errors_lock:
                        errors["MQTT"] = "MQTT connection failed."
            else:
                with errors_lock:
                    errors.pop("MQTT", None)

            last_30s = time.time()

        ### runs roughly every 5 s ###
        if time.time() > last_5s + 5:
            ui.reconfigure_appbar()
            last_5s = time.time()

            if hardware.battery_monitor is not None:
                VBUS = hardware.battery_monitor.VBUS
                VBAT = hardware.battery_monitor.VBAT
                if VBUS < 4000 and "power" not in errors:
                    logger.warning(f"Power supply disconnected, VBUS: {VBUS} mV.")
                    with errors_lock:
                        errors["power"] = f"Power supply disconnected, VBUS: {VBUS} mV."
                if VBUS > 5000:
                    with errors_lock:
                        errors.pop("power", None)
                if VBAT < 3500 and "battery" not in errors:
                    logger.warning(f"Battery low: {VBAT} mV.")
                    with errors_lock:
                        errors["battery"] = f"Battery low: {VBAT} mV."
                if VBAT > 3700:
                    with errors_lock:
                        errors.pop("battery", None)
                if VBAT < 3000 and VBUS < 4000:
                    critical_battery_seconds += 1
                    if critical_battery_seconds >= 5:
                        logger.error(f"Battery critically low: {VBAT} mV.")
                        logger.error("Shutting down, apply power to restart.")
                        time.sleep(1)
                        hardware.battery_monitor.batfet_control("ship")
                else:
                    critical_battery_seconds = 0

        ### runs roughly every second ###
        # backlight control
        if hardware.light_sensor is not None:
            try:
                current_DC = hardware.backlight._duty_cycle
                new_DC = current_DC  # default: no change
                error = current_DC - settings["brightness_adjustment"] * 100 * hardware.light_sensor.lux / settings["max_brightness"]
                if error > 3:
                    new_DC = current_DC - 1
                elif error < -3:
                    new_DC = current_DC + 1

                new_DC = max(settings["min_backlight"], min(100, new_DC))
                if new_DC != current_DC:
                    hardware.backlight.change_duty_cycle(new_DC)

                with errors_lock:
                    errors.pop("lux", None)
            except Exception as e:
                logger.error(f"Error getting ambient brightness: {e}")
                with errors_lock:
                    errors["lux"] = f"Error getting ambient brightness: {e}"
        else:
            hardware.backlight.change_duty_cycle(80 * settings["brightness_adjustment"])

        # info page update (if open)
        if ui.info in ui.page:
            ui.update_info()
            ui.page.update()

        # check if NFC tag is present
        if (ui.returning in ui.page or ui.welcome in ui.page) and nfc is not None:
            try:
                uid = nfc.check()
                if uid is not None:
                    for comp, comp_tags in settings["NFC-tags"].items():
                        if uid in comp_tags:
                            if comp == "service":
                                logging.info(f"NFC service tag with UID {uid} was scanned.")
                                ui.page_reconfigure(ui.service)
                                ui.beep_success()
                            else:
                                ui.open_compartment(comp, "return")
                                logging.info(f"NFC tag for compartment {comp} with UID {uid} was scanned.")
                else:
                    with errors_lock:
                        errors.pop("NFC", None)
            except Exception as e:
                logger.warning(f"Error checking NFC tag: {e}")
                with errors_lock:
                    errors["NFC"] = f"Error checking NFC tag: {e}"

        # check for on-hat button press to open settings
        if hardware.button is not None and not hardware.button.value:
            ui.page_reconfigure(ui.service)
            ui.beep_success()

# ---------------------------------------------------------------------------
# START GUI
# ---------------------------------------------------------------------------

ui.start_GUI(settings, toml, localization, flink, nfc, errors, errors_lock, background_tasks)
