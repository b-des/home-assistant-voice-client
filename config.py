import os
import netifaces

from dotenv import dotenv_values


def get_mac_address(interface="eth0"):
    print(netifaces.interfaces())
    return netifaces.ifaddresses(netifaces.interfaces()[1])[netifaces.AF_LINK][0]['addr']


config = {
    **os.environ,
    **dotenv_values(".env"),
    'MAC': get_mac_address()
}
