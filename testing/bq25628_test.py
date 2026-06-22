# Example usage
from adafruit_extended_bus import ExtendedI2C as I2C
import bq25628
import time

# Initialize the I2C bus
bus = I2C(1)  # Use 1 for Raspberry Pi /dev/i2c-1

# Create BQ25628 object
bq = bq25628.BQ25628(bus)

print("BQ25628 Charger Test")
print("ID:", bq.get_part_id())
print("Revision:", bq.get_part_rev())

# Set charge voltage to 4000mV
bq.set_charge_voltage(4000)

# Set charge current to 1000mA
bq.set_charge_current(1000)

bq.enable_charging(False)
time.sleep(2)
bq.enable_charging(True)

# Read status
status = bq.get_charger_status()
print(f"Charger status: {status}")

# Read ADC values
bq.adc_enable(True)
bq.adc_bits(12)

while True:
    a = time.monotonic()
    adc_values = bq.read_adc_values()
    b = time.monotonic()
    print(f"ADC read time: {b - a:.6f} seconds")
    print(f"ADC values: {adc_values}")
    time.sleep(1)