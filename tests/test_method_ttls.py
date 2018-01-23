# -*- coding: utf-8 -*-
import pytest
from jussi.cache.ttl import TTL
from jussi.cache.utils import ttl_from_jsonrpc_request
from jussi.request import JussiJSONRPCRequest
from jussi.upstream import _Upstreams
from jussi.upstream import DEFAULT_UPSTREAM_CONFIG


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


dummy_request = AttrDict()
dummy_request.headers = dict()
dummy_request['jussi_request_id'] = '123456789012345'
dummy_request.app = AttrDict()
dummy_request.app.config = AttrDict()
dummy_request.app.config.upstreams = _Upstreams(DEFAULT_UPSTREAM_CONFIG, validate=False)


SBDS_DEFAULT_CACHE = 3


ttl_rpc_req = JussiJSONRPCRequest.from_request(dummy_request, 0, {"id": "1", "jsonrpc": "2.0",
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

non_ttl_rpc_req = JussiJSONRPCRequest.from_request(dummy_request, 0, {"id": "1", "jsonrpc": "2.0",
                                                                      "method": "sbds.get_block", "params": [1000]})


@pytest.mark.parametrize('rpc_req, rpc_resp, last_block_num,expected', [
    # don't cache when last_block_num < response block_num
    (ttl_rpc_req, rpc_resp, 0, TTL.NO_CACHE),
    (ttl_rpc_req, rpc_resp, 999, TTL.NO_CACHE),

    # cache when last_block_num >= response block_num
    (ttl_rpc_req, rpc_resp, 1000, TTL.NO_EXPIRE),
    (ttl_rpc_req, rpc_resp, 1001, TTL.NO_EXPIRE),

    # don't cache when bad/missing response block_num
    (ttl_rpc_req, {}, 2000, TTL.NO_CACHE),

    # don't adjust ttl for non EXPIRE_IF_IRREVERSIBLE methods
    (non_ttl_rpc_req, rpc_resp, 2000, SBDS_DEFAULT_CACHE),


])
def test_ttls(rpc_req, rpc_resp, last_block_num, expected):
    ttl = ttl_from_jsonrpc_request(rpc_req, last_block_num, rpc_resp)
    if isinstance(expected, TTL):
        expected = expected.value
    assert ttl == expected


@pytest.mark.parametrize('ttl,eq', [
    (TTL.NO_CACHE, -1),
    (TTL.DEFAULT_TTL, 3),
    (TTL.NO_EXPIRE, None),
    (TTL.NO_EXPIRE_IF_IRREVERSIBLE, -2),
]
)
def test_ttl_eq(ttl, eq):
    assert ttl == ttl
    assert ttl == eq


@pytest.mark.parametrize('ttl', [
    (TTL.NO_CACHE),
    (TTL.DEFAULT_TTL),
    (TTL.NO_EXPIRE_IF_IRREVERSIBLE)
]
)
def test_ttl_gt(ttl):
    assert ttl > -3


@pytest.mark.parametrize('ttl', [
    (TTL.NO_CACHE),
    (TTL.DEFAULT_TTL),
    (TTL.NO_EXPIRE_IF_IRREVERSIBLE)
]
)
def test_ttl_ge(ttl):
    assert ttl >= -2


@pytest.mark.parametrize('ttl', [
    (TTL.NO_CACHE),
    (TTL.DEFAULT_TTL),
    (TTL.NO_EXPIRE_IF_IRREVERSIBLE)
]
)
def test_ttl_lt(ttl):
    assert ttl < 4


@pytest.mark.parametrize('ttl', [
    (TTL.NO_CACHE),
    (TTL.DEFAULT_TTL),
    (TTL.NO_EXPIRE_IF_IRREVERSIBLE)
]
)
def test_ttl_le(ttl):
    assert ttl <= 3
