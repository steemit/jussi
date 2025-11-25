# -*- coding: utf-8 -*-
"""
These are the settings for the sanic framework.
This is not the place to change settings for jsonrpc requests,
those belong in the upstreams config file.

"""

REQUEST_MAX_SIZE = 262144  # 256KB uncompressed
REQUEST_TIMEOUT = 5  # 5 seconds
RESPONSE_TIMEOUT = 65  # 65 seconds
KEEP_ALIVE = True
KEEP_ALIVE_TIMEOUT = 100  # 100 seconds
GRACEFUL_SHUTDOWN_TIMEOUT = 15.0  # 15 sec
