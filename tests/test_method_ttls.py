# -*- coding: utf-8 -*-
import pytest
from jussi.cache import block_num_from_jsonrpc_response
from jussi.cache import irreversible_ttl
from jussi.cache import ttl_from_jsonrpc_request
from jussi.cache import ttl_from_urn
from jussi.jsonrpc_method_cache_settings import TTL

SBDS_DEFAULT_CACHE = 10


ttl_rpc_req = {"id":"1","jsonrpc":"2.0","method":"get_block","params":[1000]}
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
        "transaction_ids": []
    }
}

non_ttl_rpc_req = {"id":"1","jsonrpc":"2.0","method":"sbds.get_block","params":[1000]}

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
def test_ttls(rpc_req, rpc_resp, last_block_num,expected):
    ttl = ttl_from_jsonrpc_request(rpc_req, last_block_num, rpc_resp)
    assert ttl == expected

@pytest.mark.parametrize('response, last_block,expected', [
    (rpc_resp, 0, TTL.NO_CACHE),
    (rpc_resp, 999, TTL.NO_CACHE),
    (rpc_resp, 1000, TTL.NO_EXPIRE),
    (rpc_resp, 1001, TTL.NO_EXPIRE),
])
def test_irreversible_ttl(response, last_block, expected):
    ttl = irreversible_ttl(response, last_block)
    assert ttl == expected

@pytest.mark.parametrize('urn,expected', [
    ('steemd.database_api.get_account_count', TTL.DEFAULT_TTL),
    ('steemd.database_api.get_block.params=[1000]', TTL.NO_EXPIRE_IF_IRREVERSIBLE),
    ('steemd.database_api.get_block_header.params=[1000]', TTL.NO_EXPIRE_IF_IRREVERSIBLE),
])
def test_ttl_from_urn(urn, expected):
    ttl = ttl_from_urn(urn)
    assert ttl == expected


@pytest.mark.parametrize('response,expected', [
    (rpc_resp,1000)
])
def test_block_num_from_jsonrpc_response(response, expected):
    num = block_num_from_jsonrpc_response(response)
    assert num == expected
