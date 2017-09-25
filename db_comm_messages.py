import json
import configparser
import binascii
from itertools import chain


# Creates JSON messages for DB Communication Protocol to be sent out


tag = 'DB_COMM_MESSAGE: '
#PATH_DRONEBRIDGE_TX_SETTINGS = "/home/cyber/Dokumente/DroneBridgeTX.ini"
#PATH_DRONEBRIDGE_RX_SETTINGS = "/home/cyber/Dokumente/DroneBridgeRX.ini"
#PATH_WBC_SETTINGS = "/home/cyber/Dokumente/wifibroadcast-1.txt"
PATH_DRONEBRIDGE_TX_SETTINGS = "/boot/DroneBridgeTX.ini"
PATH_DRONEBRIDGE_RX_SETTINGS = "/boot/DroneBridgeRX.ini"
PATH_WBC_SETTINGS = "/boot/wifibroadcast-1.txt"

# As we send it as a single frame we do not want the payload to be unnecessarily big. Only respond important settings
wbc_settings_blacklist = ["TXMODE", "MAC_RX[0]", "FREQ_RX[0]", "MAC_RX[1]", "FREQ_RX[1]", "MAC_RX[2]", "FREQ_RX[2]",
                          "MAC_RX[3]", "FREQ_RX[3]", "MAC_TX[0]", "FREQ_TX[0]", "MAC_TX[1]", "FREQ_TX[1]",
                          "WIFI_HOTSPOT_NIC", "RELAY", "RELAY_NIC", "RELAY_FREQ", "QUIET"]
db_settings_blacklist = ["ip_drone", "interface_selection", "interface_control", "interface_tel", "interface_video",
                         "interface_comm", "joy_cal"]


"""takes in a request - executes search for settings and creates a response"""
def new_settingsresponse_message(loaded_json, origin):
    complete_response = {}
    complete_response['destination'] = 4
    complete_response['type'] = 'settingsresponse'
    complete_response['response'] = loaded_json['request']
    complete_response['origin'] = origin
    complete_response['id'] = loaded_json['id']
    if loaded_json['request'] == 'dronebridge':
        complete_response = read_dronebridge_settings(complete_response, origin)
    elif loaded_json['request'] == 'wifibroadcast':
        complete_response = read_wbc_settings(complete_response)
    response = json.dumps(complete_response)
    crc32 = binascii.crc32(str.encode(response))
    #return response.encode()+crc32.to_bytes(4, byteorder='big', signed=False)
    return str.encode(response + str(crc32))


"""returns a settings change success message"""
def new_settingschangesuccess_message(origin, new_id):
    command = json.dumps({'destination': 4, 'type': 'settingssuccess', 'origin': origin, 'id': new_id})
    crc32 = binascii.crc32(str.encode(command))
    #return command.encode()+crc32.to_bytes(4, byteorder='big', signed=False)
    return str.encode(command + str(crc32))


"""takes a settings change request - executes it - returns a settings change success message"""
def change_settings(loaded_json, origin):
    # TODO:
    return new_settingschangesuccess_message(origin, loaded_json['id'])


def read_dronebridge_settings(response_header, origin):
    config = configparser.ConfigParser()
    section = ''
    settings = {}
    if origin == 'groundstation':
        config.read(PATH_DRONEBRIDGE_TX_SETTINGS)
        section = 'TX'
    elif origin == 'drone':
        config.read(PATH_DRONEBRIDGE_RX_SETTINGS)
        section = 'RX'

    for key in config[section]:
        if key not in db_settings_blacklist:
            settings[key] = config.get(section, key)

    response_header['settings'] = settings
    return response_header


def read_wbc_settings(response_header):
    virtual_section = 'root'
    settings = {}
    config = configparser.ConfigParser()
    with open(PATH_WBC_SETTINGS, 'r') as lines:
        lines = chain(('['+virtual_section+']',), lines)
        config.read_file(lines)

    for key in config[virtual_section]:
        if key not in wbc_settings_blacklist:
            settings[key] = config.get(virtual_section, key)

    response_header['settings'] = settings
    return response_header


def comm_message_extract_info(message):
    alist = message.rsplit('}',1)
    alist[0] = alist[0]+'}'
    return alist


def check_package_good(extracted_info):
    if str(binascii.crc32(str.encode(extracted_info[0]))) == extracted_info[1]:
        return True
    print(tag+"Bad CRC!")
    return False