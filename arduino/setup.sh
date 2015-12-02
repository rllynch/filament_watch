#!/bin/bash

# Based on http://pblog.ebaker.me.uk/2014/01/uploading-arduino-sketch-from-raspberry.html

sudo apt-get install -y arduino-core arduino-mk
sudo usermod -a -G dialout $USER

echo
echo Please log out then log back in

