from enum import Enum


class Command(Enum):
    START_SPEAK = b'START_SPEAK'
    CONTINUE = b'CONTINUE'
    FINISH = b'FINISH'
    CANCEL = b'CANCEL'
    CLEAR = b'CLEAR'
