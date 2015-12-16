#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''Setup for filament_watch'''

import ez_setup

ez_setup.use_setuptools()

from setuptools import setup

with open('README.md') as readme_file:
    README = readme_file.read()

setup(
    name="filament_watch",
    version="1.0",
    author="Richard L. Lynch",
    author_email="rich@richlynch.com",
    description=("Monitors filament motion and pauses/cancels OctoPrint if the filament stops feeding."),
    long_description=README,
    license="MIT",
    keywords="3d_printer 3d printer filament watch monitor jam safety",
    url="https://github.com/rllynch/filament_watch",
    packages=['filament_watch'],
    include_package_data=True,
    entry_points={
        'console_scripts': ['filament_watch = filament_watch.filament_watch:main'],
    },
    install_requires=[
        'requests',
        'pyserial',
        'cherrypy>=3.1',
        'pyyaml'
    ]
)
