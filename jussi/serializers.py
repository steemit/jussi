# -*- coding: utf-8 -*-
import logging
import zlib
from typing import AnyStr
from typing import Optional
from typing import Union

import ujson
from aiocache.serializers import StringSerializer

logger = logging.getLogger('sanic')


class CompressionSerializer(StringSerializer):

    # This is needed because zlib works with bytes.
    # this way the underlying backend knows how to
    # store/retrieve values
    encoding = None

    def dumps(self, value: Union[AnyStr, dict]) -> bytes:
        # FIXME handle structs with bytes vals, eg, [1, '2', b'3']
        # currently self.loads(self.dumps([1, '2', b'3'])) == [1, '2', '3']
        return zlib.compress(ujson.dumps(value).encode())

    def loads(self, value) -> Optional[dict]:
        if value:
            return ujson.loads(zlib.decompress(value))
        return None
