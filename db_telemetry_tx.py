import argparse
from DroneBridge_Protocol import DBProtocol
from db_comm_helper import find_mac

# Default values, may get overridden by command line arguments


UDP_Port_RX = 1604  # Port for communication with RX (Drone)
IP_RX = '192.168.3.1'  # Target IP address (IP address of the Pi on the Drone: needs fixed one)
UDP_PORT_ANDROID = 1605  # Port for communication with smartphone (port on groundstation side)
UDP_buffersize = 512  # bytes
interface_drone_comm = "000ee8dcaa2c"
#src = b'\x00\x0E\xE8\xDC\xAA\x2C'   # MAC address of TX-Pi (zioncom) - mac of local interface (groundstation)
#src = b'\x24\x05\x0f\x73\xb5\x74' # MAC address of TX-Pi (CSL) - mac of local interface (groundstation)
# - dest_mac first byte must be 0x01 !!! -
dst = b''   # MAC address of RX-Pi (TP-Link) - mac of drone
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
    parser.add_argument('-m', action='store', dest='mode',
                        help='Set the mode in which communication should happen. Use [wifi|monitor]',
                        default='monitor')
    parser.add_argument('-a', action='store', dest='frame_type',
                        help='Specify frame type. Use <1> for Ralink chips (data frame) and <2> for Atheros chips '
                             '(beacon frame). No CTS supported. Options [1|2]', default='d')
    parser.add_argument('-c', action='store', dest='comm_id',
                        help='Communication ID must be the same on drone and groundstation. 8 characters long. Allowed '
                             'chars are (0123456789abcdef) Example: "aabb0011"', default='aabbccdd')
    return parser.parse_args()


def main():
    global interface_drone_comm, IP_RX, UDP_Port_RX
    parsedArgs = parsearguments()
    interface_drone_comm = parsedArgs.interface_drone_comm
    mode = parsedArgs.mode
    IP_RX = parsedArgs.ip_rx
    UDP_Port_RX = parsedArgs.udp_port_rx
    frame_type = parsedArgs.frame_type

    src = find_mac(interface_drone_comm)
    comm_id = b'\x01\xa6\xF7\x16\xA5\x11'  # has to start with 0x01 # TODO: remove
    # comm_id = bytes(b'\x01'+b'\x01'+bytearray.fromhex(parsedArgs.comm_id)) # TODO: enable feature
    # print("DB_TX_TEL: Communication ID: " + comm_id.hex()) # only works in python 3.5
    print("DB_TX_TEL: Communication ID: " + str(comm_id))

    dbprotocol = DBProtocol(src, dst, UDP_Port_RX, IP_RX, 1606, b'\x01', interface_drone_comm, mode,
                            comm_id, frame_type, b'\x02')

    while True:
        received = dbprotocol.receive_telemetryfromdrone()
        #received= b'$TA\x00\x00\x01\x00\xf0\x00\xf1'
        #time.sleep(0.15)
        if received != False:
            if received[2] == 89:
                received = dbprotocol.finish_dronebridge_ltmframe(received)
                # send a beaconframe so drone telemetry can extract signal strength. MSP RSSI over AUX is also a option
                # Then RSSI field in LTM would be set correctly. But RSSI would be in % which is worse compared to dbm
                dbprotocol.send_beacon()
            sent = dbprotocol.sendto_smartphone(received)
            #print("DB_TX_TEL: Sent "+str(sent)+" bytes to sp")
if __name__ == "__main__":
    main()
