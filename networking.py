from Adafruit_IO import MQTTClient
import logging

import subprocess  # For executing a shell command
import ping3

import hardware_V2 as hardware

from version import __version__

logger = logging.getLogger(__name__)

# Command token required as the first word of every MQTT command payload.
# Must match the MQTT_command_token value in secrets.toml.
_command_token = None


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
    # Do not exit — the background loop will attempt reconnection every 30 s.
    logger.warning("MQTT broker disconnected.")

def init_mqtt(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY, aio_feed_name, command_token):
    global mqtt, _command_token
    _command_token = command_token
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
    parts = payload.split()
    # First word must be the shared command token for authentication.
    if _command_token is None or not parts or parts[0] != _command_token:
        logger.warning("MQTT command rejected: missing or invalid token.")
        return
    # Shift past the token so existing command logic is unchanged.
    parts = parts[1:]
    if not parts:
        return
    command = parts[0]
    if command == "status" and len(parts) == 2:
        comp = parts[1]
        if comp == "all":
            logger.info(f"Open compartments: {hardware.check_all()}")
        else:
            try:
                comp_int = int(comp)
            except ValueError:
                logger.warning(f"MQTT status command rejected: invalid compartment '{comp}'.")
                return
            if 0 < comp_int <= len(hardware.compartments):
                logger.info(f"Compartment {comp} status: door open: {hardware.compartments[comp].is_open()}, door status saved: {hardware.compartments[comp].door_status}, content status: {hardware.compartments[comp].content_status}.")
    elif command == "open" and len(parts) == 2:
        comp = parts[1]
        if comp == "all":
            hardware.open_all()
        else:
            try:
                comp_int = int(comp)
            except ValueError:
                logger.warning(f"MQTT open command rejected: invalid compartment '{comp}'.")
                return
            if 0 < comp_int <= len(hardware.compartments):
                hardware.compartments[comp].open()
        logger.info(f"Compartment open sent from MQTT broker: {comp}")
    elif command == "restart" and len(parts) == 2:
        if parts[1] == "device":
            subprocess.run(["sudo", "reboot", "now"])
        if parts[1] == "software":
            subprocess.run(["./start.sh"])
    #elif command == "service" and len(parts) == 1:    
       #UI.page_reconfigure(UI.service)
    #elif command == "tamper_alarm" and len(parts) == 2:
        # global tamper_alarm
        # if parts[1] == "off":
            # tamper_alarm = "off"
        # elif parts[1] == "on":
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