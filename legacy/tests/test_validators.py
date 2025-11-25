# -*- coding: utf-8 -*-

import pytest
from .conftest import TEST_UPSTREAM_CONFIG
from jussi.errors import JsonRpcError
from jussi.errors import JussiLimitsError
from jussi.errors import JussiCustomJsonOpLengthError
from jussi.errors import InvalidRequest
from jussi.request.jsonrpc import JSONRPCRequest
from jussi.request.jsonrpc import from_http_request as jsonrpc_from_request
from jussi.validators import is_get_block_header_request
from jussi.validators import is_get_block_request
from jussi.validators import is_valid_get_block_response
from jussi.validators import is_valid_non_error_jussi_response
from jussi.validators import is_valid_non_error_single_jsonrpc_response
from jussi.validators import is_valid_single_jsonrpc_response
from jussi.validators import limit_broadcast_transaction_request
from jussi.validators import limit_custom_json_op_length
from jussi.validators import limit_custom_json_account
from jussi.validators import is_broadcast_transaction_request
from jussi.validators import validate_jsonrpc_request

from .conftest import make_request
dummy_request = make_request()


request = jsonrpc_from_request(dummy_request, 0, {
    "id": "1", "jsonrpc": "2.0",
    "method": "get_block", "params": [1000]
})

request2 = jsonrpc_from_request(dummy_request, 1, {
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

bh_request1 = jsonrpc_from_request(dummy_request, 0, {
    "id": "1", "jsonrpc": "2.0",
    "method": "get_block_header", "params": [1000]
})
bh_request2 = jsonrpc_from_request(dummy_request, 0, {
    "id": "1", "jsonrpc": "2.0", "method": "call",
    "params": ["database_api", "get_block_header", [1000]]
})

batch_request = [request, request2]
batch_response = [response, response]

error_response = {"id": "1", "jsonrpc": "2.0", "error": {}}


def test_vaildate_jsonrpc_request_invalid(invalid_jrpc_single_and_batch_request):
    request = invalid_jrpc_single_and_batch_request
    with pytest.raises((AssertionError, InvalidRequest, KeyError, AttributeError)):
        validate_jsonrpc_request(request)


def test_vaildate_jsonrpc_requests(batch_combined_request):
    request = batch_combined_request
    assert validate_jsonrpc_request(request) is None


@pytest.mark.parametrize('req,expected', [
    (request, True),
    (request2, True),
    (dict(jsonrpc='2.0', method='m'), False)
])
def test_is_get_block_request(req, expected):
    if not isinstance(req, JSONRPCRequest):
        req = jsonrpc_from_request(dummy_request, 0, req)
    assert is_get_block_request(req) is expected


@pytest.mark.parametrize('req,expected', [
    (request, False),
    (request, False),
    (request2, False),
    (bh_request1, True),
    (bh_request2, True),
    (dict(jsonrpc='2.0', method='m'), False),
    (dict(jsonrpc='2.0', method='m'), False),
    (dict(jsonrpc='2.0', method='m'), False),
    (dict(jsonrpc='2.0', method='m'), False),
    (dict(jsonrpc='2.0', method='m'), False)
])
def test_is_get_block_header_request(req, expected):
    if not isinstance(req, JSONRPCRequest):
        req = jsonrpc_from_request(dummy_request, 0, req)
    assert is_get_block_header_request(req) is expected


@pytest.mark.parametrize('req,response,expected', [
    (request, response, True),
    (request2, response, True),
    (request, error_response, False),
    (dict(jsonrpc='2.0', method='m'), [], False),
    (dict(jsonrpc='2.0', method='m'), dict(), False),
    (dict(jsonrpc='2.0', method='m'), '', False),
    (dict(jsonrpc='2.0', method='m'), b'', False),
    (dict(jsonrpc='2.0', method='m'), None, False),
    (request, [], False),
    (request, [dict()], False),
    (request, dict(), False),
    (request, '', False),
    (request, b'', False),
    (request, None, False),
    (dict(jsonrpc='2.0', method='m'), response, False),


])
def test_is_valid_get_block_response(req, response, expected):
    if not isinstance(req, JSONRPCRequest):
        req = jsonrpc_from_request(dummy_request, 0, req)
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
def is_valid_jsonrpc_response(req, resp, expected):
    # if not isinstance(req, JSONRPCRequest):
    #    req = jsonrpc_from_request(dummy_request,0,req)
    pass
    #assert is_valid_jsonrpc_response(req, resp) is expected


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
        steemd_request_and_response):
    req, resp = steemd_request_and_response
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
        steemd_request_and_response):
    req, resp = steemd_request_and_response
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
    (request, bad_response1, False),
    (request, bad_response2, False),
    ([request, request], [response, bad_response1], False),
    ([request, request], [response, bad_response2], False),
    ([request, request], [bad_response1], False)
])
def test_is_valid_jussi_response(req, resp, expected):
    # if not isinstance(req, JSONRPCRequest):
    #    req = jsonrpc_from_request(dummy_request,0,req)
    assert is_valid_non_error_jussi_response(req, resp) is expected


def test_is_valid_jussi_response_using_steemd(steemd_request_and_response):
    req, resp = steemd_request_and_response
    req = jsonrpc_from_request(dummy_request, 0, req)
    assert is_valid_non_error_jussi_response(req, resp) is True


@pytest.mark.parametrize('ops, expected', [
    ([[
        'custom_json',
        {
            "required_auths": [],
            "id": "follow",
            "json": "{\"follower\":\"steemit\",\"following\":\"steem\",\"what\":[\"posts\"]}",
            "required_posting_auths": ["steemit"]
        }
    ]], True),
    ([[
        'custom_json',
        {
            "required_auths": [],
            "id": "follow",
            "json": "a"*8192,
            "required_posting_auths": ["steemit"]
        }
    ]], False),
    ([[
        'custom_json',
        {
            "required_auths": [],
            "id": "follow",
            "json": "😂"*2048,
            "required_posting_auths": ["steemit"]
        }
    ]], False),
])
def test_is_valid_custom_json_op_length(ops, expected):
    if expected is False:
        with pytest.raises(JussiCustomJsonOpLengthError):
            limit_custom_json_op_length(ops, size_limit=8191)
    else:
        limit_custom_json_op_length(ops, size_limit=100)


@pytest.mark.parametrize('ops, expected', [
    ([[
        'custom_json',
        {
            "required_auths": [],
            "id": "follow",
            "json": "{\"follower\":\"steemit\",\"following\":\"steem\",\"what\":[\"posts\"]}",
            "required_posting_auths": ["steemit"]
        }
    ]], True),
    ([[
        'custom_json',
        {
            "required_auths": [],
            "id": "follow",
            "json": "{\"follower\":\"steemit\",\"following\":\"steem\",\"what\":[\"posts\"]}",
            "required_posting_auths": ["not_steemit"]
        }
    ]], False),
])
def test_limit_custom_json_account(ops, expected):
    if expected is False:
        with pytest.raises(JussiLimitsError):
            limit_custom_json_account(ops, blacklist_accounts={'not_steemit'})
    else:
        limit_custom_json_account(ops, blacklist_accounts={'not_steemit'})


def test_is_broadcast_transaction_false(steemd_request_and_response):
    req, resp = steemd_request_and_response
    req = jsonrpc_from_request(dummy_request, 0,
                               req)
    assert is_broadcast_transaction_request(req) is False


def test_is_broadcast_transaction_true(valid_broadcast_transaction):
    req = jsonrpc_from_request(dummy_request, 0,
                               valid_broadcast_transaction)
    assert is_broadcast_transaction_request(req) is True


def test_is_broadcast_transaction_true_invalid(invalid_broadcast_transaction):
    req = jsonrpc_from_request(dummy_request, 0,
                               invalid_broadcast_transaction)
    assert is_broadcast_transaction_request(req) is True


def test_limit_broadcast_transaction_request(steemd_request_and_response):
    req, resp = steemd_request_and_response
    req = jsonrpc_from_request(dummy_request, 0, req)
    limit_broadcast_transaction_request(req)


def test_valid_limit_broadcast_transaction_request(valid_broadcast_transaction):
    req = jsonrpc_from_request(dummy_request, 0, valid_broadcast_transaction)
    limit_broadcast_transaction_request(
        req, limits=TEST_UPSTREAM_CONFIG['limits'])


def test_invalid_limit_broadcast_transaction_request(invalid_broadcast_transaction):
    req = jsonrpc_from_request(dummy_request, 0, invalid_broadcast_transaction)
    with pytest.raises(JsonRpcError):
        limit_broadcast_transaction_request(
            req, limits=TEST_UPSTREAM_CONFIG['limits'])
