import json

import zmq
from zmq.asyncio import Context

import logger
from commands import Command

log = logger.get(__name__)


class Client:
    def __init__(self, url: str, name: str):
        self.name = name
        context = Context.instance()
        socket = context.socket(zmq.DEALER)
        socket.setsockopt_string(zmq.IDENTITY, name)
        socket.connect(f'tcp://{url}')
        log.info(f'Connecting to {url}')
        self.socket = socket

    async def greet(self):
        log.info('Sending greetings to router')
        await self.socket.send_multipart([b"GREET", b""])

    async def send(self, command: Command, chunk):
        await self.socket.send_multipart([command, chunk])

    async def run(self, callback):
        await self.greet()
        while True:
            tag, params, audio = await self.socket.recv_multipart()
            params_decode = params.decode()
            callback(tag.decode(), json.loads(params_decode) if len(params_decode) else None, audio)
