#!/usr/bin/env python

"""
filament_watch.py

Cancel the print on OctoPrint if the filament is not feeding (e.g. due to
jam, out of filament, etc.)
"""

##############################################################################
#
# The MIT License (MIT)
#
# Copyright (c) 2015 Richard L. Lynch <rich@richlynch.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
#
##############################################################################

import time
import json
import logging
import argparse
import os

from .octoprint_ctl import OctoPrintAccess
from .microcontroller_if import ArduinoInterface

def get_config():
    '''Combine command line arguments and configuration file and return the configuration to use'''
    parser = argparse.ArgumentParser()
    parser.add_argument('--dev', help='Arduino serial device')
    parser.add_argument('--baudrate', type=int, help='Arduino baud rate')
    parser.add_argument('--apikey', help='OctoPrint API key')
    parser.add_argument('--octoprinthost', help='Hostname of OctoPrint server')
    parser.add_argument('--csvlog', help='CSV log of filament status')
    parser.add_argument('--alarmchangethreshold', type=float, help='Cancel print if filament movement falls below this threshold')
    parser.add_argument('--alarmminprinttime', type=int, help='Only cancel print after print has been running this many seconds')
    parser.add_argument('--alarmaction', help='Action to take on filament not feeding')
    parser.add_argument('--encoderscalingfactor', type=float, help='Conversion factor from encoder to mm')
    parser.add_argument('--windowduration', type=int, help='Average measurements over this number of seconds')
    parser.add_argument('--debug', action='store_true', help='Enable debug logs')
    parser.add_argument('--config', default=os.path.expanduser("~/.filament_watch"), help='Configuration file')
    args = parser.parse_args()

    default_config = {
        'dev': '/dev/serial/by-id/usb-Adafruit_Adafruit_Mini_Metro_328_ADAOFIOls-if00-port0',
        'baudrate': 115200,
        'apikey': None,
        'octoprinthost': '127.0.0.1',
        'csvlog': 'log.csv',
        'alarmchangethreshold': 0.1,
        'alarmminprinttime': 90,
        'alarmaction': 'cancel',
        'encoderscalingfactor': 0.041,
        'windowduration': 120,
    }

    # Load config from file, or use defaults
    config_modified = False
    if os.path.isfile(args.config):
        with open(args.config) as cfg_file:
            config = json.load(cfg_file)
    else:
        config = default_config

    # Update config with command line settings
    for arg_name in default_config:
        if vars(args)[arg_name]:
            config[arg_name] = vars(args)[arg_name]
            config_modified = True
        elif arg_name not in config:
            config[arg_name] = default_config[arg_name]
            config_modified = True

    # Store new config
    if config_modified:
        with open(args.config, 'w') as cfg_file:
            json.dump(config, cfg_file, indent=4)

    config['debug'] = args.debug

    return config

def main(): # pylint: disable=too-many-locals
    """Main processing loop"""

    config = get_config()

    recent_length = config['windowduration']
    idle_logging_interval = 60
    log_level = logging.INFO
    if config['debug']:
        log_level = logging.DEBUG

    logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s', level=log_level)
    logging.getLogger("requests").setLevel(logging.WARNING)

    if not config['apikey']:
        logging.error('OctoPrint API key not specified!')
        return

    filament_watch = ArduinoInterface(config['dev'], config['baudrate'], recent_length)
    octoprint = OctoPrintAccess(config['octoprinthost'], config['apikey'], recent_length)

    field_names = ['Time', 'Alarm', 'Printing', 'Valid',
                   'Filament Position', 'Measured Change', 'GCode Change',
                   'Summary', 'State', 'Filename', 'File Position',
                   'File Size', 'G-code Filament Position', 'G-code Filament Total',
                   'Bed Target', 'Bed Actual', 'Hot End Target', 'Hot End Actual']

    logging.info('Monitoring %s', config['dev'])
    with open(config['csvlog'], 'w') as csv:
        csv.write(','.join(field_names))
        csv.write('\n')

        printing_count = 0
        skipped_log_count = idle_logging_interval

        while True:
            pos, meas_change_raw = filament_watch.get_pos_change()
            if pos != None:
                meas_change_norm = meas_change_raw * config['encoderscalingfactor']
                logging.debug('New position is %d (%+.1f)', pos, meas_change_norm)
                stat = octoprint.status()

                logging.debug('OctoPrint status: printing=%d "%s" "%s" %.1f/%.1f %.1f/%.1f',
                              stat['printing'],
                              stat['summary'],
                              stat['state'],
                              stat['bed_target'],
                              stat['bed_actual'],
                              stat['tool0_target'],
                              stat['tool0_actual'])

                if stat['printing']:
                    if printing_count == 0:
                        logging.info('Printing has started (%s)', stat['state'])
                    printing_count += 1
                else:
                    if printing_count != 0:
                        logging.info('Printing has stopped (%s)', stat['state'])
                    printing_count = 0

                valid = False
                if printing_count > config['alarmminprinttime']:
                    valid = True

                alarm = False
                if valid and (meas_change_norm / stat['gcode_change']) < config['alarmchangethreshold']:
                    alarm = True

                logging.debug('State: printing_count=%d alarm=%d', printing_count, alarm)

                if stat['printing'] or alarm or meas_change_raw != 0 or skipped_log_count >= (idle_logging_interval - 1):
                    fields = [
                        time.strftime('%H:%M:%S'), alarm, stat['printing'], valid,
                        pos, meas_change_norm, stat['gcode_change'],
                        stat['summary'], stat['state'], stat['file_name'], stat['file_pos'],
                        stat['file_size'], stat['gcode_filament_pos'], stat['gcode_filament_total'],
                        stat['bed_target'], stat['bed_actual'], stat['tool0_target'], stat['tool0_actual']]
                    fields = [str(x) for x in fields]
                    csv.write(','.join(fields))
                    csv.write('\n')
                    csv.flush()
                    skipped_log_count = 0
                else:
                    skipped_log_count += 1

                if alarm:
                    logging.error('Alarm triggered - canceling job')
                    octoprint.issue_job_cmd(config['alarmaction'])
