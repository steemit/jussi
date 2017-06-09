# coding=utf-8
import sys
import asyncio
import zlib
import ujson
from aiocache.serializers import StringSerializer

class CompressionSerializer(StringSerializer):

    # This is needed because zlib works with bytes.
    # this way the underlying backend knows how to
    # store/retrieve values
    encoding = None

    def dumps(self, value):
        if isinstance(value, bytes):
            return zlib.compress(value)
        if isinstance(value, str):
            return zlib.compress(value.encode())
        else:
            return zlib.compress(ujson.dumps(value).encode())

    def loads(self, value):
        if value:
            return ujson.loads(zlib.decompress(value).decode())
