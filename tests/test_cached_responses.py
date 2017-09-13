# -*- coding: utf-8 -*-
import aiocache

import pytest
from jussi.cache import cache_get
from jussi.cache import cache_get_batch
from jussi.cache import cacher
from jussi.cache import jsonrpc_cache_key
from jussi.cache import merge_cached_responses

caches_config = {
        'default': {
            'cache':
            'jussi.cache_backends.SimpleLRUMemoryCache'
        }
}


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


@pytest.mark.parametrize('jrpc_req,jrpc_resp', [
    (jrpc_req_1,jrpc_resp_1),
    ({"id":1,"jsonrpc":"2.0","method":"get_block","params":[1000]},jrpc_resp_1),
    ({"id":1,"jsonrpc":"2.0","method":"get_block","params":[1000]},jrpc_resp_1)
])
async def test_cached_response_id_replacement(jrpc_req, jrpc_resp, dummy_request):
    aiocache.caches.set_config(caches_config)
    cache = aiocache.caches.create(alias='default')
    await cache.clear()
    assert await cache.get('steemd.database_api.get_block.params=[1000]') is None
    await cache.set('steemd.database_api.get_block.params=[1000]', jrpc_resp, ttl=None)

    dummy_request.app.config.caches = [cache]
    dummy_request.app.config.last_irreversible_block_num = 10000000

    result = await cache_get(dummy_request, jrpc_req)
    assert result is not None
    assert result['id'] == jrpc_req['id']


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




@pytest.mark.parametrize('jrpc_batch_req,responses, expected', [
    (batch1_jrpc,cached_resp1,cached_resp1),
    (batch1_jrpc,batch2_jrpc,batch2_jrpc),
    (batch1_jrpc[:4],cached_resp2,expected2)
])
def test_merge_cached_responses(jrpc_batch_req,responses, expected):
    assert merge_cached_responses(jrpc_batch_req, responses) == expected


@pytest.mark.parametrize('cached,jrpc_batch_req,expected', [
(batch1_jrpc,batch2_jrpc,batch2_jrpc)
])
def test_cache_get_batch(loop,caches,cached,jrpc_batch_req,expected):
    for cache in caches:
        loop.run_until_complete(cache.clear())

    for item in cached:
        key = jsonrpc_cache_key(item)
        for cache in caches:
            loop.run_until_complete(
                cache.set(key, item, ttl=None))

    results = loop.run_until_complete(cache_get_batch(caches,jrpc_batch_req))
    assert results == expected


def test_skip_cacher(loop):
    # pylint: disable=unused-argument, unexpected-keyword-arg
    @cacher
    async def func(sanic_http_request, jsonrpc_request):
        return 1

    result = loop.run_until_complete(func({},{},
                                          skip_cacher_get=True,
                                          skip_cacher_set=True))
    assert result == 1
