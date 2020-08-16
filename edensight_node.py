#!/usr/bin/python3
"""
Edensight Vital Signs Monitoring system
Device to Backend node

Connects to the pulse oximeter data (only vital signs we could afford to monitor)
to our backend server for monitoring

For the device: BerryMedical BM1000C 
"""
# Credits to Adafruit for https://github.com/adafruit/Adafruit_CircuitPython_BLE_BerryMed_Pulse_Oximeter 
# which is the library that we are using here
# The sensor updates the readings at 100Hz.
 
import time
import board
import busio
import digitalio
import _bleio
import adafruit_ble
from adafruit_ble.advertising.standard import Advertisement
from adafruit_ble.services.standard.device_info import DeviceInfoService
from adafruit_ble_berrymed_pulse_oximeter import BerryMedPulseOximeterService
 
# PyLint can't find BLERadio for some reason so special case it here.
ble = adafruit_ble.BLERadio()  # pylint: disable=no-member

pulse_ox_connection = None
pulse_mac_addr = None

# print welcome message

while True:

    print("Scanning for Pulse Oximeter... ", end="")
    # scan for ble advertisements
    for advertisement in ble.start_scan(timeout=5):
        # check if a device is found
        name = advertisement.complete_name
        if not name:
            # restart loop if name is invalid (no device found)
            continue
        # check if the advertisement is the oximeter we are looking for
        # "BerryMed" devices may have trailing nulls on their name.
        if name.strip("\x00") == "BerryMed":
            # connect to the device
            pulse_ox_connection = ble.connect(advertisement)
            pulse_mac_addr = advertisement.address
            print("found!")
            print("mac addr: ", pulse_mac_addr)
            # break out of the loop and go to next part of the code
            break
 
    ble.stop_scan()
 
    try:
        # if we are connected (so if we lose connection we can restart from top)
        if pulse_ox_connection and pulse_ox_connection.connected:
 
            # get the pulse oximeter service (subscribe to the service)
            pulse_ox_service = pulse_ox_connection[BerryMedPulseOximeterService]
 
            while pulse_ox_connection.connected:
                # receive data from the pulse oximeter
                values = pulse_ox_service.values
                if values is not None: #if theres value
                    # unpack the message to 'values' list
                    valid, spo2, pulse_rate, pleth, finger = values
                    
                    # the valid checking in adafruit's library only checks spO2
                    # lets check pulse rate and pleth too
                    if not valid or pulse_rate == 255 or pleth > 100:
                        # ignore the data if invalid
                        continue
                    # todo: buffer and average every second
                    #       push to remote server
                    print(
                        "SpO2: {}%  | ".format(spo2),
                        "Pulse Rate: {} BPM  | ".format(pulse_rate),
                        "Pleth: {}".format(pleth)
                    )

    # todo: properly handle disconnect
    #       out of range disconnects?
    except _bleio.ConnectionError:
        try:
            pulse_ox_connection.disconnect()
        except _bleio.ConnectionError:
            pass
        pulse_ox_connection = None
