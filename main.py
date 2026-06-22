import time
import platform
from tomlkit.toml_file import TOMLFile
import logging
import os

import ui
import hardware_V2 as hardware
#import hardware_mock as hardware
import flink
import networking
from nfc import NFC

# version string
__version__ = "2.0.0-beta5"

# background tasks function
def background_tasks(ui):
    # last time tasks were run
    last_1s = 0 # fastest task, 1 or 2 times per second
    last_5s = 0
    last_30s = 0
    next_5min = 0 # slowest task, every 5 minutes, every 30s in case of error

    critical_battery_seconds = 0  # counter for critical battery shutdown
    
    # check tasks once per second
    while True:
        while last_1s + 1 > time.time():
            time.sleep(0.1)
        last_1s = time.time()
        
        ### runs roughly every 5 minutes,  ###
        if next_5min < time.time():  
            # send keepalive message
            status_code = flink.put_status(time.monotonic(), SN, __version__, small_compartments, large_compartments)
            if status_code == 200:
                if next_5min == 0 or "flink" in errors:
                    logger.info(f"Response from Flink: {status_code}.")
                if "flink" in errors:
                    del errors["flink"]
                next_5min = time.time() + 300
            else:
                logger.warning(f"Response from Flink: {status_code}.")
                errors["flink"] = f"Connection to flink failed: {status_code}."   
                next_5min = time.time() + 30  # try again in 30s if error

        ### runs roughly every 30 s ###
        if time.time() > last_30s + 30:
            # check for raspberry pi hardware messages
            sys_messages = hardware.get_sys_messages()
            if sys_messages:
                if "rpi" not in errors or errors["rpi"] != sys_messages:
                    errors["rpi"] = sys_messages
                    logger.warning(f"System messages: {sys_messages}.")
            elif "rpi" in errors:
                del errors["rpi"]
                
            # check network connection with ping
            ping = networking.ping()
            if isinstance(ping, float) and ping < 1000:        
                if "ping" in errors or last_30s == 0:
                    logger.info(f"Ping to google: {ping:.1f} ms.")
                if "ping" in errors:
                    del errors["ping"]
            else:
                logger.warning(f"Ping to google failed: {ping} ms.")
                errors["ping"] = f"Ping to google failed: {ping} ms."

            # check if MQTT is ok, reconnect if necessary
            if networking.mqtt is None or not networking.mqtt.is_connected():
                networking.init_mqtt(settings["ADAFRUIT_IO_USERNAME"], settings["ADAFRUIT_IO_KEY"], settings["ADAFRUIT_IO_FEED"])
                if networking.mqtt is None or not networking.mqtt.is_connected(): # still not?
                    errors["MQTT"] = "MQTT connection failed."
            elif "MQTT" in errors:
                del errors["MQTT"]
            
            last_30s = time.time()
        
        ### runs roughly every 5 s ### 
        # info bar update (if errors)
        if time.time() > last_5s + 5:
            ui.reconfigure_appbar()
            last_5s = time.time()

            # check supply status
            if hardware.battery_monitor is not None:
                VBUS = hardware.battery_monitor.VBUS
                VBAT = hardware.battery_monitor.VBAT
                if VBUS < 4000 and "power" not in errors:
                    logger.warning(f"Power supply disconnected, VBUS: {VBUS} mV.")
                    errors["power"] = f"Power supply disconnected, VBUS: {VBUS} mV."
                if VBUS > 5000:
                    if "power" in errors:
                        del errors["power"]
                if VBAT < 3500 and "battery" not in errors:
                    logger.warning(f"Battery low: {VBAT} mV.")
                    errors["battery"] = f"Battery low: {VBAT} mV."
                if VBAT > 3700:
                    if "battery" in errors:
                        del errors["battery"] 
                if VBAT < 3000 and VBUS < 4000:
                    critical_battery_seconds += 1
                    if critical_battery_seconds >= 5: # 5 consecutive low readings
                        logger.error(f"Battery critically low: {VBAT} mV.")
                        logger.error("Shutting down, apply power to restart.")
                        time.sleep(1)
                        hardware.battery_monitor.batfet_control("shipmode")
                else:
                    critical_battery_seconds = 0
        
        ### runs roughly every second ###
        # backlight control
        if hardware.light_sensor is not None:
            try:
                # calculate new duty cycle
                current_DC = hardware.backlight._duty_cycle
                error = current_DC - settings["brightness_adjustment"]*100*hardware.light_sensor.lux/(settings["max_brightness"]) # positive - display too bright
                if abs(error) < 3: 
                    pass # do nothing if less than 3% off
                elif error > 0:
                    new_DC = current_DC - 1
                else:
                    new_DC = current_DC + 1

                if new_DC > 100:
                    new_DC = 100
                elif new_DC < settings["min_backlight"]:
                    new_DC = settings["min_backlight"]
                hardware.backlight.change_duty_cycle(new_DC)

                if "lux" in errors:
                    del errors["lux"]
            except Exception as e:
                logger.error(f"Error getting ambient brightness: {e}")
                ui.errors["lux"] = f"Error getting ambient brightness: {e}"
        else: # no sensor found, do 80% tied to brightness adjustment setting
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
                elif "NFC" in errors:
                    del errors["NFC"]
            except Exception as e:
                logger.warning(f"Error checking NFC tag: {e}")
                ui.errors["NFC"] = f"Error checking NFC tag: {e}"

        #check for on-hat button press to open settings
        if hardware.button is not None and not hardware.button.value:
            ui.page_reconfigure(ui.service)
            ui.beep_success()

                

        # check accelerometer?

        # check for lock status changes?
          
                       
#
# LOAD SETTINGS
#

toml = TOMLFile("assets/settings/settings.toml")
settings = toml.read()
ID = settings["ID"]
SN = settings["SN"]
HW_revision = settings["HW_revision"]

small_compartments = settings["SMALL_COMPARTMENTS"]
large_compartments = settings["LARGE_COMPARTMENTS"]

aio_username = settings["ADAFRUIT_IO_USERNAME"]
aio_key = settings["ADAFRUIT_IO_KEY"]
aio_feed_name = settings["ADAFRUIT_IO_FEED"]

localization = {}
lang_path = "assets/settings/"
lang_files = [f for f in os.listdir(lang_path) if f.startswith("lang_") and f.endswith(".toml")]

for lang_file in lang_files:
    # Extract language code from filename (e.g., "lang_en.toml" -> "en")
    lang_code = lang_file[5:-5]  
    try:
        localization[lang_code] = TOMLFile(os.path.join(lang_path, lang_file)).read()
        print(f"Loaded language file: {lang_file}")
    except Exception as e:
        print(f"Error loading language file {lang_file}: {e}")
        
#
# LOGGING SETUP
#

# filter duplicates
class DuplicateFilter(logging.Filter):
    counter = 0
    def filter(self, record):
        # add other fields if you need more granular comparison, depends on your app
        current_log = (record.module, record.levelno, record.msg)
        if current_log != getattr(self, "last_log", None):
            self.last_log = current_log
            if self.counter > 0:
                logger.log(self.last_log[1], f"Last message repeated {self.counter} times.")
            self.counter = 0
            return True
        self.counter +=1
        if self.counter%100 == 0:
            logger.log(self.last_log[1], f"Last message repeated {self.counter} times.")
        return False

errors = {}
 
# open local logfile
logger = logging.getLogger()
logger.addFilter(DuplicateFilter())  # add the filter to it

logging.basicConfig(filename='schlüsselkasten.log',
    format='%(asctime)s %(levelname)-8s %(name)-16s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

#logger.info("Logging to disk started.")

logger.addHandler(flink.FlinkLogHandler(logging.ERROR, ID, settings["FLINK_URL"], settings["FLINK_API_KEY"]))
#logger.info("Logging to Flink started.")

networking.init_mqtt(settings["ADAFRUIT_IO_USERNAME"], settings["ADAFRUIT_IO_KEY"], settings["ADAFRUIT_IO_FEED"])
logger.addHandler(networking.AIOLogHandler(logging.INFO))
#logger.info("Logging to MQTT broker started.")

flink = flink.Flink(ID, settings["FLINK_URL"], settings["FLINK_API_KEY"])

#
# INFO MESSAGES
#
logger.info("-------------")
logger.info(f"Ziemann Engineering Schlüsselkasten {ID}")
logger.info(f"Serial number {SN}, standard compartments: {small_compartments}, large compartments: {large_compartments}")
logger.info(f"Software: {__version__}, Python: {platform.python_version()}, OS: {platform.platform()}")
logger.info(f"Hardware revision: {HW_revision}")
logger.info(f"CPU version: {hardware.get_cpu_model()}, CPU SN: {hardware.get_cpu_serial()}")
logger.info(f"CPU temperature: {hardware.get_temp()}°C")
logger.info(f"Network: {hardware.get_ESSID()}, Signal: {hardware.get_RSSI()}")

#logger.info(f"Reset reason: {str(microcontroller.cpu.reset_reason).split('.')[2]}, run reason: {str(supervisor.runtime.run_reason).split('.')[2]}")


#
# HARDWARE SETUP
#

if hardware.battery_monitor is not None:
    logger.info(f"VBUS: {hardware.battery_monitor.VBUS:.0f} mV, VBAT {hardware.battery_monitor.VBAT:.0f} mV")

logger.info(f"{len(hardware.port_expanders)} compartment PCBs / rows detected.")
if len(hardware.port_expanders)*5 < small_compartments:
    logger.error("Insufficient compartment PCBs detected.")
    errors["compartments"] = "Insufficient compartment PCBs detected."

# initialize the compartment PCBs / port expanders
hardware.init_port_expanders(large_compartments)

try: 
    nfc = NFC(settings["NFC"], hardware.nfc_serial)
except Exception as e:
    nfc = None
    logger.error(f"Error setting up NFC: {e}")
    errors["NFC"] = f"Error setting up NFC: {e}"
    
open_comps = hardware.check_all()
if len(open_comps) != 0:
    logger.warning(f"Open compartments: {open_comps}")

#
# Start GUI
#

ui.start_GUI(settings, toml, localization, flink, nfc, errors, background_tasks)