# -*- coding: utf-8 -*-
import pytest

from jussi.cache.ttl import TTL
from jussi.cache.utils import irreversible_ttl
from jussi.request.jsonrpc import JSONRPCRequest
from jussi.request.jsonrpc import from_http_request as jsonrpc_from_request
from .conftest import make_request
dummy_request = make_request()


ttl_rpc_req = jsonrpc_from_request(dummy_request, 0, {"id": "1", "jsonrpc": "2.0",
                                                      "method": "get_block", "params": [1000]})
rpc_resp = {
    "id": 1,
    "result": {
        "previous": "000003e7c4fd3221cf407efcf7c1730e2ca54b05",
        "timestamp": "2016-03-24T16:55:30",
        "witness": "initminer",
        "transaction_merkle_root": "0000000000000000000000000000000000000000",
        "extensions": [],
        "witness_signature": "207f15578cac20ac0e8af1ebb8f463106b8849577e21cca9fc60da146d1d95df88072dedc6ffb7f7f44a9185bbf9bf8139a5b4285c9f423843720296a44d428856",
        "transactions": [],
        "block_id": "000003e8b922f4906a45af8e99d86b3511acd7a5",
        "signing_key": "STM8GC13uCZbP44HzMLV6zPZGwVQ8Nt4Kji8PapsPiNq1BK153XTX",
        "transaction_ids": []}}

non_ttl_rpc_req = jsonrpc_from_request(dummy_request, 0, {"id": "1", "jsonrpc": "2.0",
                                                          "method": "sbds.method", "params": [1000]})


@pytest.mark.parametrize('rpc_req, rpc_resp, last_block_num, expected', [
    # don't cache when last_block_num < response block_num
    (ttl_rpc_req, rpc_resp, 1, TTL.DEFAULT_TTL),
    (ttl_rpc_req, rpc_resp, 999, TTL.DEFAULT_TTL),

    # cache when last_block_num >= response block_num
    (ttl_rpc_req, rpc_resp, 1000, TTL.DEFAULT_TTL),
    (ttl_rpc_req, rpc_resp, 1001, TTL.DEFAULT_TTL),

    # don't cache when bad/missing response block_num
    (ttl_rpc_req, {}, 2000, TTL.NO_CACHE),
    (ttl_rpc_req, {}, None, TTL.NO_CACHE),

])
def test_ttls(rpc_req, rpc_resp, last_block_num, expected):
    ttl = irreversible_ttl(rpc_resp, last_block_num)
    if isinstance(expected, TTL):
        expected = expected.value
    assert ttl == expected


@pytest.mark.parametrize('ttl,eq', [
    (TTL.NO_CACHE, -1),
    (TTL.DEFAULT_TTL, 3),
    (TTL.NO_EXPIRE, None),
    (TTL.DEFAULT_EXPIRE_IF_IRREVERSIBLE, -2),
]
)
def test_ttl_eq(ttl, eq):
    assert ttl == ttl
    assert ttl == eq


@pytest.mark.parametrize('ttl', [
    (TTL.NO_CACHE),
    (TTL.DEFAULT_TTL),
    (TTL.DEFAULT_EXPIRE_IF_IRREVERSIBLE)
]
)
def test_ttl_gt(ttl):
    assert ttl > -3


@pytest.mark.parametrize('ttl', [
    (TTL.NO_CACHE),
    (TTL.DEFAULT_TTL),
    (TTL.DEFAULT_EXPIRE_IF_IRREVERSIBLE)
]
)
def test_ttl_ge(ttl):
    assert ttl >= -2


@pytest.mark.parametrize('ttl', [
    (TTL.NO_CACHE),
    (TTL.DEFAULT_TTL),
    (TTL.DEFAULT_EXPIRE_IF_IRREVERSIBLE)
]
)
def test_ttl_lt(ttl):
    assert ttl < 4


@pytest.mark.parametrize('ttl', [
    (TTL.NO_CACHE),
    (TTL.DEFAULT_TTL),
    (TTL.DEFAULT_EXPIRE_IF_IRREVERSIBLE)
]
)
def test_ttl_le(ttl):
    assert ttl <= 3
