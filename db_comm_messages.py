import json
import configparser

# Creates JSON messages for DB Communication Protocol to be sent out
from itertools import chain


tag = 'DB_COMM_MESSAGE: '
PATH_DRONEBRIDGE_TX_SETTINGS = "/home/cyber/Dokumente/DroneBridgeTX.ini"
PATH_DRONEBRIDGE_RX_SETTINGS = "/home/cyber/Dokumente/DroneBridgeRX.ini"
PATH_WBC_SETTINGS = "/home/cyber/Dokumente/wifibroadcast-1.txt"


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
    else:
        complete_response = read_wbc_settings(complete_response)
    return json.dumps(complete_response)


"""returns a settings change success message"""
def new_settingschangesuccess_message(origin, new_id):
    return json.dumps({'destination': 4, 'type': 'settingssuccess', 'origin': origin, 'id': new_id})


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
    else:
        config.read(PATH_DRONEBRIDGE_RX_SETTINGS)
        section = 'RX'

    for key in config[section]:
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
        settings[key] = config.get(virtual_section, key)

    response_header['settings'] = settings
    return response_header
