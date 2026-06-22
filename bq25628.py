# BQ25628 I2C Battery Charger Driver
# Datasheet: https://www.ti.com/lit/ds/symlink/bq25628.pdf

from adafruit_bus_device import i2c_device

class BQ25628:
    # Device I2C address
    DEFAULT_ADDR = 0x6A

    # Register addresses (Table 8-7)
    REG_CHARGE_CURRENT_LIMIT   = 0x02  # Charge Current Limit (REG0x02)
    REG_CHARGE_VOLTAGE_LIMIT   = 0x04  # Charge Voltage Limit (REG0x04)
    REG_INPUT_CURRENT_LIMIT    = 0x06  # Input Current Limit (REG0x06)
    REG_INPUT_VOLTAGE_LIMIT    = 0x08  # Input Voltage Limit (REG0x08)
    REG_VOTG_REGULATION        = 0x0C  # VOTG regulation (REG0x0C)
    REG_MINIMAL_SYSTEM_VOLTAGE = 0x0E  # Minimal System Voltage (REG0x0E)
    REG_PRECHG_CONTROL         = 0x10  # Pre-charge Control (REG0x10)
    REG_TERMINATION_CONTROL    = 0x12  # Termination Control (REG0x12)
    REG_CHARGE_CONTROL         = 0x14  # Charge Control (REG0x14)
    REG_CHARGE_TIMER_CONTROL   = 0x15  # Charge Timer Control (REG0x15)
    REG_CHARGER_CONTROL_0      = 0x16  # Charger Control 0 (REG0x16)
    REG_CHARGER_CONTROL_1      = 0x17  # Charger Control 1 (REG0x17)
    REG_CHARGER_CONTROL_2      = 0x18  # Charger Control 2 (REG0x18)
    REG_CHARGER_CONTROL_3      = 0x19  # Charger Control 3 (REG0x19)
    REG_NTC_CONTROL_0          = 0x1A  # NTC Control 0 (REG0x1A)
    REG_NTC_CONTROL_1          = 0x1B  # NTC Control 1 (REG0x1B)
    REG_NTC_CONTROL_2          = 0x1C  # NTC Control 2 (REG0x1C)
    REG_CHARGER_STATUS_0       = 0x1D  # Charger Status 0 (REG0x1D)
    REG_CHARGER_STATUS_1       = 0x1E  # Charger Status 1 (REG0x1E)
    REG_FAULT_STATUS_0         = 0x1F  # FAULT Status 0 (REG0x1F)
    REG_CHARGER_FLAG_0         = 0x20  # Charger Flag 0 (REG0x20)
    REG_CHARGER_FLAG_1         = 0x21  # Charger Flag 1 (REG0x21)
    REG_FAULT_FLAG_0           = 0x22  # FAULT Flag 0 (REG0x22)
    REG_CHARGER_MASK_0         = 0x23  # Charger Mask 0 (REG0x23)
    REG_CHARGER_MASK_1         = 0x24  # Charger Mask 1 (REG0x24)
    REG_FAULT_MASK_0           = 0x25  # FAULT Mask 0 (REG0x25)
    REG_ADC_CONTROL            = 0x26  # ADC Control (REG0x26)
    REG_ADC_FUNC_DISABLE_0     = 0x27  # ADC Function Disable 0 (REG0x27)
    REG_IBUS_ADC               = 0x28  # IBUS ADC (REG0x28)
    REG_IBAT_ADC               = 0x2A  # IBAT ADC (REG0x2A)
    REG_VBUS_ADC               = 0x2C  # VBUS ADC (REG0x2C)
    REG_VPMID_ADC              = 0x2E  # VPMID ADC (REG0x2E)
    REG_VBAT_ADC               = 0x30  # VBAT ADC (REG0x30)
    REG_VSYS_ADC               = 0x32  # VSYS ADC (REG0x32)
    REG_TS_ADC                 = 0x34  # TS ADC (REG0x34)
    REG_TDIE_ADC               = 0x36  # TDIE ADC (REG0x36)
    REG_PART_INFORMATION       = 0x38  # Part Information (REG0x38)

    def __init__(self, i2c_bus, address=DEFAULT_ADDR):
        """
        Initialize BQ25628 device

        Args:
            i2c_bus: I2C bus object (implements read_byte_data/write_byte_data)
            address: I2C device address
        """

        self._i2c = i2c_device.I2CDevice(i2c_bus, address)
        self._buffer = bytearray(6)
        id = self.get_part_id()
        if id not in (2, 4, 6) or self.get_part_rev() != 2:
            print("Found part ID: {}, rev: {}".format(id, self.get_part_rev()))
            raise RuntimeError("Failed to find BQ25628/9 device at address 0x{:02X}".format(address))
        

    # general functions

    def _read_register(self, register: int, length=1) -> bytearray:
        # reads 1 (default) or more bytes from a register
        self._buffer[0] = register
        with self._i2c as i2c:
            i2c.write(self._buffer, start=0, end=1)
            i2c.readinto(self._buffer, start=0, end=length)
            return self._buffer[0:length]

    def _write_register(self, register: int, value: int, length=1) -> None:
        # writes 1 (default) or 2 bytes to a register
        self._buffer[0] = register & 0xFF
        self._buffer[1] = value & 0xFF
        if length == 2: # supports only 1 and 2 bytes (16 bit)
            self._buffer[2] = (value >> 8) & 0xFF
        
        with self._i2c as i2c:
            i2c.write(self._buffer, start=0, end=1+length)

    # charge current
    def set_charge_current(self, current_ma):
        """
        Charge current limit (REG0x02 ICHG)
        40 - 2000 mA
        Bit step 40 mA
        """
        val = int(current_ma / 40) << 5
        self._write_register(self.REG_CHARGE_CURRENT_LIMIT, val, 2)

    def get_charge_current(self):
        val = self._read_register(self.REG_CHARGE_CURRENT_LIMIT, 2)
        return (int.from_bytes(val, 'little') >> 5) * 40

    # charge voltage
    def set_charge_voltage(self, voltage_mv):
        """
        Charge voltage limit (REG0x04 VREG)
        3500 - 4800 mV
        Bit step 10 mV
        """
        val = int(voltage_mv // 10) << 3
        self._write_register(self.REG_CHARGE_VOLTAGE_LIMIT, val, 2)

    def get_charge_voltage(self):
        val = self._read_register(self.REG_CHARGE_VOLTAGE_LIMIT, 2)
        return (int.from_bytes(val, 'little') >> 3) * 10

    # input current limit
    def set_input_current_limit(self, iindpm_ma):
        """
        Input current limit (REG0x06 IINDPM)
        100 - 3200 mA
        Bit step 20 mA
        """
        val = int(iindpm_ma // 20) << 4
        self._write_register(self.REG_INPUT_CURRENT_LIMIT, val, 2)

    def get_input_current_limit(self):
        val = self._read_register(self.REG_INPUT_CURRENT_LIMIT, 2)
        return (int.from_bytes(val, 'little') >> 4) * 20
    
    # input voltage limit
    def set_input_voltage_limit(self, vindpm_mv):
        """
        Input voltage limit (REG0x08 VINDPM)
        3800 - 16800 mV
        Bit step 40 mV
        """
        val = int(vindpm_mv // 40) << 5
        self._write_register(self.REG_INPUT_VOLTAGE_LIMIT, val, 2)

    def get_input_voltage_limit(self):
        val = self._read_register(self.REG_INPUT_VOLTAGE_LIMIT, 2)
        return (int.from_bytes(val, 'little') >> 5) * 40
    
    # VOTG regulation
    def set_votg_regulation(self, voltage_mv):
        """
        VOTG regulation (REG0x0C VOTG)
        3840 - 5200 mV
        Bit step 80 mV
        """
        val = int(voltage_mv // 80) << 6
        self._write_register(self.REG_VOTG_REGULATION, val, 2)

    def get_votg_regulation(self):
        val = self._read_register(self.REG_VOTG_REGULATION, 2)
        return (int.from_bytes(val, 'little') >> 6) * 80

    # minimal system voltage
    def set_minimal_system_voltage(self, voltage_mv):   
        """
        Minimal system voltage (REG0x0E VMIN)
        2560 - 3840 mV
        Bit step 80 mV
        """
        val = int(voltage_mv // 80) << 6
        self._write_register(self.REG_MINIMAL_SYSTEM_VOLTAGE, val, 2)

    def get_minimal_system_voltage(self):
        val = self._read_register(self.REG_MINIMAL_SYSTEM_VOLTAGE, 2)
        return (int.from_bytes(val, 'little') >> 6) * 80

    # pre-charge control
    def set_precharge_current(self, current_ma):    
        """
        Pre-charge current (REG0x10 ICHG)
        10-310 mA
        Bit step 10 mA
        """
        val = int(current_ma // 10) << 3
        self._write_register(self.REG_PRECHG_CONTROL, val, 2)

    def get_precharge_current(self):
        val = self._read_register(self.REG_PRECHG_CONTROL, 2)
        return (int.from_bytes(val, 'little') >> 3) * 10
    
    # termination control
    def set_termination_current(self, current_ma):
        """
        Termination current (REG0x12 ITERM)
        10-310 mA
        Bit step 10 mA
        """
        val = int(current_ma // 10) << 3
        self._write_register(self.REG_TERMINATION_CONTROL, val, 2)  

    def get_termination_current(self):
        val = self._read_register(self.REG_TERMINATION_CONTROL, 2)
        return (int.from_bytes(val, 'little') >> 3) * 10

    # charge control
    def enable_charging(self, enable=True):
        reg = int.from_bytes(self._read_register(self.REG_CHARGER_CONTROL_0))
        if enable:
            reg |= 1 << 5
        else:
            reg &= ~(1 << 5)
        self._write_register(self.REG_CHARGER_CONTROL_0, reg)

    # watchdog control
    def enable_watchdog(self, enable=True):
        reg = int.from_bytes(self._read_register(self.REG_CHARGER_CONTROL_0))
        if enable:
            reg |= 0x01
        else:
            reg &= ~0x01
        self._write_register(self.REG_CHARGER_CONTROL_0, reg)

    # tempsense control (inverted logic)
    def enable_tempsense(self, enable=True):
        reg = int.from_bytes(self._read_register(self.REG_NTC_CONTROL_0))
        if enable:
            reg &= ~(1 << 7)
        else:
            reg |= 1 << 7
        self._write_register(self.REG_NTC_CONTROL_0, reg)

    # charger status
    def get_charger_status(self):
        """Read charger status registers (REG0x1D..0x1F range)"""
        status0 = self._read_register(self.REG_CHARGER_STATUS_0)
        status1 = self._read_register(self.REG_CHARGER_STATUS_1)
        status_fault = self._read_register(self.REG_FAULT_STATUS_0)
        return {
            'status0': status0,
            'status1': status1,
            'fault_status0': status_fault
        }

    def get_fault_flags(self):
        """Read fault/flag registers"""
        flag0 = self._read_register(self.REG_CHARGER_FLAG_0)
        flag1 = self._read_register(self.REG_CHARGER_FLAG_1)
        fault0 = self._read_register(self.REG_FAULT_FLAG_0)
        return {
            'flag0': flag0,
            'flag1': flag1,
            'fault0': fault0
        }

    # ADC functions
    def adc_enable(self, enable=True):
        reg = int.from_bytes(self._read_register(self.REG_ADC_CONTROL))
        if enable:
            reg |= 1 << 7
        else:
            reg &= ~(1 << 7)
        self._write_register(self.REG_ADC_CONTROL, reg)

    def adc_mode(self, mode="continuous"):
        reg = int.from_bytes(self._read_register(self.REG_ADC_CONTROL))
        if mode == "one-shot":
            reg |= 1 << 6
        elif mode == "continuous":
            reg &= ~(1 << 6)
        else:
            raise ValueError("Invalid ADC mode. Use 'one-shot' or 'continuous'.")
        self._write_register(self.REG_ADC_CONTROL, reg)

    def adc_bits(self, bits=9):
        reg = int.from_bytes(self._read_register(self.REG_ADC_CONTROL))
        mask = 0b11 << 4
        if bits == 9:
            pattern = 0b11 << 4
        elif bits == 10:    
            pattern = 0b10 << 4
        elif bits == 11:        
            pattern = 0b01 << 4
        elif bits == 12:        
            pattern = 0b00 << 4
        else:
            raise ValueError("Invalid ADC resolution. Use 9 to 12.")
        reg = (reg & ~mask) | (pattern & mask)
        self._write_register(self.REG_ADC_CONTROL, reg)

    def batfet_control(self, mode="normal"):
        reg = int.from_bytes(self._read_register(self.REG_CHARGER_CONTROL_2))
        mask = 0b11
        if mode == "normal":
            pattern = 0b00
        elif mode == "shutdown":
            pattern = 0b01
        elif mode == "ship":
            pattern = 0b10
        elif mode == "reset":
            pattern = 0b11
        else:
            raise ValueError("Invalid BATFET mode. Use 'normal', 'ship', 'shutdown' or 'reset'.")
        reg = (reg & ~mask) | (pattern & mask)
        self._write_register(self.REG_CHARGER_CONTROL_2, reg)

    def read_adc_values(self):
        """Read ADC registers according to Table 8-7"""
        return {
            'ibus': self.IBUS,
            'ibat': self.IBAT,
            'vbus': self.VBUS,
            'vpmid': self.VPMID,
            'vbat': self.VBAT,
            'vsys': self.VSYS,
            'ts': self.TS,
            'tdie': self.TDIE
        }
    
    @property
    def IBUS(self) -> int:
        return int.from_bytes(self._read_register(self.REG_IBUS_ADC, 2), 'little', signed=True)

    @property
    def IBAT(self) -> int:
        return int.from_bytes(self._read_register(self.REG_IBAT_ADC, 2), 'little', signed=True)
    
    @property
    def VBUS(self) -> int:
        return int.from_bytes(self._read_register(self.REG_VBUS_ADC, 2), 'little', signed=False)
    
    @property
    def VPMID(self) -> int:
        return int.from_bytes(self._read_register(self.REG_VPMID_ADC, 2), 'little', signed=False)

    @property   
    def VBAT(self) -> int:
        return int.from_bytes(self._read_register(self.REG_VBAT_ADC, 2), 'little', signed=False)

    @property
    def VSYS(self) -> int:
        return int.from_bytes(self._read_register(self.REG_VSYS_ADC, 2), 'little', signed=False)

    @property
    def TS(self) -> int:
        return int.from_bytes(self._read_register(self.REG_TS_ADC, 2), 'little', signed=False)

    @property
    def TDIE(self) -> int:
        return int.from_bytes(self._read_register(self.REG_TDIE_ADC, 2), 'little', signed=True)

    # part information
    def get_part_id(self):
        """Read part information (REG0x38)
        Reads:
        2 for BQ28628 - ILIM, OTG
        4 for BQ28628E - ILIM, no OTG
        6 for BQ28629 - USB, OTG
        """
        return (int.from_bytes(self._read_register(self.REG_PART_INFORMATION)) >> 3) & 0b111

    def get_part_rev(self):
        """Read part information (REG0x38)
        Should read 2
        """
        return int.from_bytes(self._read_register(self.REG_PART_INFORMATION)) & 0b111
