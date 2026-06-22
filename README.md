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
- Hardware watchdog to recover from complete hangs (requires `dtparam=watchdog=on` in `/boot/config.txt`)
- Rotating log file (1 MB × 5 backups) to prevent SD card exhaustion
- Systemd user service for automatic start-up

## Hardware

The target hardware is a **Raspberry Pi 4** with a custom Ziemann Engineering hat. Two hat revisions are supported and selected automatically via `HW_revision` in `settings.toml`:

| Revision | I2C sys | I2C ext1 | I2C ext2 | Haptic pin | NFC UART |
|----------|---------|----------|----------|------------|----------|
| 2.0      | I2C-4   | I2C-1    | I2C-5    | GPIO 23    | ttyAMA3  |
| 2.1      | I2C-1   | I2C-5    | I2C-6    | GPIO 17    | ttyAMA4  |

The software uses the `pi5neo` library for SPI-based LED control, which was originally written for the Raspberry Pi 5 but also runs on the Raspberry Pi 4.

| Bus / Interface | Purpose |
|-----------------|---------|
| I2C sys         | System devices: accelerometer (LIS3DH), light sensor (VEML7700), haptic driver (DRV2605), battery monitor (BQ25628) |
| I2C ext1/ext2   | Compartment PCBs — MCP23017 port expanders (up to 8 per bus) |
| `/dev/spidev0.0` | LED strip, compartment LEDs (RGB) |
| `/dev/spidev1.0` | LED strip, large compartment LEDs (RGBW) |
| UART (see table) | NFC reader (PN532) |

## Software Requirements

### Operating System

Raspberry Pi OS **Bookworm** (64-bit). Some features may be Bookworm-specific. The default Python version shipped with Pi OS Bookworm is used.

### Python Dependencies

`requirements.txt` lists the curated set of project dependencies. Install them into a virtual environment:

```bash
python -m venv ~/SKV2-env
source ~/SKV2-env/bin/activate
pip install -r requirements.txt
```

Key libraries:

- `flet` — GUI framework
- `tomlkit` — TOML configuration file handling
- `adafruit-blinka` — CircuitPython hardware abstraction layer (provides `board`, `digitalio`, etc.)
- `adafruit-circuitpython-mcp230xx` — MCP23017 port expanders
- `adafruit-circuitpython-lis3dh` — accelerometer
- `adafruit-circuitpython-veml7700` — ambient light sensor
- `adafruit-circuitpython-drv2605` — haptic driver
- `pi5neo` — SPI NeoPixel/LED strip control
- `rpi-hardware-pwm` — hardware PWM for backlight and buzzer
- `adafruit-io` — MQTT client for Adafruit IO
- `ping3` — network connectivity check
- `requests` — Flink REST API communication
- `desfire` — MIFARE DESFire NFC card library

### Test Dependencies

`requirements-dev.txt` lists additional packages needed to run the automated test suite locally:

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

## Configuration

Settings are split across two TOML files in `assets/settings/`:

### `settings.toml`

Non-sensitive device configuration. **No template is provided yet (TODO).**

| Key | Description |
|-----|-------------|
| `ID` | Device identifier used in Flink API calls |
| `SN` | Device serial number |
| `HW_revision` | Hardware revision string — `"2.0"` or `"2.1"` |
| `SMALL_COMPARTMENTS` | Number of standard compartments |
| `LARGE_COMPARTMENTS` | Number of large compartments |
| `NFC-tags` | Map of NFC tag UIDs → compartment numbers (key name uses a hyphen as required by TOML) |
| `brightness_adjustment` | Backlight tuning multiplier |
| `max_brightness` | Lux value at which backlight reaches 100 % |
| `min_backlight` | Minimum backlight duty cycle (%) |
| `UI_color` | Accent colour for the UI |
| `UI_language` | UI language code (e.g. `"en"`, `"de"`) |
| `UI_sound` | Enable/disable sound feedback |
| `UI_haptic` | Enable/disable haptic feedback |

Localisation strings are loaded from `assets/settings/lang_<code>.toml` files (e.g. `lang_en.toml`, `lang_de.toml`).

### `secrets.toml`

Sensitive credentials — **excluded from version control**. Copy `assets/settings/secrets.toml.example` and fill in real values:

```bash
cp assets/settings/secrets.toml.example assets/settings/secrets.toml
chmod 600 assets/settings/secrets.toml
```

| Key | Description |
|-----|-------------|
| `ADAFRUIT_IO_USERNAME` | Adafruit IO username for MQTT logging |
| `ADAFRUIT_IO_KEY` | Adafruit IO API key |
| `ADAFRUIT_IO_FEED` | Adafruit IO feed name |
| `MQTT_command_token` | Shared token that must prefix every MQTT command payload (e.g. `"ZENG open 3"`) |
| `FLINK_URL` | Base URL of the Flink instance |
| `FLINK_API_KEY` | API key for Flink authentication |
| `[NFC] masterkey` | Current 16-byte DESFire master key (UTF-8 string) |
| `[NFC] app_id` | 3-byte DESFire application ID string |
| `[NFC] sys_id` | 3-byte system ID string |
| `[NFC] old_keys` | List of previous master keys (used by `nfc.format()` to recover older cards) |

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

### Deploy (pull from GitHub + update version)

```bash
./deploy.sh
```

The deploy script:
1. Stops the systemd user service (if running).
2. Runs `git pull` to fetch the latest code from GitHub.
3. Reads the most recent git tag and writes it into `version.py` as `__version__`.
4. Restarts the systemd user service.

### Hardware Watchdog

To enable the RPi hardware watchdog (required for the watchdog feature to work):

```
# /boot/config.txt
dtparam=watchdog=on
```

## Testing

The test suite covers all hardware-independent logic and runs in CI on every push. No Raspberry Pi hardware is required.

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

CI is configured via `.github/workflows/test.yml` (Ubuntu, Python 3.12).

## Project Structure

| Path | Description |
|------|-------------|
| `main.py` | Entry point: loads config, sets up logging, watchdog, hardware, starts GUI |
| `version.py` | Single `__version__` definition shared by all modules |
| `hardware_V2.py` | Hardware abstraction: `setup(hw_revision)` initialises all peripherals; `HW_CONFIGS` table selects pins/buses by revision |
| `compartment.py` | `Compartment` class: lock control, door status, LED assignment |
| `nfc.py` | NFC reader interface: card check, personalisation, format |
| `flink.py` | Flink REST API client and log handler |
| `networking.py` | MQTT client, command authentication, ping connectivity check |
| `ui.py` | Graphical user interface (Flet) |
| `bq25628.py` | Battery charger / fuel gauge driver (BQ25628) |
| `schluesselkasten.service` | Systemd user service unit file |
| `start.sh` / `stop.sh` | Helper scripts to start and stop the application |
| `deploy.sh` | Pull latest code from GitHub, set version from git tag, restart service |
| `assets/` | UI assets and settings files |
| `assets/settings/secrets.toml.example` | Template for `secrets.toml` |
| `requirements.txt` | Curated runtime dependencies |
| `requirements-dev.txt` | Additional dependencies for running tests |
| `tests/` | Automated pytest test suite (hardware-free) |
| `testing/` | Manual hardware test scripts |
| `.github/workflows/test.yml` | CI workflow (unit tests on Ubuntu) |

## License

TODO
