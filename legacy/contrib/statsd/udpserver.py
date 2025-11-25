#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class EchoServerProtocol:

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        message = data.decode()
        [print(line) for line in message.split('\n')]


loop = asyncio.get_event_loop()
print("Starting UDP server")
# One protocol instance will be created to serve all client requests
listen = loop.create_datagram_endpoint(
    EchoServerProtocol, local_addr=('0.0.0.0', 8125))
transport, protocol = loop.run_until_complete(listen)

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass

transport.close()
loop.close()
