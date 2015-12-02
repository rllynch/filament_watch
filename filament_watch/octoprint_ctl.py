#!/usr/bin/env python

"""
octoprint_api.py

OctoPrint control through its REST API
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

import json
import logging
import requests

class OctoPrintAccess(object): # pylint: disable=too-many-instance-attributes
    '''Class to wrap API access to OctoPrint'''
    def __init__(self, hostname, api_key, recent_length):
        self.hostname = hostname
        self.api_key = api_key
        self.cached_filename = None
        self.cached_gcode = None
        self.cached_filament_usage = None
        self.cache_resolution = None
        self.recent_gcode_pos = None
        self.recent_length = recent_length

    def cache_clear(self):
        '''Clear gcode cache'''
        if self.cached_filename != None:
            logging.debug("Clearing cache of %s", self.cached_filename)
            self.cached_filename = None
            self.cached_gcode = None
            self.cached_filament_usage = None
            self.cache_resolution = None

    def cache_file(self, filename):
        '''Cache specified file from OctoPrint server'''
        if filename == self.cached_filename and self.cached_gcode:
            return
        logging.debug("Caching %s", filename)
        file_req = requests.get('http://%s/api/files/local/%s?apikey=%s' % (self.hostname, filename, self.api_key))
        file_json = file_req.json()
        dl_url = file_json['refs']['download']
        gcode_req = requests.get('%s?apikey=%s' % (dl_url, self.api_key))
        self.cached_filename = filename
        self.cached_gcode = gcode_req.text
        self.cache_resolution = 16
        # Add one to length in case there's no line ending at the end of the
        # file, then add another one since this is the position of the last
        # element
        self.cached_filament_usage = [None] * int((len(self.cached_gcode) + 1) / self.cache_resolution + 1)

        # Measure the amount of filament used by the specified gcode
        total = 0
        last_extrude = 0.0
        file_pos = 0

        # Update usage at beginning of file
        self.cached_filament_usage[int(file_pos / self.cache_resolution)] = total

        # Step through each line of the file
        for line in self.cached_gcode.split('\n'):
            file_pos += len(line) + 1
            if line.startswith('G92 '):
                for token in line.split(' '):
                    if token[0:1] == 'E':
                        last_extrude = float(token[1:])
            if line.startswith('G1 '):
                for token in line.split(' '):
                    if token[0:1] == 'E':
                        dist = float(token[1:])
                        total += dist - last_extrude
                        last_extrude = dist
                        self.cached_filament_usage[int(file_pos / self.cache_resolution)] = total
        # Update usage at end of file
        self.cached_filament_usage[int(file_pos / self.cache_resolution)] = total

        # Fill in any gaps
        for idx in range(len(self.cached_filament_usage)):
            if self.cached_filament_usage[idx] is None:
                self.cached_filament_usage[idx] = self.cached_filament_usage[idx - 1]

    def measure_filament(self, file_pos):
        '''Determine how much filament has been used at the specified point in the file'''
        if not self.cached_filament_usage:
            return 0
        if file_pos < 0:
            return self.cached_filament_usage[-1]
        return self.cached_filament_usage[int(file_pos / self.cache_resolution)]

    def status_summary(self, printer_json, job_json): # pylint: disable=no-self-use
        """Convert print and job JSON to a meaningful human readable status"""
        temp_threshold = 5
        friendly_temp_names = {'bed': 'Bed', 'tool0': 'Hotend'}

        for dev in ['bed', 'tool0']:
            temp_actual = float(printer_json['temperature'][dev]['actual'])
            temp_target = float(printer_json['temperature'][dev]['target'])

            if (temp_target - temp_actual) > temp_threshold and temp_target > 0:
                return 'Heating %s' % (friendly_temp_names[dev])

        state = job_json['state']

        if state == 'Printing':
            try:
                time_left = float(job_json['progress']['printTimeLeft'])
            except TypeError:
                time_left = 0.0
            hours_left = int(time_left / 60 / 60)
            time_left -= hours_left * 60 * 60
            min_left = int(time_left / 60)
            time_left -= min_left * 60
            if int(job_json['progress']['filepos']) != 0:
                return 'Printing %s - %.0f%% - %02d:%02d:%02d left' % (
                    job_json['job']['file']['name'],
                    float(job_json['progress']['completion']),
                    hours_left,
                    min_left,
                    time_left)
        if state == 'Operational':
            bed_actual = float(printer_json['temperature']['bed']['actual'])
            if bed_actual > 30.0:
                return 'Bed Cooling'

            return 'Idle'

        return state

    def status(self):
        """Extract various status parameters from OctoPrint"""
        stat = {}
        stat['printing'] = False
        stat['summary'] = None
        stat['state'] = None
        stat['bed_actual'] = -1
        stat['bed_target'] = -1
        stat['tool0_actual'] = -1
        stat['tool0_target'] = -1
        stat['file_pos'] = -1
        stat['file_name'] = ''
        stat['file_size'] = -1
        stat['gcode_filament_pos'] = -1
        stat['gcode_filament_total'] = -1
        stat['gcode_change'] = 0

        printer_req = None
        printer_req_text = None
        try:
            printer_req = requests.get('http://%s/api/printer?apikey=%s' % (self.hostname, self.api_key))
            printer_req_text = printer_req.text
            if printer_req.status_code == 200:
                printer_json = printer_req.json()
            else:
                logging.debug('Status code %d querying /api/printer', printer_req.status_code)
                printer_json = None
        except requests.exceptions.ConnectionError:
            stat['summary'] = 'OctoPrint down'
            return stat
        except ValueError:
            logging.exception('ValueError processing printer status')
            stat['summary'] = 'ValueError processing printer status'
            return stat

        if printer_json is None:
            if printer_req_text.lower() == 'printer is not operational':
                stat['summary'] = 'Offline'
                return stat
            stat['summary'] = printer_req_text
            return stat

        job_json = None
        try:
            job_req = requests.get('http://%s/api/job?apikey=%s' % (self.hostname, self.api_key))
            job_json = job_req.json()
        except (requests.exceptions.ConnectionError, ValueError):
            logging.exception('Connection error')
            stat['summary'] = 'Connection error'
            return stat

        try:
            stat['summary'] = self.status_summary(printer_json, job_json)
            if stat['summary'].startswith('Printing '):
                stat['printing'] = True

            if printer_json:
                stat['bed_actual'] = float(printer_json['temperature']['bed']['actual'])
                if printer_json['temperature']['bed']['target']:
                    stat['bed_target'] = float(printer_json['temperature']['bed']['target'])
                else:
                    stat['bed_target'] = 0
                stat['tool0_actual'] = float(printer_json['temperature']['tool0']['actual'])
                if printer_json['temperature']['tool0']['target']:
                    stat['tool0_target'] = float(printer_json['temperature']['tool0']['target'])
                else:
                    stat['tool0_target'] = 0
                    stat['printing'] = False
                stat['state'] = job_json['state']
                if stat['state'] != 'Printing':
                    self.cache_clear()
                    self.recent_gcode_pos = None

            if job_json:
                if job_json['progress']['filepos']:
                    stat['file_pos'] = int(job_json['progress']['filepos'])
                    stat['file_size'] = int(job_json['job']['file']['size'])
                    stat['file_name'] = job_json['job']['file']['name']

            if stat['file_name'] and stat['state'] == 'Printing':
                self.cache_file(stat['file_name'])
                if self.cached_gcode:
                    stat['gcode_filament_pos'] = self.measure_filament(stat['file_pos'])
                    stat['gcode_filament_total'] = self.measure_filament(-1)

                    if self.recent_gcode_pos is None:
                        self.recent_gcode_pos = [stat['gcode_filament_pos']] * self.recent_length

                    self.recent_gcode_pos.append(stat['gcode_filament_pos'])
                    self.recent_gcode_pos.pop(0)
                    stat['gcode_change'] = self.recent_gcode_pos[-1] - self.recent_gcode_pos[0]

        except KeyError:
            logging.exception('Key error processing status')
            stat['summary'] = 'Key error processing status'
        except TypeError:
            logging.exception('Type error processing status')
            stat['summary'] = 'Type error processing status'
        if stat['gcode_filament_pos'] <= 0:
            stat['printing'] = False

        return stat

    def issue_job_cmd(self, cmd):
        """Issue a job command like start or cancel"""
        payload = {'command': cmd}
        url = 'http://%s/api/job' % (self.hostname)
        headers = {'Content-Type': 'application/json', 'X-Api-Key': self.api_key}
        req = requests.post(url, data=json.dumps(payload), headers=headers)
        if req.status_code != 204:
            logging.error('Received status code %d trying to issue job command "%s": %s', req.status_code, cmd, req.text)

    def jog(self, jog_x, jog_y, jog_z):
        """Job the print head"""
        payload = {'command': 'jog', 'x': jog_x, 'y': jog_y, 'z': jog_z}
        url = 'http://%s/api/printer/printhead' % (self.hostname)
        headers = {'Content-Type': 'application/json', 'X-Api-Key': self.api_key}
        req = requests.post(url, data=json.dumps(payload), headers=headers)
        if req.status_code != 204:
            logging.error('Received status code %d trying to jog head: %s', req.status_code, req.text)

    def home_head_xy(self):
        """Home the print head in xy plane"""
        payload = {'command': 'home', 'axes': ['x', 'y']}
        url = 'http://%s/api/printer/printhead' % (self.hostname)
        headers = {'Content-Type': 'application/json', 'X-Api-Key': self.api_key}
        req = requests.post(url, data=json.dumps(payload), headers=headers)
        if req.status_code != 204:
            logging.error('Received status code %d trying to home head: %s', req.status_code, req.text)
