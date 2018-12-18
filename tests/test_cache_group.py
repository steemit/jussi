# -*- coding: utf-8 -*-
import pytest
from time import perf_counter

from jussi.cache.backends.max_ttl import SimplerMaxTTLMemoryCache
from jussi.cache import CacheGroupItem
from jussi.cache import SpeedTier
from jussi.cache.cache_group import CacheGroup
from jussi.cache.utils import jsonrpc_cache_key


from .conftest import make_request
from .conftest import build_mocked_cache
from jussi.request.jsonrpc import from_http_request as jsonrpc_from_request
dummy_request = make_request()


jrpc_req_1 = jsonrpc_from_request(dummy_request, 0, {
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

batch1_jrpc = [jsonrpc_from_request(dummy_request, _id, {
    "id": _id, "jsonrpc": "2.0",
    "method": "get_block", "params": [1000]
}) for _id in range(10)]
batch2_jrpc = [jsonrpc_from_request(dummy_request, _id, {
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

request = jsonrpc_from_request(dummy_request, 0, {
    "id": "1", "jsonrpc": "2.0",
    "method": "get_block", "params": [1000]
})
request2 = jsonrpc_from_request(dummy_request, 0, {
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
    caches = [
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST),
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST),
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST)
    ]
    cache_group = CacheGroup(caches)

    for cache_item in caches:
        await cache_item.cache.set('key', 'value', 180)

    await cache_group.clear()

    for cache_item in caches:
        assert await cache_item.cache.get('key') is None
    assert await cache_group.get('key') is None


async def test_cache_group_get():
    caches = [
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST),
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST),
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST)
    ]
    cache_group = CacheGroup(caches)
    assert caches[0] is not caches[1]

    await cache_group._read_caches[0].set('key', 0, 180)
    assert await cache_group._read_caches[0].get('key') == 0

    await cache_group._read_caches[1].set('key', 1, 180)
    assert await cache_group._read_caches[0].get('key') == 0
    assert await cache_group._read_caches[1].get('key') == 1

    await cache_group._read_caches[2].set('key', 2, 180)
    assert await cache_group._read_caches[0].get('key') == 0
    assert await cache_group._read_caches[1].get('key') == 1
    assert await cache_group._read_caches[2].get('key') == 2

    assert await cache_group.get('key') == 0
    await cache_group._read_caches[0].delete('key')

    assert await cache_group.get('key') == 1
    await cache_group._read_caches[1].delete('key')
    assert await cache_group.get('key') == 2
    await cache_group._read_caches[2].delete('key')

    assert await cache_group.get('key') is None


async def test_cache_group_set():
    caches = [
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST),
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST),
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST)
    ]
    cache_group = CacheGroup(caches)

    await cache_group.set('key', 1, 180)
    for i, cache_item in enumerate(caches):
        assert await cache_item.cache.get('key') == 1


async def test_cache_group_mget():
    caches = [
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST),
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST),
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST)
    ]
    cache_group = CacheGroup(caches)

    keys = [str(i) for i in range(len(caches))]
    values = [str(i) for i in range(len(caches))]
    pairs = {k: v for k, v in zip(keys, values)}
    await cache_group.set_many(pairs, 180)

    assert await cache_group.mget(keys) == values
    assert await caches[0].cache.mget(keys) == values
    assert await caches[1].cache.mget(keys) == values
    assert await caches[2].cache.mget(keys) == values

    await cache_group._read_caches[0].clear()
    assert await cache_group.mget(keys) == values
    assert await caches[0].cache.mget(keys) == [None for key in keys]
    assert await cache_group._read_caches[1].mget(keys) == values
    assert await cache_group._read_caches[2].mget(keys) == values

    await cache_group._read_caches[1].clear()
    assert await cache_group.mget(keys) == values
    assert await caches[0].cache.mget(keys) == [None for key in keys]
    assert await caches[1].cache.mget(keys) == [None for key in keys]
    assert await cache_group._read_caches[2].mget(keys) == values

    await cache_group._read_caches[2].clear()
    assert await cache_group.mget(keys) == values
    assert await caches[0].cache.mget(keys) == [None for key in keys]
    assert await caches[1].cache.mget(keys) == [None for key in keys]
    assert await caches[2].cache.mget(keys) == [None for key in keys]

    await cache_group.clear()
    assert await caches[0].cache.mget(keys) == [None for key in keys]
    assert await caches[1].cache.mget(keys) == [None for key in keys]
    assert await caches[2].cache.mget(keys) == [None for key in keys]
    assert await cache_group.mget(keys) == [None for key in keys]


async def test_cache_group_set_many():
    caches = [
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST),
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST),
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST)
    ]
    cache_group = CacheGroup(caches)

    keys = [str(i) for i in range(len(caches))]
    values = [str(i) for i in range(len(caches))]
    ttls = [None for i in range(len(caches))]
    pairs = {k: v for k, v in zip(keys, values)}
    await cache_group.set_many(pairs, 180)

    for cache_item in caches:
        assert await cache_item.cache.mget(keys) == values
        assert await cache_group.mget(keys) == values
        await cache_item.cache.clear()


async def test_cache_group_get_single_jsonrpc_response(
        steemd_request_and_response):
    caches = [
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST),
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST),
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST)
    ]
    cache_group = CacheGroup(caches)

    cache_group = CacheGroup(caches)
    req, resp = steemd_request_and_response
    req = jsonrpc_from_request(dummy_request, 0, req)
    resp['jsonrpc'] = '2.0'
    key = jsonrpc_cache_key(req)
    assert await cache_group.get(key) is None
    await cache_group.set('last_irreversible_block_num', 15_000_000, 180)
    await cache_group.cache_single_jsonrpc_response(req, resp)
    assert await cache_group.get(key) == resp
    assert await cache_group.get_single_jsonrpc_response(req) == resp
    cache_group._memory_cache.clears()
    assert await cache_group.get_single_jsonrpc_response(req) == resp

    for cache_item in caches:
        assert await cache_item.cache.get(key) == resp


async def test_cache_group_get_batch_jsonrpc_responses():
    batch_req = [jsonrpc_from_request(dummy_request, _id, {
        "id": _id, "jsonrpc": "2.0", "method": "get_block",
        "params": [_id]
    }) for _id in range(1, 10)]

    batch_resp = [{
        'id': _id, "jsonrpc": "2.0", 'result': {
            "previous": "000003e7c4fd3221cf407efcf7c1730e2ca54b05",
            "timestamp": "2016-03-24T16:55:30",
            "witness": "initminer",
            "transaction_merkle_root": "0000000000000000000000000000000000000000",
            "extensions": [],
            "witness_signature": "207f15578cac20ac0e8af1ebb8f463106b8849577e21cca9fc60da146d1d95df88072dedc6ffb7f7f44a9185bbf9bf8139a5b4285c9f423843720296a44d428856",
            "transactions": [],
            "block_id": "000003e8b922f4906a45af8e99d86b3511acd7a5",
            "signing_key": "STM8GC13uCZbP44HzMLV6zPZGwVQ8Nt4Kji8PapsPiNq1BK153XTX",
            "transaction_ids": []
        }
    } for _id in range(1, 10)]
    caches = [
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST),
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST),
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST)
    ]
    cache_group = CacheGroup(caches)
    await cache_group.set('last_irreversible_block_num', 15_000_000, 180)
    await cache_group.cache_batch_jsonrpc_response(batch_req, batch_resp)

    test_responses = await cache_group.get_batch_jsonrpc_responses(batch_req)
    assert test_responses == batch_resp

    cache_group._memory_cache.clears()
    test_responses = await cache_group.get_batch_jsonrpc_responses(batch_req)
    assert test_responses == batch_resp


async def test_cache_group_cache_batch_jsonrpc_responses():
    batch_req = [jsonrpc_from_request(dummy_request, _id, {
        "id": _id, "jsonrpc": "2.0", "method": "get_block",
        "params": [_id]
    }) for _id in range(1, 10)]

    batch_resp = [{'id': _id, "jsonrpc": "2.0", 'result': {
        "previous": "000003e7c4fd3221cf407efcf7c1730e2ca54b05",
        "timestamp": "2016-03-24T16:55:30",
        "witness": "initminer",
        "transaction_merkle_root": "0000000000000000000000000000000000000000",
        "extensions": [],
        "witness_signature": "207f15578cac20ac0e8af1ebb8f463106b8849577e21cca9fc60da146d1d95df88072dedc6ffb7f7f44a9185bbf9bf8139a5b4285c9f423843720296a44d428856",
        "transactions": [],
        "block_id": "000003e8b922f4906a45af8e99d86b3511acd7a5",
        "signing_key": "STM8GC13uCZbP44HzMLV6zPZGwVQ8Nt4Kji8PapsPiNq1BK153XTX",
        "transaction_ids": []}} for _id in range(1, 10)]

    caches = [
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST),
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST),
        CacheGroupItem(build_mocked_cache(), True, True, SpeedTier.FAST)
    ]
    cache_group = CacheGroup(caches)

    keys = [jsonrpc_cache_key(req) for req in batch_req]
    await cache_group.set('last_irreversible_block_num', 15_000_000, 180)
    await cache_group.cache_batch_jsonrpc_response(batch_req, batch_resp)

    for i, key in enumerate(keys):
        assert cache_group._memory_cache.gets(key) == batch_resp[i]
        assert await caches[0].cache.get(key) == batch_resp[i]
        assert await caches[1].cache.get(key) == batch_resp[i]
        assert await caches[2].cache.get(key) == batch_resp[i]
        assert await cache_group.get(key) == batch_resp[i]


def test_cache_group_is_complete_response(steemd_request_and_response):
    req, resp = steemd_request_and_response
    req = jsonrpc_from_request(dummy_request, 0, req)
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


def test_cache_group_x_jussi_cache_key(steemd_request_and_response):
    req, resp = steemd_request_and_response
    req = jsonrpc_from_request(dummy_request, 0, req)
    batch_req = [req, req, req]
    assert jsonrpc_cache_key(req) == CacheGroup.x_jussi_cache_key(req)
    assert CacheGroup.x_jussi_cache_key(batch_req) == 'batch'
