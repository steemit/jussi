# coding=utf-8
import sys
import asyncio
import zlib
import ujson

import diskcache


class JSONDisk(diskcache.Disk):
    def __init__(self, directory, compress_level=1, **kwargs):
        self.compress_level = compress_level
        super(JSONDisk, self).__init__(directory, **kwargs)

    def put(self, key):
        return super(JSONDisk, self).put(key)

    def get(self, key, raw):
        data = super(JSONDisk, self).get(key, raw)
        return ujson.loads(zlib.decompress(data).decode())

    def store(self, value, read):
        if not read:
            if isinstance(value, bytes):
                json_bytes = value
            elif isinstance(value, str):
                json_bytes = value.encode()
            else:
                json_bytes = ujson.dumps(value).encode()
            data = zlib.compress(json_bytes, self.compress_level)
        return super(JSONDisk, self).store(data, read)

    def fetch(self, mode, filename, value, read):
        data = super(JSONDisk, self).fetch(mode, filename, value, read)
        if not read:
            data = ujson.loads(zlib.decompress(data).decode())
        return data
