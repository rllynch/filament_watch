#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
filament_watch_uc.py

Interface to microcontroller connected to encoder
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

import logging
import serial

class ArduinoInterface(object):
    '''Class to interface with Arduino running filament watch'''
    def __init__(self, dev, baudrate, recent_length):
        self.port = serial.Serial(dev, baudrate=baudrate, timeout=10.5)
        self.recent_length = recent_length
        self.recent_pos = None
        self.offset = 0
        self.logger = logging.getLogger(__name__)

    def get_pos_change(self):
        '''Get current absolute position and position change'''
        rcv = self.port.readline().decode('utf-8', 'ignore')
        lines = rcv.replace('\r', '').split('\n')
        lines = [l.strip() for l in lines if l.strip() != '']
        pos = None

        if len(lines) > 0:
            if lines[-1]:
                try:
                    pos = int(lines[-1]) + self.offset
                except ValueError:
                    self.logger.error('Invalid serial data: "%s"', lines[-1])

        if pos != None:
            if self.recent_pos is None:
                self.recent_pos = [pos] * self.recent_length

            change = pos - self.recent_pos[-1]
            if change > 32768:
                self.offset -= 65536
                pos -= 65536
                self.logger.debug('New offset is %d', self.offset)
            if change < -32768:
                self.offset += 65536
                pos += 65536
                self.logger.debug('New offset is %d', self.offset)

            self.recent_pos.append(pos)
            self.recent_pos.pop(0)

            change = pos - self.recent_pos[0]
            change = abs(change) / len(self.recent_pos)
            return [pos, change]
        return [None, None]
