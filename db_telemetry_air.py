import socket
import serial
import argparse
from subprocess import Popen
from DroneBridge_Protocol import DBProtocol
from db_comm_helper import find_mac
import time

# Default values, may get overridden by command line arguments

UDP_Port_TX = 1604  # Port for communication with TX (Groundstation)
IP_TX = "192.168.3.2"   # Target IP address (IP address of the Groundstation - not important and gets overridden anyways)
UDP_buffersize = 512  # bytes
SerialPort = '/dev/ttyAMA0'  # connect this one to your flight controller
AB_INTERFACE = "wlan1"

# LTM: payload+crc
LTM_sizeGPS = 15
LTM_sizeAtt = 7
LTM_sizeStatus = 8
dst = b''

MavLink_junksize = 128 # bytes


def openTXUDP_Socket():
    print("DB_TEL_AIR: Opening UDP-Socket towards TX-Pi - listening on port " + str(UDP_Port_TX))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = ('', UDP_Port_TX)
    sock.bind(server_address)
    return sock


def openFCTel_Socket():
    print("DB_TEL_AIR: Opening Telemetrie-Socket " + SerialPort + " (to listen to FC)")
    ser = serial.Serial(SerialPort, timeout=None)
    return ser


def getGoPro_Status_JSON():
    return b"GoPro-Test Status"
    #return requests.get('http://10.5.5.9/gp/gpControl/status').json()


def read_LTM_Frame(functionbyte, serial_socket):
    """:returns complete LTM frame"""
    if functionbyte == b'A':
        return bytes(bytearray(b'$TA' + serial_socket.read(LTM_sizeAtt)))
    elif functionbyte == b'S':
        return bytes(bytearray(b'$TS' + serial_socket.read(LTM_sizeStatus)))
    elif functionbyte == b'G':
        return bytes(bytearray(b'$TG' + serial_socket.read(LTM_sizeGPS)))
    elif functionbyte == b'O':
        return bytes(bytearray(b'$TO' + serial_socket.read(LTM_sizeGPS)))
    elif functionbyte == b'N':
        return bytes(bytearray(b'$TN' + serial_socket.read(LTM_sizeAtt)))
    elif functionbyte == b'X':
        return bytes(bytearray(b'$TX' + serial_socket.read(LTM_sizeAtt)))
    else:
        print("unknown Frame!")
        return b'$T?'


def isitLTM_telemetry(telemetry_socket):
    for i in range(1,50):
        if telemetry_socket.read() == b'$':
            if telemetry_socket.read() == b'T':
                if check_LTM_crc_valid(read_LTM_Frame(telemetry_socket.read(), telemetry_socket)):
                    print("DB_RX_TEL: Detected LTM telemetry stream")
                    return True
    print("DB_TEL_AIR: Detected possible MavLink telemetry stream.")
    return False


def check_LTM_crc_valid(bytes_LTM_complete):
    """bytes_LTM_payload_crc is LTM payload+crc bytes"""
    crc = 0x00
    for byte in bytes_LTM_complete[3:]:
        crc = crc ^ (byte & 0xFF)
    return (crc == 0)


def setupVideo(mode):
    if mode == "wifi":
        proc = Popen("pp_rx_keepgopro.py", shell=True, stdin=None, stdout=None, stderr=None, close_fds=True)


def parseArguments():
    parser = argparse.ArgumentParser(description='Put this file on your drone. It handles telemetry.')
    parser.add_argument('-i', action='store', dest='DB_INTERFACE',
                        help='Network interface on which we send out packets to drone. Should be interface '
                             'for long range comm (default: wlan1)',
                        default='wlan1')
    parser.add_argument('-f', action='store', dest='serialport', help='Serial port which is connected to flight controller'
                                                                      ' and receives the telemetry (default: /dev/ttyAMA0)',
                        default='/dev/ttyAMA0')
    parser.add_argument('-t', action='store', dest='enable_telemetry',
                        help='Enables LTM over DroneBridge Protocol. Enable if you want to receive LTM from FC and pass'
                             ' it on to the groundstation via DroneBridge-Protocol. Disable wifibroadcast telemetry to '
                             'not block the socket. Use [yes|no]',
                        default='no')
    parser.add_argument('-l', action='store', dest='telemetry_type',
                        help='Set telemetry type manually. Default is [auto]. Use [ltm|mavlink|auto]',
                        default='auto')
    parser.add_argument('-p', action="store", dest='udp_port_tx', help='Local and remote port on which we need to address '
                                                                       'our packets for the groundstation and listen for '
                                                                       'commands coming from groundstation (same port '
                                                                       'number on TX and RX - you may not change'
                                                                       ' default: 1604)', type=int, default=1604)
    parser.add_argument('-m', action='store', dest='mode',
                        help='Set the mode in which communication should happen. Use [wifi|monitor]',
                        default='monitor')
    parser.add_argument('-a', action='store', dest='frame_type',
                        help='Specify frame type. Use <1> for Ralink chips (data frame) and <2> for Atheros chips '
                             '(beacon frame). No CTS supported. Options [1|2]', default='1')
    parser.add_argument('-c', action='store', dest='comm_id',
                        help='Communication ID must be the same on drone and groundstation. 8 characters long. Allowed '
                             'chars are (0123456789abcdef) Example: "aabb0011"', default='aabbccdd')
    return parser.parse_args()


def main():
    global SerialPort, UDP_Port_TX, IP_TX
    parsedArgs = parseArguments()
    SerialPort = parsedArgs.serialport
    UDP_Port_TX = parsedArgs.udp_port_tx
    istelemetryenabled = False
    if parsedArgs.enable_telemetry == "yes":
        istelemetryenabled = True
    mode = parsedArgs.mode
    frame_type = parsedArgs.frame_type
    DB_INTERFACE = parsedArgs.DB_INTERFACE
    telemetry_selection_auto = False
    isLTMTel = True
    if parsedArgs.telemetry_type == "mavlink":
        isLTMTel = False
    elif parsedArgs.telemetry_type == "auto":
        telemetry_selection_auto = True
        isLTMTel = False
    src = find_mac(DB_INTERFACE)
    comm_id = bytes(b'\x01'+b'\x02'+bytearray.fromhex(parsedArgs.comm_id))
    # print("DB_RX_TEL: Communication ID: " + comm_id.hex()) # only works in python 3.5
    print("DB_TEL_AIR: Communication ID: " + str(comm_id))
    dbprotocol = DBProtocol(src, dst, UDP_Port_TX, IP_TX, 0, b'\x02', DB_INTERFACE, mode, comm_id, frame_type, b'\x02')


    if istelemetryenabled:
        tel_sock = openFCTel_Socket()
        time.sleep(0.3)
        if telemetry_selection_auto:
            isLTMTel = isitLTM_telemetry(tel_sock)
    time.sleep(0.3)

    while True:
        if istelemetryenabled:
            if isLTMTel:
                if tel_sock.read() == b'$':
                    tel_sock.read()  # next one is always a 'T' (do not care)
                    LTM_Frame = read_LTM_Frame(tel_sock.read(), tel_sock)
                    dbprotocol.sendto_groundstation(LTM_Frame, b'\x02')
                    # TODO: deprecated, use control module (drone) --> status module (ground)
                    # if LTM_Frame[2] == 83:  # int("53", 16) --> 0x53 = S in UTF-8 --> sending frame after each status frame
                        # dbprotocol.send_dronebridge_frame()
                # TODO: deprecated, use control module (drone) --> status module (ground)
                # dbprotocol.receive_process_datafromgroundstation()  # to get the beacon frame and its RSSI values
            else:
                # it is not LTM --> fully transparent link for MavLink and other protocols
                dbprotocol.sendto_groundstation(tel_sock.read(MavLink_junksize), b'\x02')
        if not istelemetryenabled and isLTMTel:
            # TODO: deprecated, use control module (drone) --> status module (ground)
            pass
            # DroneBridge LTM Frame is triggered from telemetry. If telemetry is "no" we need to change trigger
            # dbprotocol.send_dronebridge_frame()
            # time.sleep(0.2)


if __name__ == "__main__":
    main()