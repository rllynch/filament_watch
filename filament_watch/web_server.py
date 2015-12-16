#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
web_server.py

Web server to serve filament_watch status
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

import os
import json
import time
import cherrypy

class WebGen(object):
    '''CherryPy generator for web server'''
    def __init__(self):
        self.state = {}
        self.log_msgs = ''

    @cherrypy.expose
    def gen_change(self, _=None):
        '''Dynamically updating data'''
        cherrypy.response.headers['Content-Type'] = 'text/json'
        self.state['log_msgs'] = self.log_msgs
        return json.dumps(self.state)

class WebServer(object):
    '''Main interface to web server'''
    def __init__(self, port, show_cherrypy_logs):
        self.webgen = None
        self.port = port
        self.log_msgs = []
        self.show_cherrypy_logs = show_cherrypy_logs

    def start(self):
        '''Start web server'''
        script_dir = os.path.dirname(os.path.abspath(__file__))
        http_config = {
            'server.socket_host': '0.0.0.0',
            'server.socket_port': self.port
        }
        mount_config = {
            '/': {
                'tools.staticdir.on': True,
                'tools.staticdir.root': script_dir,
                'tools.staticdir.dir': './static_www',
                'tools.staticdir.index': 'index.html'
            }
        }
        self.webgen = WebGen()
        cherrypy.config.update(http_config)
        cherrypy.tree.mount(self.webgen, '/', mount_config)
        # Disable redundant logging to screen
        cherrypy.log.screen = False
        if not self.show_cherrypy_logs:
            # Disable propagation to root logger
            #cherrypy.log.error_log.propagate = False
            cherrypy.log.access_log.propagate = False
        cherrypy.engine.start()

    def update(self, state):
        '''Update dynamic data'''
        self.webgen.state = state

    def log(self, msg):
        '''Append a log message'''
        timestamp = time.strftime('%H:%M:%S', time.localtime())
        self.log_msgs.append('%s: %s<br/>\n' % (timestamp, msg))
        if len(self.log_msgs) > 5:
            self.log_msgs.pop(0)
        self.webgen.log_msgs = '\n'.join(self.log_msgs)

    def stop(self):
        '''Stop web server'''
        cherrypy.engine.stop()
        self.webgen = None
