import asyncio
import json

import zmq
from zmq.asyncio import Context

import logger
from commands import Command
from config import config

log = logger.get(__name__)

SUB_FILTER = 'request'


class Client:
    def __init__(self, url: str, name: str):
        self.name = name
        context = Context.instance()
        socket = context.socket(zmq.DEALER)
        socket.setsockopt_string(zmq.IDENTITY, name)
        socket.connect(f'tcp://{url}')

        self.pub = context.socket(zmq.PUB)
        self.pub.bind(f"tcp://*:{config.get('ZEROMQ_PEERS_PORT')}")

        self.sub = context.socket(zmq.SUB)
        self.sub.setsockopt_string(zmq.SUBSCRIBE, SUB_FILTER)

        log.info(f'Connecting to {url}')
        self.socket = socket

    async def greet(self):
        log.info('Sending greetings to router')
        await self.socket.send_multipart([b"GREET", b""])

    async def publish(self, message):
        log.info(f'Publish message to peers: {message}')
        self.pub.send_string(message)

    async def subscribe(self, ip):
        log.info(f'Subscribing to {ip}')
        self.sub.connect(f"tcp://{ip}:{config.get('ZEROMQ_PEERS_PORT')}")

    async def send(self, command: Command, chunk):
        await self.socket.send_multipart([command, chunk])

    async def peer_listener(self, callback):
        while True:
            msg = await self.sub.recv_string()
            msg = msg.split()
            log.info(f"Got message from peer: {msg}")
            callback(msg[1])

    async def router_listen(self, callback):
        await self.greet()
        while True:
            tag, params, audio = await self.socket.recv_multipart()
            params_decode = params.decode()
            callback(tag.decode(), json.loads(params_decode) if len(params_decode) else None, audio)

    async def start(self, router_listener_callback, peer_listener_callback):
        await asyncio.gather(self.router_listen(router_listener_callback), self.peer_listener(peer_listener_callback))
