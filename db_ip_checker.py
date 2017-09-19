import time
import sysv_ipc
from subprocess import *

# memory map
# 111111 = smartphone ip

def find_smartphone_ip():
    # USB Tethering
    r = check_output('ip route show 0.0.0.0/0 dev usb0 | cut -d\  -f3', shell=True)
    if r == b'':
       return '192.168.2.2'
    # b'192.168.42.129\n'
    return str(r,'utf-8')

def main():
    print("DB_IPCHECKER: starting")
    keeprunning = True
    memory = sysv_ipc.SharedMemory(111111, sysv_ipc.IPC_CREX)

    while(keeprunning):
        time.sleep(2)
        memory.write(find_smartphone_ip())


if __name__ == "__main__":
    main()