# -*- coding: utf-8 -*-
import pytest

from jussi.cache.backends import SimpleMaxTTLMemoryCache
from jussi.cache.cache_group import CacheGroup
from jussi.cache.utils import jsonrpc_cache_key
from jussi.request import JussiJSONRPCRequest
from .extra_caches import SimpleMemoryCache2
from .extra_caches import SimpleMemoryCache3
from .extra_caches import SimpleMemoryCache4

jrpc_req_1 = JussiJSONRPCRequest.from_request({
    "id": "1", "jsonrpc": "2.0",
    "method": "get_block", "params": [1000]
})

jrpc_resp_1 = {
    "id": 2,
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

error_response = {"id": "1", "jsonrpc": "2.0", "error": {}}

batch1_jrpc = [JussiJSONRPCRequest.from_request({
    "id": _id, "jsonrpc": "2.0",
    "method": "get_block", "params": [1000]
}) for _id in range(10)]
batch2_jrpc = [JussiJSONRPCRequest.from_request({
    "id": _id, "jsonrpc": "2.0", "method": "get_block",
    "params": [1000]
}) for _id in range(20, 30)]

cached_resp1 = [None for i in batch1_jrpc]
cached_resp2 = [
    None,
    {"id": 99, "jsonrpc": "2.0", "method": "get_block", "params": [1000]},
    None,
    {"id": 98, "jsonrpc": "2.0", "method": "get_block", "params": [1000]}]
expected2 = [None,
             {
                 "id": 1, "jsonrpc": "2.0",
                 "method": "get_block", "params": [1000]
             },
             None,
             {
                 "id": 3, "jsonrpc": "2.0",
                 "method": "get_block", "params": [1000]
             },
             ]

request = JussiJSONRPCRequest.from_request({
    "id": "1", "jsonrpc": "2.0",
    "method": "get_block", "params": [1000]
})
request2 = JussiJSONRPCRequest.from_request({
    "id": "1", "jsonrpc": "2.0", "method": "call",
    "params": ["database_api", "get_block", [1000]]
})
response = {
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
bad_response1 = {
    "id": 1,
    "result": {
        "previous": "000003e7c4fd3221cf407efcf7c1730e2ca54b05",
        "timestamp": "2016-03-24T16:55:30",
        "witness": "initminer",
        "transaction_merkle_root": "0000000000000000000000000000000000000000",
        "extensions": [],
        "witness_signature": "207f15578cac20ac0e8af1ebb8f463106b8849577e21cca9fc60da146d1d95df88072dedc6ffb7f7f44a9185bbf9bf8139a5b4285c9f423843720296a44d428856",
        "transactions": [],
        "block_id": "00000",
        "signing_key": "STM8GC13uCZbP44HzMLV6zPZGwVQ8Nt4Kji8PapsPiNq1BK153XTX",
        "transaction_ids": []}}

bad_response2 = {
    "id": 1,
    "result": {
        "previous": "000003e7c4fd3221cf407efcf7c1730e2ca54b05",
        "timestamp": "2016-03-24T16:55:30",
        "witness": "initminer",
        "transaction_merkle_root": "0000000000000000000000000000000000000000",
        "extensions": [],
        "witness_signature": "207f15578cac20ac0e8af1ebb8f463106b8849577e21cca9fc60da146d1d95df88072dedc6ffb7f7f44a9185bbf9bf8139a5b4285c9f423843720296a44d428856",
        "transactions": [],
        "block_id": "000004e8b922f4906a45af8e99d86b3511acd7a5",
        "signing_key": "STM8GC13uCZbP44HzMLV6zPZGwVQ8Nt4Kji8PapsPiNq1BK153XTX",
        "transaction_ids": []}}


async def test_cache_group_clear():
    caches = [SimpleMaxTTLMemoryCache(),
              SimpleMemoryCache2(),
              SimpleMemoryCache3(),
              SimpleMemoryCache4()
              ]
    for cache in caches:
        await cache.clear()
    cache_group = CacheGroup(caches)

    for cache in caches:
        await cache.set('key', 'value')
    await cache_group.clear()

    assert await cache_group.get('key') is None


async def test_cache_group_get():
    caches = [SimpleMaxTTLMemoryCache(),
              SimpleMemoryCache2(),
              SimpleMemoryCache3(),
              SimpleMemoryCache4()
              ]
    for cache in caches:
        await cache.clear()
    cache_group = CacheGroup(caches)
    assert caches[0] is not caches[1]

    await cache_group._caches[0].set('key', 0)
    assert await cache_group._caches[0].get('key') == 0

    await cache_group._caches[1].set('key', 1)
    assert await cache_group._caches[0].get('key') == 0
    assert await cache_group._caches[1].get('key') == 1

    await cache_group._caches[2].set('key', 2)
    assert await cache_group._caches[0].get('key') == 0
    assert await cache_group._caches[1].get('key') == 1
    assert await cache_group._caches[2].get('key') == 2

    await cache_group._caches[3].set('key', 3)
    assert await cache_group._caches[0].get('key') == 0
    assert await cache_group._caches[1].get('key') == 1
    assert await cache_group._caches[2].get('key') == 2
    assert await cache_group._caches[3].get('key') == 3

    assert await cache_group.get('key') == 0
    await cache_group._caches[0].delete('key')

    assert await cache_group.get('key') == 1
    await cache_group._caches[1].delete('key')
    assert await cache_group.get('key') == 2
    await cache_group._caches[2].delete('key')
    assert await cache_group.get('key') == 3


async def test_cache_group_set():
    caches = [SimpleMaxTTLMemoryCache(),
              SimpleMemoryCache2(),
              SimpleMemoryCache3(),
              SimpleMemoryCache4()
              ]
    for cache in caches:
        await cache.clear()
    cache_group = CacheGroup(caches)

    await cache_group.set('key', 1)
    for i, cache in enumerate(caches):
        assert await cache.get('key', i)


async def test_cache_group_multi_get():
    caches = [SimpleMaxTTLMemoryCache(),
              SimpleMemoryCache2(),
              SimpleMemoryCache3(),
              SimpleMemoryCache4()
              ]
    for cache in caches:
        await cache.clear()
    cache_group = CacheGroup(caches)

    keys = [str(i) for i in range(len(caches))]
    values = [str(i) for i in range(len(caches))]
    await cache_group.multi_set(zip(keys, values, [None for key in keys]))

    assert await cache_group.multi_get(keys) == values
    assert await caches[0].multi_get(keys) == values
    assert await caches[1].multi_get(keys) == values
    assert await caches[2].multi_get(keys) == values
    assert await caches[3].multi_get(keys) == values

    await cache_group._caches[0].clear()
    assert await cache_group.multi_get(keys) == values
    assert await cache_group._caches[1].multi_get(keys) == values
    assert await cache_group._caches[2].multi_get(keys) == values
    assert await cache_group._caches[3].multi_get(keys) == values

    await cache_group._caches[1].clear()
    assert await cache_group.multi_get(keys) == values
    assert await cache_group._caches[2].multi_get(keys) == values
    assert await cache_group._caches[3].multi_get(keys) == values

    await cache_group._caches[2].clear()
    assert await cache_group.multi_get(keys) == values
    assert await cache_group._caches[3].multi_get(keys) == values


async def test_cache_group_multi_set():
    caches = [SimpleMaxTTLMemoryCache(),
              SimpleMemoryCache2(),
              SimpleMemoryCache3(),
              SimpleMemoryCache4()
              ]
    for cache in caches:
        await cache.clear()

    cache_group = CacheGroup(caches)

    keys = [str(i) for i in range(len(caches))]
    values = [str(i) for i in range(len(caches))]
    ttls = [None for i in range(len(caches))]
    triplets = list(zip(keys, values, ttls))
    await cache_group.multi_set(triplets)

    for cache in caches:
        assert await cache.multi_get(keys) == values
        assert await cache_group.multi_get(keys) == values
        await cache.clear()


async def test_cache_group_cache_jsonrpc_response(
        steemd_requests_and_responses):
    caches = [SimpleMaxTTLMemoryCache(),
              SimpleMemoryCache2(),
              SimpleMemoryCache3(),
              SimpleMemoryCache4()
              ]
    for cache in caches:
        await cache.clear()

    cache_group = CacheGroup(caches)
    req, resp = steemd_requests_and_responses
    req = JussiJSONRPCRequest.from_request(req)
    resp['jsonrpc'] = '2.0'
    key = jsonrpc_cache_key(req)

    assert await cache_group.get(key) is None
    await cache_group.cache_jsonrpc_response(req, resp, 15_000_000)

    for cache in caches:
        assert await cache.get(key) == resp, f'key:{key} urn:{req.urn}'
    assert await cache_group.get(key) == resp, f'key:{key} urn:{req.urn}'


async def test_cache_group_get_jsonrpc_response(steemd_requests_and_responses):
    caches = [SimpleMaxTTLMemoryCache(),
              SimpleMemoryCache2(),
              SimpleMemoryCache3(),
              SimpleMemoryCache4()
              ]
    for cache in caches:
        await cache.clear()

    cache_group = CacheGroup(caches)
    req, resp = steemd_requests_and_responses
    req = JussiJSONRPCRequest.from_request(req)
    resp['jsonrpc'] = '2.0'
    key = jsonrpc_cache_key(req)
    assert await cache_group.get(key) is None
    await cache_group.cache_jsonrpc_response(req, resp, 15_000_000)

    assert await cache_group.get(key) == resp
    assert await cache_group.get_jsonrpc_response(req) == resp
    for cache in caches:
        assert await cache.get(key) == resp


async def test_cache_group_get_single_jsonrpc_response(
        steemd_requests_and_responses):
    caches = [SimpleMaxTTLMemoryCache(),
              SimpleMemoryCache2(),
              SimpleMemoryCache3(),
              SimpleMemoryCache4()
              ]
    for cache in caches:
        await cache.clear()

    cache_group = CacheGroup(caches)
    req, resp = steemd_requests_and_responses
    req = JussiJSONRPCRequest.from_request(req)
    resp['jsonrpc'] = '2.0'
    key = jsonrpc_cache_key(req)
    assert await cache_group.get(key) is None
    await cache_group.cache_jsonrpc_response(req, resp, 15_000_000)
    assert await cache_group.get(key) == resp
    assert await cache_group.get_single_jsonrpc_response(req) == resp
    for cache in caches:
        assert await cache.get(key) == resp


async def test_cache_group_get_batch_jsonrpc_responses(
        steemd_requests_and_responses):
    caches = [SimpleMaxTTLMemoryCache(),
              SimpleMemoryCache2(),
              SimpleMemoryCache3(),
              SimpleMemoryCache4()
              ]
    for cache in caches:
        await cache.clear()

    cache_group = CacheGroup(caches)

    req, resp = steemd_requests_and_responses
    req = JussiJSONRPCRequest.from_request(req)
    resp['jsonrpc'] = '2.0'
    batch_req = [req, req, req]
    batch_resp = [resp, resp, resp]
    key = jsonrpc_cache_key(req)
    assert await cache_group.get(key) is None
    await cache_group.cache_jsonrpc_response(batch_req, batch_resp, 15_000_000)
    assert await cache_group.get(key) == resp
    assert await cache_group.get_batch_jsonrpc_responses(
        batch_req) == batch_resp


def test_cache_group_is_complete_response(steemd_requests_and_responses):
    req, resp = steemd_requests_and_responses
    req = JussiJSONRPCRequest.from_request(req)
    assert CacheGroup.is_complete_response(req, resp) is True


@pytest.mark.parametrize('req,resp,expected', [
    (request, response, True),
    (request2, response, True),
    (request, error_response, False),
    ([], [], False),
    (dict(), dict(), False),
    ('', '', False),
    (b'', b'', False),
    (None, None, False),
    (request, [], False),
    (request, [dict()], False),
    (request, dict(), False),
    (request, '', False),
    (request, b'', False),
    (request, None, False),
    ([], response, False),
    ([dict()], response, False),
    (dict(), response, False),
    ('', response, False),
    (b'', response, False),
    (None, response, False),
    ([request, request], [response], False),
    ([request], [response, response], False),
    (request, bad_response1, False),
    (request, bad_response2, False),
    ([request, request], [response, bad_response1], False),
    ([request, request], [response, bad_response2], False),
    ([request, request], [bad_response1], False)
])
def test_cache_group_is_complete_response_bad_responses(req, resp, expected):
    assert CacheGroup.is_complete_response(req, resp) is expected


def test_cache_group_x_jussi_cache_key(steemd_requests_and_responses):
    req, resp = steemd_requests_and_responses
    req = JussiJSONRPCRequest.from_request(req)
    batch_req = [req, req, req]
    assert jsonrpc_cache_key(req) == CacheGroup.x_jussi_cache_key(req)
    assert CacheGroup.x_jussi_cache_key(batch_req) == 'batch'
