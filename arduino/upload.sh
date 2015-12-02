#!/bin/bash

SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd $SCRIPTDIR/filament_watch || exit 1
make upload || exit 1
make clean
if [ -d build-cli ]
then
    rmdir build-cli
fi

