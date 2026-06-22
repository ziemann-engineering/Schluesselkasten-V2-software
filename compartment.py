# Ziemann Engineering Schlüsselkasten-Software
# compartment class, each compartment gets an object

# SPDX-FileCopyrightText: 2023 Thomas Ziemann for Ziemann Engineering
#
# SPDX-License-Identifier: GPL-3.0-or-later

import time
import digitalio

__version__ = "2.0.0-beta4"

maximum_on_time = 2 # set maximum lock on time
check_time = 0.1 # time to sleep between door checks

class compartment():
    def __init__(self, input_pin, output_pin): # initialize with one IO pair
        self.type = "small" # small, big (only one, set manually)
        self.door_status = "closed" # closed, open, error (e.g. detected open without command)
        self.content_status = "unknown" # present, empty, unknown (default on boot)
        self.LED_connector = None
        self.LEDs = None
        self.status_inputs = []
        self.lock_outputs = []
        self.add_input(input_pin)
        self.add_output(output_pin)

    # Setup input with a pull-up resistor enabled
    def add_input(self, input_pin):
        input_pin.direction = digitalio.Direction.INPUT
        input_pin.pull = digitalio.Pull.UP
        self.status_inputs.append(input_pin)

    # Setup output
    def add_output(self, output_pin):
        output_pin.direction = digitalio.Direction.OUTPUT
        output_pin.value = False
        self.lock_outputs.append(output_pin)

    def set_LEDs(self, color):
        for LED in self.LEDs:
            #self.LED_connector[LED] = color # V1
            # V2
            if color == "white":
                if self.LED_connector.colors == "RGBW":
                    self.LED_connector.set_led_color(LED, (0,0,0,255))
                else:
                    self.LED_connector.set_led_color(LED, (255,255,255))
            elif color == "off":
                if self.LED_connector.colors == "RGBW":
                    self.LED_connector.set_led_color(LED, (0,0,0,0))
                else:
                    self.LED_connector.set_led_color(LED, (0,0,0))
            else:
                try:
                    if len(color) == 3 and self.LED_connector.colors == "RGBW":
                        color = color + (0,)
                    if len(color) == 4 and self.LED_connector.colors == "RGB":
                        color = color[:3]                            
                    self.LED_connector.set_led_color(LED, color)
                except Exception:
                    pass
            self.LED_connector.update_strip(sleep_duration=0.001)                  
            
    def is_open(self):
        open = True
        for input in self.status_inputs:
            if not input.value: # count inputs which are low -> switch is pressed, door is closed (considered closed if one switch is pressed)
                open = False
        return open  # if sum > 0, door is closed

    def set_outputs(self, status):
        for output in self.lock_outputs:
            output.value = status

    def open(self, on_time=2):
        if on_time > maximum_on_time:
            on_time = maximum_on_time
        counter = on_time / check_time
        self.set_outputs(True)
        while counter > 0:
            time.sleep(check_time)# TODO: non-blocking?
            if self.is_open():
                break
            counter -= 1
        self.set_outputs(False)
        return self.is_open()
