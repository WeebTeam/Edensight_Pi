#!/usr/bin/python3
"""
Edensight Vital Signs Monitoring system
Device to Backend node

Connects to the pulse oximeter data (only vital signs we could afford to monitor)
to our backend server for monitoring

For the device: BerryMedical BM1000C

Dependencies:
bleak
requests 
"""

import sys
import asyncio
import requests
from requests.auth import HTTPBasicAuth
from bleak import BleakScanner
from bleak import BleakClient

####### variables declaration ###########
berryMedCharacteristicUUID = "49535343-1e4d-4bd9-ba61-23c647249616"

# for storing vital signs data before sending to server
# key value with key being mac address of device
# value being array of dictionaries of sensor data
vitalSignsData = {}

########### functions/coroutines ###########

# main async function?
async def run():
    # we wanna run this forever as we want to keep scanning for devices
    # but we scan evert 5 secs
    while True:
        await scanForBerryMedDevices()
        await asyncio.sleep(5)

# scan for berrymed sensors
async def scanForBerryMedDevices():
    devices = await BleakScanner.discover()
    print("Scanning for devices...")
    for d in devices:
        if d.name.strip("\x00") == "BerryMed":
            # if device is starts with berrymed, connect to it
            print("BerryMed device found!")
            
            # create a task to handle the device async-ly
            # loop continues to search for other devices while the task reads data from
            # the sensor (MULTIPLE DEVICE SUPPORT!!!!)
            asyncio.create_task(connectToBerryMedDevice(d.address))


# connects to the device and start sending data to server
async def connectToBerryMedDevice(address):
    print("connecting to device", address)
    client =  BleakClient(address)
    
    def berryMedNotify(sender, data):
        # use nonlocal to get the address variable of the outer function
        # this is because the callback function params are expected by start_notify
        # and cannot be altered. therefore we get the address only and hand that over 
        # to another function to do the actual parsing
        nonlocal address
        parseBerryMedData(address, data)
    
    try:
        await client.connect()
        
        # we loop forever as we want data from the sensor forever (until program quits or 
        # device is disconnected)
        while True:
            # start notify to get data from the sensor
            # we only wait 0.1 before closing as we dont need so much data (wastes processing anyways)
            await client.start_notify(berryMedCharacteristicUUID, berryMedNotify)
            await asyncio.sleep(0.1)
            await client.stop_notify(berryMedCharacteristicUUID)
            
            # wait abit for any callbacks to finish
            await asyncio.sleep(0.1)
            sendDataToServer(address)
            
            # after stop notify we wait for 5 seconds before getting data from sensor again
            await asyncio.sleep(4.8)
            
    except Exception as e:
       # print("------------------- EXCEPTION OWO ---------------")
        #print(e)
    finally:
        print("disconnecting from", address)
        await client.disconnect()

# parse data from BerryMed vital signs monitor
# at this point it only parses pulse rate and spo2
def parseBerryMedData(address, data):
    count = 0
    packet = bytearray()
    packets = []

    for byte in data:
        # each packet is 5 bytes long
        # we split them into an array of bytearrays 5 byte wide
        packet.append(byte)
        count += 1
        
        if count == 5:
            packets.append(packet)
            packet = bytearray()
            count = 0
    
    # source for data packet info: https://raw.githubusercontent.com/zh2x/BCI_Protocol/master/BCI%20Protocol%20V1.2.pdf
    # go through all the collected data and parse the vital signs
    for p in packets:
        # we only need pulse and spo2 so only getting them both
        pulse = p[3] + (p[2] & (1 << 7))
        spo2 = p[4]
        
        # according to pdf these 2 values are invalid
        # save valid values into the vital signs data array for later processing
        if pulse != 0xFF and spo2 != 0x7F:
            if address in vitalSignsData:
                # if we have previously added data in, just append
                vitalSignsData[address].append({"pulse": pulse, "spo2": spo2})
            else:
                # if not we create new key value with the array
                vitalSignsData[address] = [{"pulse": pulse, "spo2": spo2}]


def sendDataToServer(address):
    if address in vitalSignsData:
        dataArray = vitalSignsData[address]

        # average that data and send it    
        meanData = {"pulse": 0, "spo2": 0}
        
        for data in dataArray:
            meanData["pulse"] += data["pulse"]
            meanData["spo2"] += data["spo2"]
        arraySize = len(dataArray)
        meanData["pulse"] = int(meanData["pulse"]/arraySize)
        meanData["spo2"] = int(meanData["spo2"]/arraySize)
        
        # clear the data array, since we have the mean values now
        del vitalSignsData[address]
        
        #post to server
        response = requests.post('https://braserver.mooo.com/edensight/api/vitalsigns/add', data = {'macAddr':address.lower(), 'heartRate':meanData["pulse"], 'spO2':meanData["spo2"]}, auth=(backendUname, backendPasswd))
        
        print(address, ":", meanData, "|", response.status_code)
    else:
        print("no data for", address)

    
########## end of functions/coroutines declaration #######



################################## code runs here? ##################################

# print welcome message
print("Edensight Raspberry Pi Node (Data collection)")
print("Press 'Ctrl+C' anytime to quit!\n")
if len(sys.argv) != 3:
    print("Please input username and password of account.")
    print("./edensight_node <username> <password>")
    exit()

backendUname = sys.argv[1]
backendPasswd = sys.argv[2]



####### main ########
# we just call the run() async function and let it do the rest

try:
    asyncio.run(run())

except KeyboardInterrupt:
    print("\n\nQuitting...")

    print("Goodbye!")
    exit()
    
######## End of main ###########    

