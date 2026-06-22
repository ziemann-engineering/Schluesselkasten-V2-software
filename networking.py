from Adafruit_IO import MQTTClient
import logging
import sys

import subprocess  # For executing a shell command
import ping3

__version__ = "2.0.0-beta4"

logger = logging.getLogger(__name__)

# Global hardware instance
hardware = None


def ping():
    return ping3.ping("google.com", unit='ms')

#
# MQTT
#
mqtt = None

# Callback function which will be called when a connection is established
def connected(mqtt):
    mqtt.subscribe(mqtt.feed_name + "-command")

# Callback function which will be called when a message comes from a subscribed feed
def message(mqtt, feed_id, payload):
    if feed_id == (mqtt.feed_name + "-command"):
        process_mqtt_command(payload)
        
def disconnected(mqtt):
    # Disconnected function will be called when the mqtt disconnects.
    sys.exit(1)

def init_mqtt(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY, aio_feed_name, hardware_instance):
    global mqtt, hardware
    hardware = hardware_instance
    
    # Create an MQTT instance.
    mqtt = MQTTClient(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)
    
    # Setup the callback functions defined above.
    mqtt.on_connect    = connected
    mqtt.on_disconnect = disconnected
    mqtt.on_message    = message
    mqtt.feed_name = aio_feed_name

    connect_mqtt()
    
def connect_mqtt():    
    global mqtt
    try:
        # Connect to the Adafruit IO server.
        mqtt.connect()

        # Runs a thread in the background 
        mqtt.loop_background()
        return mqtt
    except Exception as e:
        logger.error(f"Error connecting to MQTT broker: {e}")
        return None
          

# process received command
def process_mqtt_command(payload):
    payload = payload.split(" ")
    command = payload[0]
    if command == "status" and len(payload) == 2:
        comp = payload[1]
        if comp == "all":
            logger.info(f"Open compartments: {hardware.check_all()}")
        elif int(comp) > 0 and int(comp) <= len(hardware.compartments):
            logger.info(f"Compartment {comp} status: door open: {hardware.compartments[comp].get_inputs()}, door status saved: {hardware.compartments[comp].door_status}, content status: {hardware.compartments[comp].content_status}.")
    elif command == "open" and len(payload) == 2:
        comp = payload[1]
        if comp == "all":
            hardware.open_all()
        elif int(comp) > 0 and int(comp) <= len(hardware.compartments):
            hardware.compartments[comp].open()
        logger.info(f"Compartment open sent from MQTT broker: {comp}")
    elif command == "restart" and len(payload) == 2:
        if payload[1] == "device":
            subprocess.run("sudo reboot now", shell=True)
        if payload[1] == "software":
            subprocess.run("./start.sh")
    #elif command == "service" and len(payload) == 1:    
       #UI.page_reconfigure(UI.service)
    #elif command == "tamper_alarm" and len(payload) == 2:
        # global tamper_alarm
        # if payload[1] == "off":
            # tamper_alarm = "off"
        # elif payload[1] == "on":
            # tamper_alarm = "on"

class AIOLogHandler(logging.Handler):
    def __init__(self, level):
        super().__init__(level)
    def emit(self, record):
        global mqtt
        try:
            mqtt.publish(mqtt.feed_name + "-status", self.format(record))
        except Exception as e:  # logging would trigger further exceptions
            print(f"Error when logging to MQTT broker: {e}")