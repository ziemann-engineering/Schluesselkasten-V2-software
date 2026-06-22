#
# Schlüsselkasten V2 Hardware SETUP
#

import subprocess  # For executing a shell command
import logging
import time
from math import floor

import board
import digitalio
from adafruit_extended_bus import ExtendedI2C as I2C
from adafruit_mcp230xx.mcp23017 import MCP23017 # port expander
import adafruit_lis3dh # accelerometer
import adafruit_veml7700 # light sensor
import adafruit_drv2605 # haptic driver
from pi5neo import Pi5Neo as SPIneo
from rpi_hardware_pwm import HardwarePWM

import compartment
import bq25628 # battery charger / fuel gauge

logger = logging.getLogger(__name__)

# infos
__version__ = "2.0.0-beta5"


class Hardware:
    def __init__(self, settings):
        # Initialize compartments dict
        self.compartments = {}

        # serial for nfc reader, 3 on Hat V1.0, 4 on Hat V1.1
        self.nfc_serial = "/dev/ttyAMA4"

        # 4 separate buses on V2, using the ExtendedI2C class
        # for hat 1.0 / HW 2.0: 0 (EEPROM), 1 (conn 1), 4 (system devices) and 5 (conn 2)
        # for hat 1.1 / HW 2.1: 0 (EEPROM), 1 (system devices), 5 (conn 1) and 6 (conn 2)

        self.i2c_sys = I2C(1)  # 2.0: 4, 2.1: 1
        self.i2c_ext1 = I2C(5)  # 2.0: 1, 2.1: 5
        self.i2c_ext2 = I2C(6)  # 2.0: 5, 2.1: 6
        self.i2c_ee = I2C(0)  # 2.0: 0, 2.1: 0

        try:
            # PWM
            # display backlight
            self.backlight = HardwarePWM(pwm_channel=1, hz=10000, chip=0)
            self.backlight.start(50) 

            # piezo buzzer
            self.piezo = HardwarePWM(pwm_channel=0, hz=1000, chip=0)
        except Exception as e:
            self.backlight = None
            self.piezo = None
            logger.error(f"Error setting up PWM devices: {e}")

        # set up NFC interrupt pin
        self.nfc_int = digitalio.DigitalInOut(board.D25)
        self.nfc_int.direction = digitalio.Direction.INPUT

        # set up NFC reset pin
        self.nfc_rst = digitalio.DigitalInOut(board.D24) # does not exist on HW 2.0
        self.nfc_rst.direction = digitalio.Direction.OUTPUT
        self.nfc_rst.value = True

        # set up hapt trigger pin
        self.hapt_int = digitalio.DigitalInOut(board.D17) # 23 on HW v2.0, 17 on HW v2.1
        self.hapt_int.direction = digitalio.Direction.OUTPUT
        self.hapt_int.value = False

        # set up lock interrupt pin
        self.lock_int = digitalio.DigitalInOut(board.D27) # 22 on HW v2.0, 27 on HW v2.1
        self.lock_int.direction = digitalio.Direction.INPUT

        # set up on-hat button
        self.button = digitalio.DigitalInOut(board.D26) # does not exist on HW 2.0
        self.button.direction = digitalio.Direction.INPUT
        self.button.pull = digitalio.Pull.UP

        # set up charge disable pin
        self.CD = digitalio.DigitalInOut(board.D16) # does not exist on HW 2.0
        self.CD.direction = digitalio.Direction.OUTPUT
        self.CD.value = True  # disable charging

        ## LED config 
        self.LED_connector_1 = SPIneo('/dev/spidev0.0', 40, 1200)
        #self.LED_connector_2 = SPIneo('/dev/spidev4.0', 40, 1000)
        self.LED_connector_3 = SPIneo('/dev/spidev1.0', 3, 1000, "RGBW")

        self.LED_connector_1.clear_strip()
        self.LED_connector_1.update_strip(sleep_duration=0.001)
        #self.LED_connector_2.clear_strip()
        #self.LED_connector_2.update_strip(sleep_duration=0.001)
        self.LED_connector_3.clear_strip()
        self.LED_connector_3.update_strip(sleep_duration=0.001)


        try:
            self.haptic = adafruit_drv2605.DRV2605(self.i2c_sys) # 0x5A
            self.haptic.use_LRM()
            self.haptic.library = adafruit_drv2605.LIBRARY_LRA
            self.haptic.sequence[0] = adafruit_drv2605.Effect(26) # effect 1: strong click, 4: sharp click 100%, 5: sharp click 60%,  24: sharp tick, 25-26 weaker ticks,  27: short double click strong, 16: 1000 ms alert, 21: medium click, 
            self.haptic.mode = adafruit_drv2605.MODE_EXTTRIGEDGE
        except Exception as e:
            self.haptic = None
            logger.error(f"Error setting up haptic engine: {e}")
            
        # autocal results with DRIVE_TIME / 0x1B[4:0] = 25, RATED_VOLTAGE / reg 0x16 = 104, OD_CLAMP / 0x17 = 150
        # >>> haptic._read_u8(0x18)
        # 12
        # >>> haptic._read_u8(0x19)
        # 209
        # >>> haptic._read_u8(0x1A)
        # 182

        try:
            self.accelerometer = adafruit_lis3dh.LIS3DH_I2C(self.i2c_sys, address=0x19)
        except Exception as e:
            self.accelerometer = None
            logger.error(f"Error setting up accelerometer: {e}")

        try:
            self.light_sensor = adafruit_veml7700.VEML7700(self.i2c_sys) # 0x10 read: light_sensor.lux
            self.light_sensor.light_integration_time = self.light_sensor.ALS_400MS
            self.light_sensor.light_gain = self.light_sensor.ALS_GAIN_2
        except Exception as e:
            self.light_sensor = None
            logger.error(f"Error setting up brightness sensor: {e}")

        try: 
            self.battery_monitor = bq25628.BQ25628(self.i2c_sys) # 0x6A

            charger_status = self.battery_monitor.get_charger_status()  # read initial status
            fault_flags = self.battery_monitor.get_fault_flags()  # read initial fault flags

            if charger_status:
                logger.info(f"Battery monitor charger status: {charger_status}")
            if fault_flags:
                logger.info(f"Battery monitor fault flags: {fault_flags}")

            # configure battery monitor
            self.battery_monitor.set_charge_current(settings["charging_current"]) # mA
            self.battery_monitor.set_charge_voltage(settings["charging_voltage"]) # mV

            # check if battery is plugged in, only enable charging if battery is present
            self.battery_present = self.detect_battery()  
            if self.battery_present is False:
                self.battery_monitor.enable_charging(False) # should be already off from detect_battery()
            elif self.battery_present is True and settings["charging"] is True:
                self.battery_monitor.enable_charging(True)
            self.CD.value = False # enable charging in hardware and let software decide
            # self.battery_monitor.adc_enable(True) # already done in detect_battery()
            self.battery_monitor.enable_watchdog(False) # disable watchdog
        except Exception as e:
            self.battery_monitor = None
            logger.error(f"Error setting up battery monitor: {e}")

        # get connected port expanders on two buses (adresses from 0x20 to 0x27, prototype PCBs: 0x24 to 0x27)
        # first bus/connector        
        self.port_expanders = []
        for addr in range(0x20, 0x28):
            try:
                self.port_expanders.append(MCP23017(self.i2c_ext1, address=addr))
            except ValueError: # ValueError if device does not exist, ignore
                pass
        # second bus/connector      
        #for addr in range(0x20, 0x28):
        #    try:
        #        self.port_expanders.append(MCP23017(self.i2c_ext2, address=addr))
        #    except: # ValueError if device does not exist, ignore
        #        pass


    # initializes the port expanders and compartmnts
    # input: the number of desired large compartments
    # returns: the list of accessible/present compartments
    def init_port_expanders(self, large_compartments):
        # for V2, large compartments can be on connector 6 of each PCB
        # starting with PCB 1, going to 2 and 3 if 3 compartments are present
        # create compartment objects with IO ports, and a dict for all of them
        
        compartments_per_row = 5
        
        counter = 1
        # normal compartments, 1 to n*5 (n = number of port expanders)
        for index, expander in enumerate(self.port_expanders):
            # enable PCB activity LED
            LED_pin = expander.get_pin(15)
            LED_pin.direction = digitalio.Direction.OUTPUT
            LED_pin.value = True
            for compartment_per_expander in range(compartments_per_row):
                space = index * compartments_per_row + compartment_per_expander + 1
                
                input_pin = expander.get_pin(compartment_per_expander * 2)
                output_pin = expander.get_pin(compartment_per_expander * 2 + 1)
                new_compartment = compartment.compartment(input_pin, output_pin)
                new_compartment.LEDs = [space - 1]
                new_compartment.LED_connector = self.LED_connector_1
                self.compartments[f"{counter}"] = new_compartment
                counter += 1
                
        # large compartments, n*5 + 1 to n*5 + n (e.g. 21 to 24 for n = 4)
        for index in range(large_compartments):
            if len(self.port_expanders) > index:
                expander = self.port_expanders[index]
                input_pin = expander.get_pin(compartments_per_row * 2)
                output_pin = expander.get_pin(compartments_per_row * 2 + 1)
                new_compartment = compartment.compartment(input_pin, output_pin)
                new_compartment.LEDs = [index]
                new_compartment.LED_connector = self.LED_connector_3
                self.compartments[f"{counter}"] = new_compartment
                counter += 1

                
                
    # check door of all compartments
    def check_all(self):
        open_comps = []
        for index in range(len(self.compartments)):
            if self.compartments[str(index + 1)].is_open():
                open_comps.append(str(index + 1))
        return open_comps
        
    # open all compartments
    def open_all(self):
        for index in range(len(self.compartments)):
            self.compartments[str(index + 1)].open()
            
    # open compartments for mounting (block corners)
    def open_mounting(self):
        for block in range(floor(len(self.compartments) / 20)):
            self.compartments[f"{1+20*block}"].open()
            self.compartments[f"{5+20*block}"].open()
            self.compartments[f"{16+20*block}"].open()
            self.compartments[f"{20+20*block}"].open()
            
    def get_cpu_serial(self):
        try:
            with open("/sys/firmware/devicetree/base/serial-number") as f:
                return(f.read().strip('\x00'))
        except Exception as e:
            logger.warning(f"Error reading RPi serial: {e}")
            return "None"

    def get_cpu_model(self):
        try:
            with open("/sys/firmware/devicetree/base/model") as f:
                return(f.read().strip('\x00'))
        except Exception as e:
            logger.warning(f"Error reading cpu model: {e}")
            return "None"
            
    def get_ESSID(self):
        try:
            result = subprocess.run("iw dev wlan0 link | grep SSID", capture_output=True, text=True, shell=True)
            return result.stdout.strip()[6:]
        except Exception:
            return None
        
    def get_RSSI(self):
        try:
            result = subprocess.run("iw dev wlan0 link | grep signal", capture_output=True, text=True, shell=True)
            return result.stdout.strip()[8:]
        except Exception:
            return None
        
    def get_sys_messages(self):
        try:
            result = subprocess.run("vcgencmd get_throttled", capture_output=True, text=True, shell=True)
            
            hex_value = result.stdout.strip().split("=")[1]
            throttled = int(hex_value, 16)
            # Bit definitions
            status_bits = {
                0: "Under-voltage detected",
                1: "Arm frequency capped",
                2: "Currently throttled",
                3: "Soft temperature limit active",
                16: "Under-voltage occurred since last reboot",
                17: "Arm frequency capped since last reboot",
                18: "Throttling occurred since last reboot",
                19: "Soft temperature limit occurred"
            }
            messages = {}
            # Check each bit and print the status
            for bit, message in status_bits.items():
                if throttled & (1 << bit):
                    messages[bit] = message
            
            return messages
        except Exception:
            return None

    def get_temp(self):
        try:
            result = subprocess.run("vcgencmd measure_temp", capture_output=True, text=True, shell=True)
            return result.stdout.strip().split("=")[1][:-2]
        except Exception:
            return None
            
    def uptime(self):
        try:
            result = subprocess.run("uptime", capture_output=True, text=True, shell=True)
            return result.stdout.strip()
        except Exception:
            return None

    def beep(self, duration=0.1, frequency=2000):
        self.piezo.change_frequency(frequency)
        self.piezo.start(50)
        time.sleep(duration)
        self.piezo.stop()

    def get_memory_info(self):
        try:
            with open('/proc/meminfo') as f:
                mem_info = {}
                for line in f:
                    key, value = line.split(':')
                    mem_info[key.strip()] = int(value.strip().split()[0])  # Convert KB to MB
                return f"{mem_info['MemAvailable']//1024}/{mem_info['MemTotal']//1024} MB"
        except Exception as e:
            logger.warning(f"Error reading memory info: {e}")
            return "N/A"

    def trigger_haptic(self): # the haptic driver has an additional trigger pin
        self.hapt_int.value = True
        time.sleep(0.00001)
        self.hapt_int.value = False

    def detect_battery(self):
        if self.battery_monitor is None:
            return None
    # 1. Disable charging
        self.battery_monitor.enable_charging(False)
    # 2. Enable IBAT discharge current by writing FORCE_IBATDIS=1 (0x16[6]=1).
        self.battery_monitor.force_discharge(True)
    # 3. Wait approximately 5ms.
        time.sleep(0.005)
    # 4. Disable IBAT discharge current by writing FORCE_IBATDIS=0 (0x16[6]=0).
        self.battery_monitor.force_discharge(False)
    # 5. Set ADC to one-shot Mode and enable by writing ADC_RATE=1 (0x26[6]=1) & ADC_EN=1 (0x26[7]=1).
        self.battery_monitor.adc_enable(True)
    # 6. Readback VBAT ADC Value from 0x30.
        time.sleep(0.01)  # wait for ADC conversion
        if self.battery_monitor.VBAT < 3000:
            return False
        else:
            return True
