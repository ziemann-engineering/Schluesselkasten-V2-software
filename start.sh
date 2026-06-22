#!/bin/bash
# script to start the Schlüsselkasten GUI

# kill any remaining app components
pkill flet
pkill python
pkill python

# set up pins which are not (properly) configured at boot time

pinctrl 19 a5 # enable PWM (alternate 5) on pin 19 (display backlight)

pinctrl 22 a5 # enable SDA6 # TODO: enable pullups?
pinctrl 23 a5 # enable SCL6

cd ~/Schluesselkasten-V2-software/

source ../SKV2-env/bin/activate # enable venv

# start the main application. Do not use & here, as systemd will then think the service has ended.
# flet run also watches main.py, but reloads may fail
# for some reason, main.py currently does not launch the GUI
#python main.py
flet run
