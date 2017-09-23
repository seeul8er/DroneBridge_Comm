import time
import sysv_ipc
from subprocess import *

# memory map
# 111111 = smartphone ip
key_smartphone_ip_sm = 1111
key_smartphone_ip_sem = 1112

class DB_IP_GETTER():

    def __init__(self):
        try:
            self.sem = sysv_ipc.Semaphore(key_smartphone_ip_sem, sysv_ipc.IPC_CREX)
        except sysv_ipc.ExistentialError:
            # One of my peers created the semaphore already
            self.sem = sysv_ipc.Semaphore(key_smartphone_ip_sem)
            # Waiting for that peer to do the first acquire or release
            while not self.sem.o_time:
                time.sleep(.1)
        else:
            # Initializing sem.o_time to nonzero value
            self.sem.release()
        try:
            self.memory = sysv_ipc.SharedMemory(key_smartphone_ip_sm, sysv_ipc.IPC_CREX)
        except sysv_ipc.ExistentialError:
            self.memory = sysv_ipc.SharedMemory(key_smartphone_ip_sm)

    def return_smartphone_ip(self):
        self.sem.acquire()
        ip = str(self.memory.read(key_smartphone_ip_sm))
        ip = ip[2:]
        self.sem.release()
        return ip


def find_smartphone_ip():
    # USB Tethering
    r = check_output('ip route show 0.0.0.0/0 dev usb0 | cut -d\  -f3', shell=True)
    #if r == b'':
       #return "192.168.2.2"
    # b'192.168.42.129\n'
    return "192.168.2.2"
    #return str(r,'utf-8')

def main():
    print("DB_IPCHECKER: starting")
    keeprunning = True
    try:
        memory = sysv_ipc.SharedMemory(key_smartphone_ip_sm, sysv_ipc.IPC_CREX)
    except sysv_ipc.ExistentialError:
        memory = sysv_ipc.SharedMemory(key_smartphone_ip_sm)

    while(keeprunning):
        time.sleep(2)

        try:
            sem = sysv_ipc.Semaphore(key_smartphone_ip_sem, sysv_ipc.IPC_CREX)
        except sysv_ipc.ExistentialError:
            # One of my peers created the semaphore already
            sem = sysv_ipc.Semaphore(key_smartphone_ip_sem)
            # Waiting for that peer to do the first acquire or release
            while not sem.o_time:
                time.sleep(.1)
        else:
            # Initializing sem.o_time to nonzero value
            sem.release()

        sem.acquire()
        memory.write(find_smartphone_ip())
        ip = str(memory.read(key_smartphone_ip_sm))
        ip = ip[2:]
        #print(ip)
        sem.release()


if __name__ == "__main__":
    main()