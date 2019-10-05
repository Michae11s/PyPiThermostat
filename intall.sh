#!/bin/bash
dir=$(pwd)

sudo ln -s /home/pi/build/PyPiThermostat/thermostat.service /lib/systemd/system/thermostat.service

sudo systemctl enable thermostat.service
sudo systemctl start thermostat.service
