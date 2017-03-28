#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Murano Newreka Device Simulator
# This Python script simulates the prototype Newreka device.  It is used in conjunction with the 
# newreka-device Product on the Exosite Business Platform.

#It is based on:
# Murano Python Simple Device Simulator
# Copyright 2016 Exosite
# Version 1.0
# For more information see: http://beta-docs.exosite.com/murano/get-started
#
# Requires Python 2.6 or Python 2.7


import os
import time
import datetime
import random

import socket
import ssl


try:
    from StringIO import StringIO
    import httplib
    input = raw_input
    PYTHON = 2
except ImportError:
    from http import client as httplib
    from io import StringIO, BytesIO

    PYTHON = 3

# -----------------------------------------------------------------
# EXOSITE PRODUCT ID / SERIAL NUMBER IDENTIFIER / CONFIGURATION
# -----------------------------------------------------------------

#This must be configured for each product
# Product ID is obtained from the Product Info page
#UNSET_PRODUCT_ID = 'qvebworumfyo80k9'
#productid = os.getenv('SIMULATOR_PRODUCT_ID', UNSET_PRODUCT_ID)
identifier = os.getenv('SIMULATOR_DEVICE_ID', '1')  # default identifier

SHOW_HTTP_REQUESTS = False
PROMPT_FOR_PRODUCTID_AND_SN = os.getenv('SIMULATOR_SHOULD_PROMPT', '1') == '1'
LONG_POLL_REQUEST_TIMEOUT = 2 * 1000  # in milliseconds

# -----------------------------------------------------------------
# ---- SHOULD NOT NEED TO CHANGE ANYTHING BELOW THIS LINE ------
# -----------------------------------------------------------------

host_address_base = os.getenv('SIMULATOR_HOST', 'm2.exosite.com')
host_address = None  # set this later when we know the product ID
https_port = 443

class FakeSocket:
    def __init__(self, response_str):
        if PYTHON == 2:
            self._file = StringIO(response_str)
        else:
            self._file = BytesIO(response_str)

    def makefile(self, *args, **kwargs):
        return self._file


# LOCAL DATA VARIABLES
FLAG_CHECK_ACTIVATION = False
uptime = 0
connected = True
last_modified = {}
LOOP = True
#state = ''

# Default Simulated Newreka device outputs
outside_temp = 60
refrig_pressure = 25
registered = 1
location = "35.78958593, -78.65986705"
battery_lvl = 11.6
compressor_powered = 1
compressor_running = 1
signal_strength = -90
tamper_1 = 0
tamper_2 = 0
mains_power = 1
carrier = "Verizon"
imei = "12345-12345"

# Default Simulated Newreka device inputs
underPressure = -1
overPressure = -1

# --------------------------#
# MURANO SPECIFIC FUNCTIONS
#
# These must be rewritten in the device's native language
# -------------------------- 

def SOCKET_SEND(http_packet):
    # SEND REQUEST
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ssl_s = ssl.wrap_socket(s)
    ssl_s.connect((host_address, https_port))
    if SHOW_HTTP_REQUESTS:
        print("--- Sending ---\r\n {} \r\n----".format(http_packet))
    if PYTHON == 2:
        ssl_s.send(http_packet)
    else:
        ssl_s.send(bytes(http_packet, 'UTF-8'))
    # GET RESPONSE
    response = ssl_s.recv(1024)
    ssl_s.close()
    if SHOW_HTTP_REQUESTS:
        print("--- Response --- \r\n {} \r\n---")

    # PARSE REPONSE
    fake_socket_response = FakeSocket(response)
    parsed_response = httplib.HTTPResponse(fake_socket_response)
    parsed_response.begin()
    return parsed_response


def ACTIVATE():
    try:
        # print("attempt to activate on Murano")

        http_body = 'vendor=' + productid + '&model=' + productid + '&sn=' + identifier
        # BUILD HTTP PACKET
        http_packet = ""
        http_packet += 'POST /provision/activate HTTP/1.1\r\n'
        http_packet += 'Host: ' + host_address + '\r\n'
        http_packet += 'Connection: Close \r\n'
        http_packet += 'Content-Type: application/x-www-form-urlencoded; charset=utf-8\r\n'
        http_packet += 'content-length:' + str(len(http_body)) + '\r\n'
        http_packet += '\r\n'
        http_packet += http_body

        response = SOCKET_SEND(http_packet)

        # HANDLE POSSIBLE RESPONSES
        if response.status == 200:
            new_cik = response.read().decode("utf-8")
            print("Activation Response: New CIK: {} ..............................".format(new_cik[0:10]))
            return new_cik
        elif response.status == 409:
            print("Activation Response: Device Aleady Activated, there is no new CIK")
        elif response.status == 404:
            print("Activation Response: Device Identity ({}) activation not available or check Product Id ({})".format(
                identifier,
                productid
                ))
        else:
            print("Activation Response: failed request: {} {}".format(str(response.status), response.reason))
            return None

    except Exception as e:
        # pass
        print("Exception: {}".format(e))
    return None


def GET_STORED_CIK():
    print("get stored CIK from non-volatile memory")
    try:
        f = open(productid + "_" + identifier + "_cik", "r+")  # opens file to store CIK
        local_cik = f.read()
        f.close()
        print("Stored cik: {} ..............................".format(local_cik[0:10]))
        return local_cik
    except Exception as e:
        print("Unable to read a stored CIK: {}".format(e))
        return None


def STORE_CIK(cik_to_store):
    print("storing new CIK to non-volatile memory")
    f = open(productid + "_" + identifier + "_cik", "w")  # opens file that stores CIK
    f.write(cik_to_store)
    f.close()
    return True


def WRITE(WRITE_PARAMS):
    # print "write data to Murano"

    http_body = WRITE_PARAMS
    # BUILD HTTP PACKET
    http_packet = ""
    http_packet += 'POST /onep:v1/stack/alias HTTP/1.1\r\n'
    http_packet += 'Host: ' + host_address + '\r\n'
    http_packet += 'X-EXOSITE-CIK: ' + cik + '\r\n'
    http_packet += 'Connection: Close \r\n'
    http_packet += 'Content-Type: application/x-www-form-urlencoded; charset=utf-8\r\n'
    http_packet += 'content-length:' + str(len(http_body)) + '\r\n'
    http_packet += '\r\n'
    http_packet += http_body

    response = SOCKET_SEND(http_packet)

    # HANDLE POSSIBLE RESPONSES
    if response.status == 204:
        # print "write success"
        return True, 204
    elif response.status == 401:
        print("401: Bad Auth, CIK may be bad")
        return False, 401
    elif response.status == 400:
        print("400: Bad Request: check syntax")
        return False, 400
    elif response.status == 405:
        print("405: Bad Method")
        return False, 405
    else:
        print(str(response.status), response.reason, 'failed:')
        return False, response.status

def READ(READ_PARAMS):
    try:
        # BUILD HTTP PACKET
        http_packet = ""
        http_packet += 'GET /onep:v1/stack/alias?' + READ_PARAMS + ' HTTP/1.1\r\n'
        http_packet += 'Host: ' + host_address + '\r\n'
        http_packet += 'X-EXOSITE-CIK: ' + cik + '\r\n'
        # http_packet += 'Connection: Close \r\n'
        http_packet += 'Accept: application/x-www-form-urlencoded; charset=utf-8\r\n'
        http_packet += '\r\n'

        response = SOCKET_SEND(http_packet)

        # HANDLE POSSIBLE RESPONSES
        if response.status == 200:
            # print "read success"
            return True, response.read().decode('utf-8')
        elif response.status == 401:
            print("401: Bad Auth, CIK may be bad")
            return False, 401
        elif response.status == 400:
            print("400: Bad Request: check syntax")
            return False, 400
        elif response.status == 405:
            print("405: Bad Method")
            return False, 405
        else:
            print(str(response.status), response.reason, 'failed:')
            return False, response.status

    except Exception as e:
        # pass
        print("Exception: {}".format(e))
    return False, 'function exception'


def LONG_POLL_WAIT(READ_PARAMS):
    try:
        # print "long poll state wait request from Murano"
        # BUILD HTTP PACKET
        http_packet = ""
        http_packet += 'GET /onep:v1/stack/alias?' + READ_PARAMS + ' HTTP/1.1\r\n'
        http_packet += 'Host: ' + host_address + '\r\n'
        http_packet += 'Accept: application/x-www-form-urlencoded; charset=utf-8\r\n'
        http_packet += 'X-EXOSITE-CIK: ' + cik + '\r\n'
        http_packet += 'Request-Timeout: ' + str(LONG_POLL_REQUEST_TIMEOUT) + '\r\n'
        if last_modified.get(READ_PARAMS) != None:
            http_packet += 'If-Modified-Since: ' + last_modified.get(READ_PARAMS) + '\r\n'
        http_packet += '\r\n'

        response = SOCKET_SEND(http_packet)

        # HANDLE POSSIBLE RESPONSES
        if response.status == 200:
            # print "read success"
            if response.getheader("last-modified") != None:
                # Save Last-Modified Header (Plus 1s)
                lm = response.getheader("last-modified")
                next_lm = (datetime.datetime.strptime(lm, "%a, %d %b %Y %H:%M:%S GMT") + datetime.timedelta(seconds=1)).strftime("%a, %d %b %Y %H:%M:%S GMT")
                last_modified[READ_PARAMS] = next_lm
            return True, response.read()
        elif response.status == 304:
            # print "304: No Change"
            return False, 304
        elif response.status == 401:
            print("401: Bad Auth, CIK may be bad")
            return False, 401
        elif response.status == 400:
            print("400: Bad Request: check syntax")
            return False, 400
        elif response.status == 405:
            print("405: Bad Method")
            return False, 405
        else:
            print(str(response.status), response.reason)
            return False, response.status

    except Exception as e:
        pass
        print("Exception: {}".format(e))
    return False, 'function exception'

# --------------------------
# Start simualtion by reading the Product ID
# --------------------------

try:
    with open('prod_id.txt', 'r') as f:
        productid = f.read().replace('\n', '')
except IOError:
    print ("Product ID file not found or corrupt" )

host_address = productid + '.' + host_address_base

# Select alternate device identity
print("The default Device Identity is: {}".format(identifier))
identityok = input("If OK, hit return, if you prefer a different Identity, type it here: ")
if identityok != "":
    identifier = identityok

# Display some useful info
print("\r\n-----")
print("Product Id: {}".format(productid))
print("Device Identity: {}".format(identifier))
print("Product Unique Host: {}".format(host_address))
print("-----")

print("Device activation...")
# --------------------------
# ACTIVATE DEVICE IF NECESSARY
#
# This must be rewritten in the device's native language
# --------------------------
# Check if CIK locally stored already
cik = GET_STORED_CIK()
if cik is None:
    # Try to activate device
    print("Try to activate")
    act_response = ACTIVATE()
    if act_response is not None:
        cik = act_response
        STORE_CIK(cik)
        FLAG_CHECK_ACTIVATION = False
    else:
        FLAG_CHECK_ACTIVATION = True

# --------------------------
# DEVICE SIMULATION CODE STARTS HERE
# --------------------------
start_time = int(time.time())
print("\r\nStarting main loop...\r\n")

counter = 100  # for debug purposes so you don't have issues killing this process
init = 1

while LOOP:
    uptime = int(time.time()) - start_time
    last_request = time.time()

    connection = 'Connected'
    if FLAG_CHECK_ACTIVATION:
        connection = "Not Connected"
            

    if cik is not None and not FLAG_CHECK_ACTIVATION:

        # Show heartbeat so we know device emulator is running
        output_string = ("Connection: {0:s}, Run Time: {1:5d}").format(connection, uptime)
        print("{}".format(output_string))

        # Look for change in low pressure warning 
        status, resp = READ('underPressure')
        if not status and resp == 401:
            FLAG_CHECK_ACTIVATION = True
        if not status and resp == 304:
            pass
        if status:
            print("Low Pressure Warning Value: {}".format(str(resp)))
            new_value = resp.split('=')
            underPressure = new_value[1]
                
        # Look for change in high pressure warning 
        status, resp = READ('overPressure')
        if not status and resp == 401:
            FLAG_CHECK_ACTIVATION = True
        if not status and resp == 304:
            pass
        if status:
            print("High Pressure Warning Value: {}".format(str(resp)))
            new_value = resp.split('=')
            overPressure = new_value[1]

        # Generate random temperature and pressure values
        outside_temp = round(random.uniform(outside_temp - 0.2, outside_temp + 0.2), 1)
        if outside_temp > 120:
            outside_temp = 120
        if outside_temp < -20:
            outside_temp = -20000002
            
        refrig_pressure = round(random.uniform(refrig_pressure - 5, refrig_pressure + 5), 2)
        if refrig_pressure > 100:
            refrig_pressure = 100
        if refrig_pressure < 1:
            refrig_pressure = 1
        
        # Write data from device to Exosite
        device_data = 'outside_temp=' + str(outside_temp) + '&refrig_pressure=' + str(refrig_pressure) + '&conn_uptime=' + str(uptime) + \
            '&registered=' + str(registered) + '&location=' + str(location) + '&battery_lvl=' + str(battery_lvl) + '&compressor_powered=' + str(compressor_powered) + \
            '&compressor_running=' + str(compressor_running) + '&signal_strength=' + str(signal_strength) + '&tamper_1=' + str(tamper_1) + '&tamper_2=' + str(tamper_2) + \
            '&mains_power=' + str(mains_power) + '&carrier=' + str(carrier) + '&imei=' + str(imei)
        status, resp = WRITE(device_data)
        if not status and resp == 401:
            FLAG_CHECK_ACTIVATION = True

    if FLAG_CHECK_ACTIVATION:
        if (uptime % 10) == 0:
            # print("---")
            print("Device CIK may be expired or not available (not added to product) - trying to activate")
        act_response = ACTIVATE()
        if act_response is not None:
            cik = act_response
            STORE_CIK(cik)
            FLAG_CHECK_ACTIVATION = False
        else:
            # print("Wait 10 seconds and attempt to activate again")
            time.sleep(10)
            
    time.sleep(.5)

IMDONE = input("Press any key to continue")