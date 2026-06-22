import hardware_V2 as hardware
import time
import colorsys

def hsv2rgb(h,s,v):
    return tuple(round(i * 255) for i in colorsys.hsv_to_rgb(h,s,v))

large_compartment_count = 1

hardware.init_port_expanders(large_compartment_count)

hardware.backlight.change_duty_cycle(50)

# rainbow effect
for i in range(50):
    for index in range(20):
        hardware.LED_connector_1.set_led_color(index, hsv2rgb(index/100+i/100,1,i/50))
    hardware.LED_connector_1.update_strip(0.001)
    time.sleep(0.03)
for i in range(50, 100):
    for index in range(20):
        hardware.LED_connector_1.set_led_color(index, hsv2rgb(index/100+i/100,1,1-(i-50)/50))
    hardware.LED_connector_1.update_strip(0.001)
    time.sleep(0.03)
hardware.LED_connector_1.clear_strip()
hardware.LED_connector_1.update_strip(0.001)

#hardware.compartments["21"].set_LEDs((0,0,0,255))
#hardware.LED_connector_3.set_led_color(LED, color[0], color[1], color[2], color[3]) 
#print(hardware.compartments["21"].open())
#time.sleep(2)
#hardware.compartments["21"].set_LEDs((0,0,0,0))




# hardware.light_sensor.light_gain = hardware.light_sensor.ALS_GAIN_2
# hardware.light_sensor.light_integration_time = hardware.light_sensor.ALS_800MS
# print("res")
# print(hardware.light_sensor.resolution())

# while True:
    # print(hardware.light_sensor.lux)
    # time.sleep(5)