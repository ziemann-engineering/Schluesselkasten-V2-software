#!/bin/bash
# checks if desktop environment is running, starts it if not; also shuts down python program
if ! pgrep -x "wf-panel-pi" > /dev/null
then
    /usr/bin/lwrespawn /usr/bin/pcmanfm --desktop --profile LXDE-pi &
    /usr/bin/lwrespawn /usr/bin/wf-panel-pi &
    #/usr/bin/kanshi &
    /usr/bin/lxsession-xdg-autostart &
    squeekboard &
fi

# Check if service is running
if systemctl is-active --user --quiet schluesselkasten.service; 
then
    echo "Service $SERVICE_NAME is running. Stopping it..."
    systemctl --user stop schluesselkasten.service
else
    echo "Service $SERVICE_NAME is not running."
    
    pkill flet
    pkill python
    pkill python
fi






