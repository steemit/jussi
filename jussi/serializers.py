# -*- coding: utf-8 -*-
import zlib
from typing import AnyStr
from typing import Optional
from typing import Union

import ujson
from aiocache.serializers import StringSerializer


class CompressionSerializer(StringSerializer):

    # This is needed because zlib works with bytes.
    # this way the underlying backend knows how to
    # store/retrieve values
    encoding = None

    def dumps(self, value: Union[AnyStr, dict]) -> bytes:
        if isinstance(value, bytes):
            return zlib.compress(value)
        elif isinstance(value, str):
            return zlib.compress(value.encode())
        # dict
        return zlib.compress(ujson.dumps(value).encode())

    def loads(self, value: Optional[bytes]) -> Optional[dict]:
        if value:
            return ujson.loads(zlib.decompress(value).decode())
        return None
