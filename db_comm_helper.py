def find_mac(interface):
    f = open("/sys/class/net/"+interface+"/address", 'r',)
    mac_bytes = bytes(bytearray.fromhex(f.read(17).replace(':', '')))
    f.close()
    return mac_bytes

def find_smartphone_ip():
    # USB Tethering
    #ip route show 0.0.0.0/0 dev usb0 | cut -d\  -f3

    # WIFI Hotspot:
    # "192.168.2.2"
    pass