#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
import logging
import argparse
import os
import socket
import yaml

from .octoprint_ctl import OctoPrintAccess
from .microcontroller_if import ArduinoInterface
from .web_server import WebServer

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
    parser.add_argument('--httpport', type=int, help='Port for status HTTP server')
    parser.add_argument('--debug', action='store_true', help='Enable debug logs')
    parser.add_argument('--config', default=os.path.expanduser("~/.filament_watch"), help='Configuration file')
    args = parser.parse_args()

    default_config = {
        'dev': '/dev/serial/by-id/usb-Adafruit_Adafruit_Mini_Metro_328_ADAOFIOls-if00-port0',
        'baudrate': 115200,
        'apikey': None,
        'octoprinthost': '127.0.0.1',
        'csvlog': None,
        'alarmchangethreshold': 0.1,
        'alarmminprinttime': 120,
        'alarmaction': 'cancel',
        'encoderscalingfactor': 0.040,
        'windowduration': 120,
        'httpport': None,
    }

    # Load config from file, or use defaults
    config_modified = False
    if os.path.isfile(args.config):
        with open(args.config) as cfg_file:
            config = yaml.load(cfg_file)
    else:
        config = default_config

    # Update config with command line settings
    for arg_name in default_config:
        if vars(args)[arg_name] is not None:
            config[arg_name] = vars(args)[arg_name]
            config_modified = True
        elif arg_name not in config:
            config[arg_name] = default_config[arg_name]
            config_modified = True

    # Store new config
    if config_modified:
        with open(args.config, 'w') as cfg_file:
            yaml.dump(config, cfg_file, default_flow_style=False)

    config['debug'] = args.debug

    return config

def log_msg(logger, web_server, msg):
    '''Log an info level message to all logging facilities'''
    logger.info(msg)
    if web_server:
        web_server.log(msg)

def get_this_host_ip():
    '''Returns the IP address of this computer used to connect to the internet
    (i.e. not the loopback interface's IP)'''
    # Adapted from Alexander at http://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib/1267524#1267524
    ghbn_ips = socket.gethostbyname_ex(socket.gethostname())[2]
    ip_list = [ip for ip in ghbn_ips if not ip.startswith("127.")]
    if len(ip_list) > 0:
        return ip_list[0]
    # Find the IP used to connect to the internet
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect(('8.8.8.8', 80))
    gsn_ip = sock.getsockname()[0]
    sock.close()
    return gsn_ip

def main(): # pylint: disable=too-many-locals
    """Main processing loop"""

    config = get_config()

    recent_length = config['windowduration']
    web_history_length = 120
    idle_logging_interval = 60
    log_level = logging.INFO
    if config['debug']:
        log_level = logging.DEBUG

    logging.basicConfig(format='%(asctime)-15s %(name)-30s %(levelname)-8s %(message)s', level=log_level)
    logger = logging.getLogger(__name__)
    logging.getLogger("requests").setLevel(logging.WARNING)

    if not config['apikey']:
        logger.error('OctoPrint API key not specified!')
        return

    filament_watch = ArduinoInterface(config['dev'], config['baudrate'], recent_length)
    octoprint = OctoPrintAccess(config['octoprinthost'], config['apikey'], recent_length)
    if config['httpport']:
        web_server = WebServer(config['httpport'], config['debug'])
        logger.info('Status URL: http://%s:%d/', get_this_host_ip(), config['httpport'])
        web_server.start()
    else:
        web_server = None

    try:
        field_names = ['Time', 'Alarm', 'Printing', 'Valid',
                       'Filament Position', 'Measured Change', 'GCode Change',
                       'Summary', 'State', 'Filename', 'File Position',
                       'File Size', 'G-code Filament Position', 'G-code Filament Total',
                       'Bed Target', 'Bed Actual', 'Hot End Target', 'Hot End Actual']

        log_msg(logger, web_server, 'Monitoring %s' % (config['dev']))

        if config['csvlog']:
            csv = open(config['csvlog'], 'w')
            csv.write(','.join(field_names))
            csv.write('\n')
        else:
            csv = None

        printing_count = 0
        skipped_log_count = idle_logging_interval
        web_gcode_history = []
        web_actual_history = []

        while True:
            pos, meas_change_raw = filament_watch.get_pos_change()
            if pos != None:
                meas_change_norm = meas_change_raw * config['encoderscalingfactor']
                logger.debug('New position is %d (%+.1f)', pos, meas_change_norm)
                stat = octoprint.status()

                logger.debug('OctoPrint status: printing=%d "%s" "%s" %.1f/%.1f %.1f/%.1f',
                             stat['printing'],
                             stat['summary'],
                             stat['state'],
                             stat['bed_target'],
                             stat['bed_actual'],
                             stat['tool0_target'],
                             stat['tool0_actual'])

                if stat['printing']:
                    if printing_count == 0:
                        log_msg(logger, web_server, 'Printing has started (%s)' % (stat['state']))
                    printing_count += 1
                else:
                    if printing_count != 0:
                        log_msg(logger, web_server, 'Printing has stopped (%s)' % (stat['state']))
                    printing_count = 0

                valid = False
                if printing_count >= config['alarmminprinttime']:
                    valid = True

                alarm = False
                if valid and (meas_change_norm / stat['gcode_change']) < config['alarmchangethreshold']:
                    alarm = True

                logger.debug('State: printing_count=%d alarm=%d', printing_count, alarm)
                chart_time = time.time() * 1000
                if web_server:
                    web_server.update({
                        'gcode': [chart_time, stat['gcode_change']],
                        'actual': [chart_time, meas_change_norm],
                        'gcode_history': web_gcode_history,
                        'actual_history': web_actual_history,
                        'history_length': web_history_length,
                        'alarm': alarm,
                        'printing': stat['printing'],
                        'valid': valid,
                        'time_to_valid': config['alarmminprinttime'] - printing_count,
                        'filament_pos': pos,
                        'summary': stat['summary'],
                        'file_pos': stat['file_pos'],
                        'bed_target': stat['bed_target'],
                        'bed_actual': stat['bed_actual'],
                        'tool0_target': stat['tool0_target'],
                        'tool0_actual': stat['tool0_actual'],
                    })
                # Make the history mirror the javascript state before it does addPoint
                web_gcode_history.append([chart_time, stat['gcode_change']])
                web_actual_history.append([chart_time, meas_change_norm])
                if len(web_gcode_history) > web_history_length:
                    web_gcode_history.pop(0)
                    web_actual_history.pop(0)

                if stat['printing'] or alarm or meas_change_raw != 0 or skipped_log_count >= (idle_logging_interval - 1):
                    fields = [
                        time.strftime('%H:%M:%S'), alarm, stat['printing'], valid,
                        pos, meas_change_norm, stat['gcode_change'],
                        stat['summary'], stat['state'], stat['file_name'], stat['file_pos'],
                        stat['file_size'], stat['gcode_filament_pos'], stat['gcode_filament_total'],
                        stat['bed_target'], stat['bed_actual'], stat['tool0_target'], stat['tool0_actual']]
                    fields = [str(x) for x in fields]
                    if csv:
                        csv.write(','.join(fields))
                        csv.write('\n')
                        csv.flush()
                    skipped_log_count = 0
                else:
                    skipped_log_count += 1

                if alarm:
                    logger.error('Alarm triggered - canceling job')
                    octoprint.issue_job_cmd(config['alarmaction'])
    finally:
        if csv:
            csv.flush()
            csv.close()
            csv = None
        if web_server:
            web_server.stop()
            web_server = None
