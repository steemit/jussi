# -*- coding: utf-8 -*-

import json

import pytest

correct_get_block_1000_response = {
    "id": 1,
    "result":
    {"previous": "000003e7c4fd3221cf407efcf7c1730e2ca54b05",
     "timestamp": "2016-03-24T16:55:30", "witness": "initminer",
     "transaction_merkle_root": "0000000000000000000000000000000000000000",
     "extensions": [],
     "witness_signature":
     "207f15578cac20ac0e8af1ebb8f463106b8849577e21cca9fc60da146d1d95df88072dedc6ffb7f7f44a9185bbf9bf8139a5b4285c9f423843720296a44d428856",
     "transactions": [],
     "block_id": "000003e8b922f4906a45af8e99d86b3511acd7a5",
     "signing_key": "STM8GC13uCZbP44HzMLV6zPZGwVQ8Nt4Kji8PapsPiNq1BK153XTX",
     "transaction_ids": []}}

test_request = {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'steemd.fake_method'
}

error_response1 = {'id': 1, 'jsonrpc': '2.0', 'error': {
    'code': -32603, 'message': 'Internal Error', 'data': {'error_id': '123'}}}

error_response2 = {'id': 1, 'jsonrpc': '2.0', 'error': {
    'code': -32603, 'message': 'Internal Error', 'data': {'error_id': '123'}}}

error_response3 = {
    'id': 1,
    'jsonrpc': '2.0',
    'error': {'code': -32603, 'message': 'Internal Error'}
}

error_response4 = {
    'id': 1,
    'jsonrpc': '2.0',
    'error': {'code': -32603, 'message': 'Internal Error'}
}


@pytest.mark.parametrize('jsonrpc_request, expected', [
    (test_request, error_response1),
    (test_request, error_response2),
    (test_request, error_response3),
    (test_request, error_response4),
    (test_request, correct_get_block_1000_response)
])
async def test_upstream_error_responses(mocker, mocked_app_test_cli, jsonrpc_request,
                                        expected):
    with mocker.patch('jussi.handlers.random', getrandbits=lambda x: 1) as mocked_rand:
        mocked_ws_conn, test_cli = mocked_app_test_cli
        mocked_ws_conn.recv.return_value = json.dumps(expected)
        response = await test_cli.post('/', json=jsonrpc_request)
        assert response.status == 200
        assert response.headers['Content-Type'] == 'application/json'
        json_response = await response.json()
        assert json_response == expected
