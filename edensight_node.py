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

import sys
import time
import board
import busio
import digitalio
import _bleio
import adafruit_ble
from adafruit_ble.advertising.standard import Advertisement
from adafruit_ble.services.standard.device_info import DeviceInfoService
from adafruit_ble_berrymed_pulse_oximeter import BerryMedPulseOximeterService

import requests
from requests.auth import HTTPBasicAuth

# PyLint can't find BLERadio for some reason so special case it here.
ble = adafruit_ble.BLERadio()  # pylint: disable=no-member

pulse_ox_connection = None
pulse_mac_addr = None
last_connecting_time = None

last_sent_time = None

# print welcome message
print("Edensight Raspberry Pi Node (Data collection)")
print("Press 'Ctrl+C' anytime to quit!\n")
if len(sys.argv) != 3:
    print("Please input username and password of account.")
    print("./edensight_node <username> <password>")
    exit()

#get username password from command line arg
username = sys.argv[1]
password = sys.argv[2]

try:
    while True:
        if pulse_mac_addr is None:
            print("Scanning for Pulse Oximeter... ")
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
                    connecting_count = 0
                    pulse_ox_connection = ble.connect(advertisement)
                    pulse_mac_addr = advertisement.address
                    print("Device found! Address:", pulse_mac_addr.string)
                    print("Connecting...")
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
                        if not valid or pulse_rate == 255 or pulse_rate == 0 or pleth > 100 or spo2 < 50:
                            # ignore the data if invalid
                            continue
                        # todo: buffer and average every second

                        #average and send every second
                        if last_sent_time is None:
                            last_sent_time = time.time()
                        else:
                            current_time = time.time()
                            #if 5 seconds has passed since last send
                            if current_time - last_sent_time > 5:
                                last_sent_time = current_time

                                print(
                                    "sending data to server... | ",
                                    "SpO2: {}%  | ".format(spo2),
                                    "Pulse Rate: {} BPM  | ".format(pulse_rate),
                                    "Pleth: {}".format(pleth)
                                )

                                print(requests.post('https://braserver.mooo.com/edensight/api/vitalsigns/add', data = {'macAddr':pulse_mac_addr.string, 'heartRate':pulse_rate, 'spO2':spo2}, auth=(username, password)))

            if last_connecting_time is None:
                last_connecting_time = time.time()
            else:
                connecting_time = time.time()
                #if 5 seconds has passed since last send
                if connecting_time - last_connecting_time > 5:
                    last_connecting_time = connecting_time
                    #timeout connecting after 5s, try to scan and reconnect again
                    pulse_mac_addr = None
                    if pulse_ox_connection and pulse_ox_connection.connected:
                        pulse_ox_connection.disconnect()
                        pulse_ox_connection = None

        # todo: properly handle disconnect
        #       out of range disconnects?
        #except (_bleio.ConnectionError, AttributeError):
        except Exception as e:
            print(e)
            print("Connection lost.")
            try:
                print("Disconnecting...")
                pulse_ox_connection.disconnect()
            #except (_bleio.ConnectionError, AttributeError):
            except Exception as e:
                print("2: ", e)
                pass
            print("Disconnected. Scanning for device again.")
            pulse_ox_connection = None
            pulse_mac_addr = None
        #print("  end of while?")

except KeyboardInterrupt:
    print("\n\nQuitting...")
    try:
        #if connected, gracefully disconnect
        if pulse_ox_connection and pulse_ox_connection.connected:
            print("Disconnecting...")
            pulse_mac_addr = None
            pulse_ox_connection.disconnect()
            pulse_ox_connection = None
    except:
        pass #nothing to do

    print("Goodbye!")
    exit()
