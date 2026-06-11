# Schlüsselkasten V2 Software

Software for the Ziemann Engineering Schlüsselkasten (key cabinet) V2. This project provides general documentation for potential open-source collaboration.

## Overview

The Schlüsselkasten is a smart key cabinet that manages access to multiple compartments via NFC tags and PIN codes. It integrates with [Flink](https://flink.coop) — an external platform for building cooperatives — to manage valid access codes and log usage events. The specific Flink instance used is [maw.flink.coop](https://maw.flink.coop).

**Current version:** 2.0.0-beta5

## Features

- Compartment management (small and large compartments) with motorised locks and door status detection
- NFC authentication using MIFARE DESFire cards with AES key diversification
- PIN code validation via the Flink REST API
- Ambient light sensor for automatic display backlight adjustment
- Haptic feedback (LRA motor driver)
- Battery monitoring and charge management (BQ25628)
- LED strip control per compartment (RGB/RGBW via SPI)
- Remote logging via Flink REST API and Adafruit IO MQTT
- Systemd user service for automatic start-up

## Hardware

The target hardware is a **Raspberry Pi 4** with a custom Ziemann Engineering hat (HW revision 2.1). The software uses the `pi5neo` library for SPI-based LED control, which was originally written for the Raspberry Pi 5 but also runs on the Raspberry Pi 4.

Several I2C buses are used for on-hat peripherals and may be specific to the Raspberry Pi 4:

| Bus | Purpose |
|-----|---------|
| I2C-0 | EEPROM |
| I2C-1 | System devices (accelerometer, light sensor, haptic driver, battery monitor) |
| I2C-5 | Compartment PCB connector 1 (MCP23017 port expanders) |
| I2C-6 | Compartment PCB connector 2 (MCP23017 port expanders) |

SPI buses are used for the LED strips (`/dev/spidev0.0` and `/dev/spidev1.0`). UART4 (`/dev/ttyAMA4`) is used for the NFC reader.

## Software Requirements

### Operating System

Raspberry Pi OS **Bookworm** (64-bit). Some features may be Bookworm-specific. The default Python version shipped with Pi OS Bookworm is used.

### Python Dependencies

Key libraries (see `requirements.txt` for the full list frozen from Pi OS Bookworm):

- `adafruit-circuitpython-mcp230xx` — MCP23017 port expanders
- `adafruit-circuitpython-lis3dh` — accelerometer
- `adafruit-circuitpython-veml7700` — ambient light sensor
- `adafruit-circuitpython-drv2605` — haptic driver
- `adafruit-extended-bus` — extended I2C bus support
- `pi5neo` — SPI NeoPixel/LED strip control
- `rpi-hardware-pwm` — hardware PWM for backlight and buzzer
- `rpi-lgpio` — GPIO access
- `smbus2` — I2C/SMBus communication
- `requests` — Flink REST API communication
- `Adafruit-IO` — MQTT client for Adafruit IO
- `ping3` — network connectivity check
- `python-dotenv` / `tomlkit` — configuration file handling
- `desfire` — MIFARE DESFire NFC card library

### Virtual Environment

It is recommended to set up a Python virtual environment:

```bash
python -m venv ~/SKV2-env
source ~/SKV2-env/bin/activate
pip install -r requirements.txt
```

## Configuration

Configuration is stored in `assets/settings/settings.toml` (excluded from version control via `.gitignore`). A template for this file is **TODO**.

Required settings include:

- `ID` — device identifier used in Flink API calls
- `SN` — device serial number
- `HW_revision` — hardware revision string
- `SMALL_COMPARTMENTS` — number of standard compartments
- `LARGE_COMPARTMENTS` — number of large compartments
- `FLINK_URL` — base URL of the Flink instance (e.g. `https://your-flink-instance.flink.coop`)
- `FLINK_API_KEY` — API key for Flink authentication
- `ADAFRUIT_IO_USERNAME` — Adafruit IO username for MQTT logging
- `ADAFRUIT_IO_KEY` — Adafruit IO API key
- `ADAFRUIT_IO_FEED` — Adafruit IO feed name
- `NFC` — NFC settings (master key, app ID, system ID)
- `NFC-tags` — mapping of NFC tag UIDs to compartment numbers for tag-based access (note: key name uses a hyphen as required by the TOML parser)
- `brightness_adjustment`, `max_brightness`, `min_backlight` — display backlight tuning

Localisation strings are loaded from `assets/settings/lang_<code>.toml` files (e.g. `lang_en.toml`, `lang_de.toml`).

## Running

### Manual Start

```bash
cd ~/Schluesselkasten-V2-software
./start.sh
```

The start script kills any existing instances, configures GPIO pins, activates the virtual environment and starts `main.py`.

### Systemd Service

The software can be run as a systemd user service that starts automatically on boot and restarts on failure:

```bash
ln -s ~/Schluesselkasten-V2-software/schluesselkasten.service ~/.config/systemd/user/schluesselkasten.service
systemctl --user daemon-reload
systemctl --user enable schluesselkasten.service
systemctl --user start schluesselkasten.service
```

Useful service commands:

```bash
systemctl --user status schluesselkasten.service
systemctl --user restart schluesselkasten.service
journalctl --user -u schluesselkasten.service -f
```

### Manual Stop

```bash
./stop.sh
```

## Project Structure

| File | Description |
|------|-------------|
| `main.py` | Entry point: loads config, sets up logging, starts background tasks and GUI |
| `hardware_V2.py` | Hardware abstraction: I2C, SPI, PWM, GPIO, LEDs, sensors |
| `compartment.py` | Compartment class: lock control, door status, LED assignment |
| `nfc.py` | NFC reader interface: card check, personalisation, format |
| `flink.py` | Flink REST API client and logging handler |
| `networking.py` | MQTT client and ping connectivity check |
| `ui.py` | Graphical user interface |
| `bq25628.py` | Battery charger / fuel gauge driver (BQ25628) |
| `schluesselkasten.service` | Systemd user service unit file |
| `start.sh` / `stop.sh` | Helper scripts to start and stop the application |
| `assets/` | UI assets and settings files |
| `testing/` | Test scripts |

## License

TODO
