import argparse
from DroneBridge_Protocol import DBProtocol

# Default values, may get overridden by command line arguments
UDP_Port_RX = 1604  # Port for communication with RX (Drone)
IP_RX = '192.168.3.1'  # Target IP address (IP address of the Pi on the Drone: needs fixed one)
UDP_PORT_ANDROID = 1605  # Port for communication with smartphone (port on groundstation side)
UDP_Port_SMARTPHONE_SIDE = 1604  # Port of smartphone app
IP_ANDROID = '127.0.0.1'  # IP address of the android phone (not important, gets overridden)
UDP_buffersize = 512  # bytes
interface_drone_comm = "wlx000ee8dcaa2c"
#src = b'\x00\x0E\xE8\xDC\xAA\x2C'   # MAC address of TX-Pi (zioncom) - mac of local interface (groundstation)
src = b'\x24\x05\x0f\x73\xb5\x74' # MAC address of TX-Pi (CSL) - mac of local interface (groundstation)
# - dest_mac first byte must be 0x01 !!! -
dst = b'\x01\xa6\xF7\x16\xA5\x11'   # MAC address of RX-Pi (TP-Link) - mac of drone
comm_id = b'\x01\xa6\xF7\x16\xA5\x11' # has to start with 0x01
# TODO: at the moment comm_id must be same as dest for compatibility reasons of v1 and v2 of raw protocol. Otherwise no MSP command can be sent
#cat /sys/class/net/wlx000ee8dcaa2c/address


def parsearguments():
    parser = argparse.ArgumentParser(description='Put this file on TX (drone). It handles telemetry, GoPro settings'
                                                 ' and communication with smartphone')
    parser.add_argument('-i', action='store', dest='interface_drone_comm',
                        help='Network interface on which we send out packets to MSP-pass through. Should be interface '
                        'for long range comm (default: wlan1)',
                        default='wlan1')
    parser.add_argument('-p', action="store", dest='udp_port_rx',
                        help='Local and remote port on which we need to address '
                             'our packets for the drone and listen for '
                             'commands coming from drone (same port '
                             'number on TX and RX - you may not change'
                             ' default: 1604)', type=int, default=1604)
    parser.add_argument('-r', action='store', dest='ip_rx', help='IP address of RX (drone) (default: 192.168.3.1)',
                        default='192.168.3.1')
    parser.add_argument('-a', action='store', dest='udp_port_android',
                        help='Port we listen on for incoming packets from '
                             'smartphone (default: 1605)',
                        default=1605, type=int)
    parser.add_argument('-m', action='store', dest='mode',
                        help='Set the mode in which communication should happen. Use [wifi|monitor]',
                        default='monitor')
    return parser.parse_args()


def main():
    global interface_drone_comm, IP_RX, UDP_Port_RX, UDP_PORT_ANDROID
    parsedargs = parsearguments()
    interface_drone_comm = parsedargs.interface_drone_comm
    mode = parsedargs.mode
    IP_RX = parsedargs.ip_rx
    UDP_Port_RX = parsedargs.udp_port_rx
    UDP_PORT_ANDROID = parsedargs.udp_port_android

    dbprotocol = DBProtocol(src, dst, UDP_Port_RX, IP_RX, UDP_PORT_ANDROID, b'\x01', interface_drone_comm, mode, comm_id)
    if mode == 'wifi':
        dbprotocol.updateRouting()


    last_keepalive = 0
    global IP_ANDROID, UDP_Port_SMARTPHONE_SIDE

    # if sendTelemetryTX_ready(rx_sock):
    while True:
        #TODO: only send data to smartphone is smartphone is listening
        received = dbprotocol.receive_datafromdrone()
        #received= b'$TA\x00\x00\x01\x00\xf0\x00\xf1'
        #time.sleep(0.15)
        #if (time.time()-last_keepalive)<6 and received != False:
        if received != False:
            if received[2] == 89:
                received = dbprotocol.finish_dronebridge_ltmframe(received)
                # send a beaconframe so drone telemetry can extract signal strength. MSP RSSI over AUX is also a option
                # Then RSSI field in LTM would be set correctly. But RSSI would be in % which is worse compared to dbm
                dbprotocol.send_beacon()
            print("Sent "+str(dbprotocol.sendto_smartphone(received))+" bytes to sp")
            last_keepalive = dbprotocol.process_smartphonerequests(last_keepalive)
        #else:
        #    print("smartphone is not ready!")
        #    result = dbprotocol.check_smartphone_ready()
        #    if result:
        #        # updateRouting(IP_ANDROID, tables_updated)
        #        # tables_updated = True
        #        last_keepalive = time.time()

if __name__ == "__main__":
    main()
