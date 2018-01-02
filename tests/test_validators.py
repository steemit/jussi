# -*- coding: utf-8 -*-

import pytest

from jussi.request import JussiJSONRPCRequest
from jussi.validators import is_get_block_header_request
from jussi.validators import is_get_block_request
from jussi.validators import is_valid_get_block_response
from jussi.validators import is_valid_jsonrpc_response
from jussi.validators import is_valid_jussi_response
from jussi.validators import is_valid_non_error_jsonrpc_response
from jussi.validators import is_valid_non_error_single_jsonrpc_response
from jussi.validators import is_valid_single_jsonrpc_response
from jussi.validators import validate_response_decorator

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

bh_request1 = JussiJSONRPCRequest.from_request({
    "id": "1", "jsonrpc": "2.0",
    "method": "get_block_header", "params": [1000]
})
bh_request2 = JussiJSONRPCRequest.from_request({
    "id": "1", "jsonrpc": "2.0", "method": "call",
    "params": ["database_api", "get_block_header", [1000]]
})

batch_request = [request, request2]
batch_response = [response, response]

error_response = {"id": "1", "jsonrpc": "2.0", "error": {}}


@pytest.mark.parametrize('value,expected', [
    (request, True),
    (response, False),
    (request2, True),
    ([], False),
    (dict(), False),
    ('', False),
    (b'', False),
    (None, False)
])
def test_is_get_block_request(value, expected):
    assert is_get_block_request(value) is expected


@pytest.mark.parametrize('req,expected', [
    (request, False),
    (request, False),
    (request2, False),
    (bh_request1, True),
    (bh_request2, True),
    ([], False),
    (dict(), False),
    ('', False),
    (b'', False),
    (None, False)
])
def test_is_get_block_header_request(req, expected):
    assert is_get_block_header_request(req) is expected


@pytest.mark.parametrize('req,response,expected', [
    (request, error_response, False),
    (request, response, True),
    (request2, response, True),
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

])
def test_is_valid_get_block_response(req, response, expected):
    assert is_valid_get_block_response(req, response) is expected


@pytest.mark.parametrize('req,resp,expected', [
    (request, response, True),
    (request2, response, True),
    (request, error_response, True),

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
])
def test_is_valid_jsonrpc_response(req, resp, expected):
    assert is_valid_jsonrpc_response(req, resp) is expected


def test_is_valid_jsonrpc_response_using_steemd(steemd_requests_and_responses):
    req, resp = steemd_requests_and_responses
    req = JussiJSONRPCRequest.from_request(req)
    assert is_valid_jsonrpc_response(req, resp) is True


@pytest.mark.parametrize('value,expected', [
    (response, True),
    (error_response, True),

    (request, False),

    (batch_request, False),
    (batch_response, False),

    ([], False),
    ([dict()], False),
    (dict(), False),
    ('', False),
    (b'', False),
    (None, False)
])
def test_is_valid_single_jsonrpc_response(value, expected):
    assert is_valid_single_jsonrpc_response(value) is expected


def test_is_valid_single_jsonrpc_response_using_steemd(
        steemd_requests_and_responses):
    req, resp = steemd_requests_and_responses
    req = JussiJSONRPCRequest.from_request(req)
    assert is_valid_single_jsonrpc_response(resp) is True


@pytest.mark.parametrize('value,expected', [
    (request, False),
    (response, True),
    (batch_request, False),
    (batch_response, False),
    (error_response, False),
    ([], False),
    ([dict()], False),
    (dict(), False),
    ('', False),
    (b'', False),
    (None, False)
])
def test_is_valid_non_error_single_jsonrpc_response(value, expected):
    assert is_valid_non_error_single_jsonrpc_response(value) is expected


def test_is_valid_non_error_single_jsonrpc_response_using_steemd(
        steemd_requests_and_responses):
    req, resp = steemd_requests_and_responses
    req = JussiJSONRPCRequest.from_request(req)
    assert is_valid_non_error_single_jsonrpc_response(resp) is True


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
])
def test_is_valid_non_error_jsonrpc_response(req, resp, expected):
    assert is_valid_non_error_jsonrpc_response(req, resp) is expected


def test_is_valid_non_error_jsonrpc_response_using_steemd(
        steemd_requests_and_responses):
    req, resp = steemd_requests_and_responses
    req = JussiJSONRPCRequest.from_request(req)
    assert is_valid_non_error_jsonrpc_response(req, resp) is True


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
def test_is_valid_jussi_response(req, resp, expected):
    assert is_valid_jussi_response(req, resp) is expected


def test_is_valid_jussi_response_using_steemd(steemd_requests_and_responses):
    req, resp = steemd_requests_and_responses
    req = JussiJSONRPCRequest.from_request(req)
    assert is_valid_jussi_response(req, resp) is True


async def test_validate_response_valid():
    req = {
        "id": "1", "jsonrpc": "2.0",
        "method": "get_block", "params": [1000]
    }

    @validate_response_decorator
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
                "transaction_ids": []}}

    response = await test_func(None, req)
    assert response == response
