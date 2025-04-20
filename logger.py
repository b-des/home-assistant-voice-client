import logging
import sys
from logging import handlers

log = logging.getLogger('')
log.setLevel(logging.INFO)
format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(format)
log.addHandler(ch)

fh = handlers.RotatingFileHandler("logs.log", maxBytes=(1048576 * 5), backupCount=7)
fh.setFormatter(format)
log.addHandler(fh)


def get(name):
    return logging.getLogger(name)
