import base64
import json
from socket import *
import crc8
import time
import select
import psutil
from subprocess import call

from bpf import attach_filter

RADIOTAP_HEADER = b'\x00\x00\x0c\x00\x04\x80\x00\x00\x0c\x00\x18\x00'
DB_FRAME_VERSION = b'\x01'
TO_DRONE = b'\x01'
TO_GROUND = b'\x02'
PORT_CONTROLLER = b'\x01'
PORT_TELEMETRY = b'\x02'
ETH_TYPE = b"\x88\xAB"
DB_80211_HEADER_LENGTH = 24
UDP_BUFFERSIZE = 512
MONITOR_BUFFERSIZE = 128
LTM_PORT_SMARTPHONE = 5001


class DBProtocol:
    ip_smartp = "192.168.42.129"


    def __init__(self, src_mac, dst_mac, udp_port_rx, ip_rx, udp_port_smartphone, comm_direction, interface_drone_comm,
                 mode):
        self.src_mac = src_mac
        self.dst_mac = dst_mac
        self.udp_port_rx = udp_port_rx  # 1604
        self.ip_rx = ip_rx
        self.udp_port_smartphone = udp_port_smartphone
        # communication direction: the direction the packets will have when sent from the application
        self.comm_direction = comm_direction # set to 0x01 if program runs on groundst. and to 0x02 if runs on drone
        self.interface = interface_drone_comm  # the long range interface
        self.mode = mode
        if self.mode == 'wifi':
            self.short_mode = 'w'
        else:
            self.short_mode = 'm'
        self.comm_sock = self._open_comm_sock()
        if self.comm_direction == TO_DRONE:
            self.android_sock = self._open_android_udpsocket()
        self.changed = False
        self.signal_ground = b'\x00'  # signal quality that the groundstation measures [dBm]
        self.signal_drone = 0  # signal quality that the drone measures [dBm]

    def receive_datafromdrone(self):
        if self.mode == 'wifi':
            try:
                data, addr = self.comm_sock.recvfrom(UDP_BUFFERSIZE)
                return data
            except Exception as e:
                print(str(e) + ": Drone is not ready or has wrong IP address of groundstation. Sending hello-packet")
                self._send_hello()
                return False
        else:
            try:
                while True:
                    data = self._pars_packet(bytearray(self.comm_sock.recv(MONITOR_BUFFERSIZE)))
                    if data != False:
                        return data
            except Exception as e:
                print(str(e) + ": Error receiving data form drone (monitor mode)")
                return False

    def receive_process_datafromgroundstation(self):
        # check if the socket received something and process data
        if self.mode == "wifi":
            readable, writable, exceptional = select.select([self.comm_sock], [], [], 0)
            if readable:
                data, addr = self.comm_sock.recvfrom(UDP_BUFFERSIZE)
                if data.decode() == "tx_hello_packet":
                    self.ip_rx = addr[0]
                    self.updateRouting()
                    print("Updated goundstation IP-address to: " + str(self.ip_rx))
                else:
                    print("New data from groundstation: " + data.decode())
        else:
            readable, writable, exceptional = select.select([self.comm_sock], [], [], 0)
            if readable:
                # bytearray(self.comm_sock.recv(MONITOR_BUFFERSIZE)).hex()
                data = self._pars_packet(bytearray(self.comm_sock.recv(MONITOR_BUFFERSIZE)))
                # TODO execute request from groundstation (GoPro settings/WBC settings/DroneBridge settings)

    def process_smartphonerequests(self, last_keepalive):
        """See if smartphone told the groundstation to do something. Returns recent keep-alive time"""
        r, w, e = select.select([self.android_sock], [], [], 0)
        if r:
            smartph_data, android_addr = self.android_sock.recvfrom(UDP_BUFFERSIZE)
            return self._process_smartphonecommand(smartph_data.decode(), last_keepalive)
        return last_keepalive

    def check_smartphone_ready(self):
        """Checks if smartphone app is ready for data. Returns IP of smartphone"""
        sock_status = select.select([self.android_sock], [], [], 0.05)
        if sock_status[0]:
            new_data, new_addr = self.android_sock.recvfrom(UDP_BUFFERSIZE)
            if new_data.decode() == "smartphone_is_still_here":
                print("Smartphone is ready")
                self.ip_smartp = new_addr[0]
                print("Sending future data to smartphone - " + self.ip_smartp + ":" + str(self.udp_port_smartphone))
                return True
        return False

    def finish_dronebridge_ltmframe(self, frame):
        """Adds information to custom LTM-Frame on groundstation side"""
        if self.mode == 'wifi':
            with open('/proc/net/wireless') as fp:
                for line in fp:
                    if line.startswith(self.interface, 1, len(self.interface) + 1):
                        result = line.split(" ", 8)
                        frame[5] = int(result[5][:-1])
                        frame[6] = int(result[7][1:-1])
                        fp.close()
                        return bytes(frame)
            return frame
        else:
            # frame[5] = int((int(self.datarate)*500)/1000)
            frame[6] = self.signal_ground
            return bytes(frame)

    def sendto_smartphone(self, raw_data):
        """Sends data to smartphone. Socket is nonblocking so we need to wait till it becomes"""
        while True:
            r, w, e = select.select([], [self.android_sock], [], 0)
            if w:
                try:
                    return self.android_sock.sendto(raw_data, (self.ip_smartp, LTM_PORT_SMARTPHONE))
                except:
                    print("Could not send to smartphone. Make sure it is connected and has USB tethering enabled.")
                    return 0

    def sendto_groundstation(self, data_bytes, port_bytes):
        """Call this function to send stuff to the groundstation or directly to smartphone"""
        if self.mode == "wifi":
            num = self._sendto_tx_wifi(data_bytes)
        else:
            num = self._send_monitor(data_bytes, port_bytes, TO_GROUND)
        return num

    def send_dronebridge_frame(self):
        DroneBridgeFrame = b'$TY' + self.short_mode.encode() + chr(int(psutil.cpu_percent(interval=None))).encode() + \
                           bytes([self.signal_drone]) + b'\x00\x00\x00\x00\x00\x00\x00'
        self.sendto_groundstation(DroneBridgeFrame, PORT_TELEMETRY)

    def send_beacon(self):
        self._sendto_drone('groundstation_beacon'.encode(), PORT_TELEMETRY)

    def updateRouting(self):
        print("Update iptables to send GoPro stream to " + str(self.ip_rx))
        if self.changed:
            call("iptables -t nat -R PREROUTING 1 -p udp --dport 8554 -j DNAT --to " + str(self.ip_rx))
        else:
            call("iptables -t nat -I PREROUTING 1 -p udp --dport 8554 -j DNAT --to " + str(self.ip_rx))
            self.changed = True

    def getsmartphonesocket(self):
        return self.android_sock

    def getcommsocket(self):
        return self.comm_sock

    def _pars_packet(self, packet):
        """Parses Packet and checks if it is for us. Returns False if not or packet payload if it is"""
        rth_length = packet[2]
        # print("Packet with radiotapheader length: "+str(rth_length))
        if self._frameis_ok(packet, rth_length):
            # TODO: always get correct bytes independent of used wireless driver. This one is for Atheros (TPLink)
            if self.comm_direction == TO_DRONE:
                self.signal_ground = packet[14]
                self.datarate = packet[9]
            else:
                self.signal_drone = packet[30]
            return packet[(rth_length + DB_80211_HEADER_LENGTH):len(packet)]
        else:
            return False

    def _frameis_ok(self, packet, radiotap_header_length):
        # TODO: check crc8 of header or something
        return True

    def _process_smartphonecommand(self, raw_data, thelast_keepalive):
        print("Received from SP: " + raw_data)
        if raw_data == "smartphone_is_still_here":
            return time.time()
        if not self._process_smartphone_dbprotocol(raw_data):
            print("smartphone command could not be processed correctly")
        return thelast_keepalive

    def _process_smartphone_dbprotocol(self, raw_data):
        status = False
        raw_data_json = json.loads(raw_data)
        if raw_data_json['type'] == 0:
            print("A message for the local controller (RC data overwrite)")
            # TODO pass parameters over to local controller via FIFO-Pipe
        elif raw_data_json['type'] == 1:
            print("A message for the drone flight controller")  # port 0
            status = self._sendto_drone(base64.b64decode(raw_data_json['MSP']), PORT_CONTROLLER)
        elif raw_data_json['type'] == 2:  # port 1 or port 3 (not sure yet)
            print("A message to change settings")
            # TODO change settings
        elif raw_data_json['type'] == 3:  # port 1
            print("A message to change GoPro-Settings")
            status = self._sendto_drone(raw_data, PORT_TELEMETRY)
        else:
            print("unknown command from smartphone")
        return status

    def _send_hello(self):
        """Send this in wifi mode to let the drone know about IP of groundstation"""
        self.comm_sock.sendto("tx_hello_packet".encode(), (self.ip_rx, self.udp_port_rx))

    def _sendto_drone(self, data_bytes, port_bytes):
        """Call this function to send stuff to the drone!"""
        if self.mode == "wifi":
            num = self._sendto_rx_wifi(data_bytes, port_bytes)
        else:
            num = self._send_monitor(data_bytes, port_bytes, TO_DRONE)
        return num

    def _sendto_tx_wifi(self, data_bytes):
        """Sends LTM and other stuff to groundstation/smartphone in wifi mode"""
        while True:
            r, w, e = select.select([], [self.comm_sock], [], 0)
            if w:
                num = self.comm_sock.sendto(data_bytes, (self.ip_rx, self.udp_port_rx))
                return num

    def _sendto_rx_wifi(self, raw_data_bytes, port_bytes):
        """
        Send a packet to drone in wifi mode
        depending on message type different ports/programmes aka frontends on the drone need to be addressed
        """
        if port_bytes == PORT_CONTROLLER:
            print("Sending MSP command to RX Controller (wifi)")
            try:
                raw_socket = socket(AF_PACKET, SOCK_RAW)
                raw_socket.bind((self.interface, 0))
                num = raw_socket.send(self.dst_mac + self.src_mac + ETH_TYPE + raw_data_bytes)
                raw_socket.close()
            except Exception as e:
                print(str(e) + ": Are you sure this program was run as superuser?")
                return False
            print("Sent it! " + str(num))
        else:
            print("Sending a message to telemetry frontend on drone")
            num = self.comm_sock.sendto(raw_data_bytes, (self.ip_rx, self.udp_port_rx))
        return num

    def _send_monitor(self, data_bytes, port_bytes, direction):
        """Send a packet in monitor mode"""
        payload_length_bytes = [bytes(chr(len(data_bytes) >> i & 0xff).encode()) for i in (24, 16, 8, 0)]
        crc_content = bytes(bytearray(DB_FRAME_VERSION + port_bytes + direction + payload_length_bytes[3]
                                      + payload_length_bytes[2]))
        crc = crc8.crc8()
        crc.update(crc_content)
        ieee_min_header_mod = bytes(
            bytearray(b'\x08\x00\x00\x00' + self.dst_mac + self.src_mac + crc_content + crc.digest() + b'\x10\x86'))
        while True:
            r, w, e = select.select([], [self.comm_sock], [], 0)
            if w:
                num = self.comm_sock.send(RADIOTAP_HEADER + ieee_min_header_mod + data_bytes)
                break
        return num

    def _open_comm_sock(self):
        """Opens a socket that talks to drone (on tx side) or groundstation (on rx side)"""
        if self.mode == "wifi":
            return self._open_comm_udpsocket()
        else:
            return self._open_comm_monitorsocket()

    def _open_comm_udpsocket(self):
        print("Opening UDP-Socket for DroneBridge communication")
        sock = socket(AF_INET, SOCK_DGRAM)
        server_address = ('', self.udp_port_rx)
        sock.bind(server_address)
        if self.comm_direction == b'\x00':
            sock.settimeout(1)
        else:
            sock.setblocking(False)
        return sock

    def _open_comm_monitorsocket(self):
        print("Opening socket for monitor mode")
        raw_socket = socket(AF_PACKET, SOCK_RAW, htons(0x0004))
        raw_socket.bind((self.interface, 0))
        if self.comm_direction == TO_GROUND:
            raw_socket.setblocking(False)
            raw_socket = attach_filter(raw_socket, TO_DRONE, self.src_mac)
        else:
            raw_socket = attach_filter(raw_socket, TO_GROUND, self.src_mac)
        return raw_socket

    def _open_android_udpsocket(self):
        print("Opening UDP-Socket to smartphone")
        sock = socket(AF_INET, SOCK_DGRAM)
        address = ('', self.udp_port_smartphone)
        sock.bind(address)
        sock.setblocking(False)
        print("Done")
        return sock
