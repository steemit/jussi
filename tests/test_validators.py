# -*- coding: utf-8 -*-
import aiocache

import pytest
from jussi.errors import ServerError
from jussi.validators import block_num_from_jsonrpc_request
from jussi.validators import block_num_from_jsonrpc_response
from jussi.validators import is_get_block_header_request
from jussi.validators import is_get_block_request
from jussi.validators import is_jsonrpc_error_response
from jussi.validators import is_valid_get_block_response
from jussi.validators import is_valid_jsonrpc_response
from jussi.validators import is_valid_non_error_jsonrpc_response
from jussi.validators import is_valid_non_error_single_jsonrpc_response
from jussi.validators import is_valid_single_jsonrpc_response
from jussi.validators import validate_response

request = {"id":"1","jsonrpc":"2.0","method":"get_block","params":[1000]}
request2 = {"id":"1","jsonrpc":"2.0","method":"call","params":["database_api","get_block",[1000]]}
response = {
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


bh_request1 = {"id":"1","jsonrpc":"2.0","method":"get_block_header","params":[1000]}
bh_request2 = {"id":"1","jsonrpc":"2.0","method":"call","params":["database_api","get_block_header",[1000]]}

batch_request = [request, request2]
batch_response = [response, response]

error_response = {"id":"1","jsonrpc":"2.0","error": {}}

@pytest.mark.parametrize('value,expected',[
    (request, True),
    (response, False),
    (request2, True)
])
def test_is_get_block_request(value, expected):
    assert is_get_block_request(value) is expected


@pytest.mark.parametrize('req,expected',[
    (request, False),
    (request, False),
    (request2, False),
    (bh_request1, True),
    (bh_request2, True),
])
def test_is_get_block_header_request(req,expected):
    assert is_get_block_header_request(req) is expected


@pytest.mark.parametrize('req,response,expected',[
    (request, error_response, False),
    (request, response, True),
    (request2, response, True),
])
def test_is_valid_get_block_response(req,response,expected):
    assert is_valid_get_block_response(req, response) is expected


@pytest.mark.parametrize('value,expected',[
    (request, False),
    (response, True),
    (batch_response, True),
    (error_response, True)
])
def test_is_valid_jsonrpc_response(value, expected):
    assert is_valid_jsonrpc_response(value) is expected

@pytest.mark.parametrize('value,expected',[
    (request, False),
    (response, True),
    (batch_request, False),
    (batch_response, False),
    (error_response, True)
])
def test_is_valid_single_jsonrpc_response(value, expected):
    assert is_valid_single_jsonrpc_response(value) is expected

@pytest.mark.parametrize('value,expected',[
    (request, False),
    (response, True),
    (batch_request, False),
    (batch_response, False),
    (error_response, False)
])
def test_is_valid_non_error_single_jsonrpc_response(value, expected):
    assert is_valid_non_error_single_jsonrpc_response(value) is expected


@pytest.mark.parametrize('value,expected',[
    (request, False),
    (response, False),
    (batch_request, False),
    (batch_response, False),
    (error_response, True)
])
def test_is_jsonrpc_error_response(value, expected):
    assert is_jsonrpc_error_response(value) is expected


@pytest.mark.parametrize('value,expected',[
    (request, False),
    (response, True),
    (batch_request, False),
    (batch_response, True),
    (error_response, False)
])
def test_is_valid_non_error_jsonrpc_response(value, expected):
    assert is_valid_non_error_jsonrpc_response(value) is expected


@pytest.mark.parametrize('value,expected',[
    (response, 1000),
])
def test_block_num_from_jsonrpc_response(value, expected):
    assert block_num_from_jsonrpc_response(value) == expected


@pytest.mark.parametrize('value,expected',[
    (request, 1000),
    (request2, 1000)
])
def test_block_num_from_jsonrpc_request(value, expected):
    assert block_num_from_jsonrpc_request(value) == expected



async def test_validate_response_invalid(invalid_jrpc_responses):
    @validate_response
    async def test_func(sanic_http_request, jsonrpc_request, json_response):
        return json_response

    with pytest.raises(ServerError):
        await test_func(None, invalid_jrpc_responses, invalid_jrpc_responses)



async def test_validate_response_valid():
    req = {"id":"1","jsonrpc":"2.0","method":"get_block","params":[1000]}
    @validate_response
    async def test_func(sanic_http_request, jsonrpc_request):
        return {
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

    response = await test_func(None, req)
    assert response == response
