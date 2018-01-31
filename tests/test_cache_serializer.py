# -*- coding: utf-8 -*-

import pytest
from jussi.cache.serializers import CompressionSerializer


@pytest.mark.parametrize('value,expected', [
    [1, b'x\x9c3\x04\x00\x002\x002'],
    ['1', b'x\x9cS2T\x02\x00\x00\xed\x00v'],
    [b'1', b'x\x9cS2T\x02\x00\x00\xed\x00v'],
    [{'a': 1, 'b': '2', 'c': b'3', 'd': {}, 'e': []},
        b'x\x9c\xabVJT\xb22\xd4QJR\xb2R2R\xd2QJ\x06\xd2\xc6@:E\xc9\xaa\xbaVG)U\xc9*:\xb6\x16\x00\x9d\n\x08\xdc'],
    [[1, '2', b'3'], b'x\x9c\x8b6\xd4Q2R\xd2Q2V\x8a\x05\x00\rB\x02/']
])
def test_dumps(value, expected):
    c = CompressionSerializer()
    assert c.dumps(value) == expected


@pytest.mark.parametrize('expected,value', [
    [1, b'x\x9c3\x04\x00\x002\x002'],
    ['1', b'x\x9cS2T\x02\x00\x00\xed\x00v'],
    ['1', b'x\x9cS2T\x02\x00\x00\xed\x00v'],
    [{'a': 1, 'b': '2', 'c': '3', 'd': {}, 'e': []},
        b'x\x9c\xabVJT\xb22\xd4QJR\xb2R2R\xd2QJ\x06\xd2\xc6@:E\xc9\xaa\xbaVG)U\xc9*:\xb6\x16\x00\x9d\n\x08\xdc'],
    [[1, '2', '3'], b'x\x9c\x8b6\xd4Q2R\xd2Q2V\x8a\x05\x00\rB\x02/']
])
def test_loads(expected, value):
    c = CompressionSerializer()
    assert c.loads(value) == expected


def test_roundtrip(jrpc_response):
    c = CompressionSerializer()
    assert c.loads(c.dumps(jrpc_response)) == jrpc_response
