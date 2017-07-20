# -*- coding: utf-8 -*-
import aiocache

import pytest
from jussi.cache import cache_get
from jussi.serializers import CompressionSerializer

caches_config = {
        'default': {
            'cache':aiocache.SimpleMemoryCache,
            'serializer': {
                'class': CompressionSerializer
            }
        }
}


jrpc_req = {"id":"1","jsonrpc":"2.0","method":"get_block","params":[1000]}
jrpc_resp = {
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
    (jrpc_req,jrpc_resp),
    ({"id":1,"jsonrpc":"2.0","method":"get_block","params":[1000]},jrpc_resp),
    ({"id":1,"jsonrpc":"2.0","method":"get_block","params":[1000]},jrpc_resp),
    ({"jsonrpc":"2.0","method":"get_block","params":[1000]},jrpc_resp),
])
async def test_cached_response(jrpc_req, jrpc_resp, dummy_request):

    aiocache.caches.set_config(caches_config)
    cache = aiocache.caches.get('default')
    await cache.set('steemd.database_api.get_block.params=[1000]',jrpc_resp)
    dummy_request.app.config.caches = [cache]
    dummy_request.json = jrpc_req
    result = await cache_get(dummy_request)
    if 'id' in jrpc_req:
        assert result['id'] == jrpc_req['id']
    else:
        assert 'id' not in result
