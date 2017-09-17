# -*- coding: utf-8 -*-
import pytest
from jussi.cache.backends import SimpleMaxTTLMemoryCache
from jussi.cache.cache_group import CacheGroup
from jussi.cache.utils import jsonrpc_cache_key

from .extra_caches import SimpleMemoryCache2
from .extra_caches import SimpleMemoryCache3
from .extra_caches import SimpleMemoryCache4

jrpc_req_1 = {"id":"1","jsonrpc":"2.0","method":"get_block","params":[1000]}
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
        "transaction_ids": []
    }
}


batch1_jrpc = [{"id":_id,"jsonrpc":"2.0","method":"get_block","params":[1000]} for _id in range(10)]
batch2_jrpc = [{"id":_id,"jsonrpc":"2.0","method":"get_block","params":[1000]} for _id in range(20,30)]

cached_resp1 = [None for i in batch1_jrpc]
cached_resp2 = [None,
                {"id":99,"jsonrpc":"2.0","method":"get_block","params":[1000]},
                None,
                {"id":98,"jsonrpc":"2.0","method":"get_block","params":[1000]}]
expected2 = [None,
             {"id": 1, "jsonrpc": "2.0", "method": "get_block", "params": [1000]},
             None,
             {"id": 3, "jsonrpc": "2.0", "method": "get_block", "params": [1000]},
]

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
        await cache.set('key','value')
    await cache_group.clear()

    assert await cache_group.get('key') == None




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

    await cache_group._caches[0].set('key',0)
    assert await cache_group._caches[0].get('key') == 0

    await cache_group._caches[1].set('key',1)
    assert await cache_group._caches[0].get('key') == 0
    assert await cache_group._caches[1].get('key') == 1

    await cache_group._caches[2].set('key',2)
    assert await cache_group._caches[0].get('key') == 0
    assert await cache_group._caches[1].get('key') == 1
    assert await cache_group._caches[2].get('key') == 2

    await cache_group._caches[3].set('key',3)
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

    await cache_group.set('key',1)
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
    await cache_group.multi_set(zip(keys, values,[None for key in keys]))

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




async def test_cache_group_cache_jsonrpc_response(steemd_requests_and_responses):
    caches = [SimpleMaxTTLMemoryCache(),
              SimpleMemoryCache2(),
              SimpleMemoryCache3(),
              SimpleMemoryCache4()
              ]
    for cache in caches:
        await cache.clear()

    cache_group = CacheGroup(caches)
    req, resp = steemd_requests_and_responses
    key = jsonrpc_cache_key(req)
    assert await cache_group.get(key) == None
    await cache_group.cache_jsonrpc_response(req, resp)
    for cache in caches:
        assert await cache.get(key) == resp
    assert await cache_group.get(key) == resp

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
    key = jsonrpc_cache_key(req)
    assert await cache_group.get(key) == None
    await cache_group.cache_jsonrpc_response(req, resp)
    assert await cache_group.get(key) == resp
    assert await cache_group.get_jsonrpc_response(req) == resp
    for cache in caches:
        assert await cache.get(key) == resp

async def test_cache_group_get_single_jsonrpc_response(steemd_requests_and_responses):
    caches = [SimpleMaxTTLMemoryCache(),
              SimpleMemoryCache2(),
              SimpleMemoryCache3(),
              SimpleMemoryCache4()
              ]
    for cache in caches:
        await cache.clear()

    cache_group = CacheGroup(caches)
    req, resp = steemd_requests_and_responses
    key = jsonrpc_cache_key(req)
    assert await cache_group.get(key) == None
    await cache_group.cache_jsonrpc_response(req, resp)
    assert await cache_group.get(key) == resp
    assert await cache_group.get_single_jsonrpc_response(req) == resp
    for cache in caches:
        assert await cache.get(key) == resp

async def test_cache_group_get_batch_jsonrpc_responses(steemd_requests_and_responses):
    caches = [SimpleMaxTTLMemoryCache(),
              SimpleMemoryCache2(),
              SimpleMemoryCache3(),
              SimpleMemoryCache4()
              ]
    for cache in caches:
        await cache.clear()

    cache_group = CacheGroup(caches)
    req, resp = steemd_requests_and_responses
    batch_req = [req,req,req]
    batch_resp = [resp,resp,resp]
    key = jsonrpc_cache_key(req)
    assert await cache_group.get(key) == None

    await cache_group.cache_jsonrpc_response(batch_req, batch_resp)
    assert await cache_group.get(key) == resp
    assert await cache_group.get_batch_jsonrpc_responses(batch_req) == batch_resp


async def test_cache_group_is_complete_response(steemd_requests_and_responses):
    cache_group = CacheGroup([])
    req, resp = steemd_requests_and_responses
    batch_req = [req, req, req]
    batch_resp = [resp, resp, resp]
    assert cache_group.is_complete_response(batch_req, batch_resp) is True
    assert cache_group.is_complete_response(batch_req, [resp,resp,None]) is False
    assert cache_group.is_complete_response(batch_req, [None, None, None]) is False
    assert cache_group.is_complete_response(batch_req, [resp, resp, None]) is False

async def test_cache_group_x_jussi_cache_key(steemd_requests_and_responses):
    cache_group = CacheGroup([])
    req, resp = steemd_requests_and_responses
    batch_req = [req, req, req]
    assert jsonrpc_cache_key(req) == cache_group.x_jussi_cache_key(req)
    assert cache_group.x_jussi_cache_key(batch_req) == 'batch'
