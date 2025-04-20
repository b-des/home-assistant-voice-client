import os
import netifaces

from dotenv import dotenv_values


def get_mac_address(interface="eth0"):
    print(netifaces.interfaces())
    return netifaces.ifaddresses(netifaces.interfaces()[1])[netifaces.AF_LINK][0]['addr']


config = {
    **dotenv_values(".env"),
    **os.environ,
    'MAC': get_mac_address()
}
