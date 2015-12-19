# filament_watch

Pauses or stops OctoPrint if the 3D printer filament jams or runs out

# Setup

1) Purchase:

1.1) Quadrature encoder. The STL files are designed for the "Signswise 600p/r Incremental Rotary Encoder Dc5-24v Wide Voltage Power Supply 6mm Shaft" [[Amazon link]](http://www.amazon.com/gp/product/B00UTIFCVA?psc=1&redirect=true&ref_=oh_aui_detailpage_o09_s00)

1.2) M3-0.5 x 20mm screws [[Amazon link]](http://www.amazon.com/gp/product/B000FN21AO?psc=1&redirect=true&ref_=oh_aui_search_detailpage)

1.3) Adafruit Metro Mini 328 - 5V 16MHz [[Adafruit link]](http://www.adafruit.com/product/2590)

1.4) Optional: 2 x 0.1" pitch header blocks [[Adafruit link]](https://www.adafruit.com/products/2142)

2) Print the [base and wheel](http://www.thingiverse.com/thing:936521) to hold the encoder in place.

3) Optional: 3D print the [mini metro enclosure](http://www.thingiverse.com/thing:936519)

4) Wire up the Metro Mini 328 to the encoder, optionally soldering on the header blocks first:

4.1) Encoder red (power) - 5V

4.2) Encoder black (ground) - GND

4.3) Encoder green (output 1) - digital pin 3

4.4) Encoder white (output 2) - digital pin 2

![](https://github.com/rllynch/filament_watch/blob/master/images/metro_mini_328_wiring.jpg)

5) Connect the Metro Mini by USB to the computer running OctoPrint. Attach the wheel to the encoder and place it in the base. Feed the filament through the base.

6) Check out this git repository onto the computer running OctoPrint.

```
git clone https://github.com/rllynch/filament_watch.git
```

7) Compile and flash arduino/filament_watch/filament_watch.ino into the Metro Mini using either the Arduino IDE, or the command line scripts shown below:

```
cd filament_watch/arduino
./setup.sh
./upload.sh
cd ../..
```

8) Recommended: create a virtualenv for filament_watch and activate it

```
virtualenv filament_watch_env
. filament_watch_env/bin/activate
```

9) Install filament_watch

```
cd filament_watch
python setup.py install
```

10) Go to Settings in OctoPrint and in the API page, note the API key, enabling it if necessary. Launch filament_watch with --apikey argument, supplying the API key, and an open TCP port for the web interface.

```
filament_watch --apikey 11111111111111111111111111111111 --httpport 8081
```

11) Point a web browser at the selected port and start a print. The graph will show the actual movement of the filament graphed against the movement specified in the gcode (averaged over two minutes). If the two lines approximately track each other, then filament_watch is working correctly.

![](https://github.com/rllynch/filament_watch/blob/master/images/filament_watch_status.png)
