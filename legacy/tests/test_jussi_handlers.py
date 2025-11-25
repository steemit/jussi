# -*- coding: utf-8 -*-

import json
import ujson
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

utf8_request = {"jsonrpc": "2.0",
                "method": "call",
                "id": 1,
                "params": [
                    "network_broadcast_api",
                    "broadcast_transaction_synchronous",
                    [
                        {"ref_block_num": 14495,
                         "ref_block_prefix": 3872236081,
                         "expiration": "2017-10-17T03:58:12",
                         "operations": [
                             [
                                 "comment",
                                 {"parent_author": "",
                                  "parent_permlink": "cn",
                                  "author": "sbd2paypal",
                                  "permlink": "gvvay",
                                  "title": "废青废老，建宗 |谷哥点名#11",
                                  "body": "「又遲到了！」年輕人醒來的時候，已時八時三十分。"
                                  }
                             ]
                         ],
                         "extensions": [],
                         "signatures":["207982c1af873b183b69457bf62996c0b27c4772999e960e4fa784f73915915a13077ccb8c98e21ca28601436f605069c67c5113dd4781631f3d6e7824a5dbe857"]
                         }
                    ]
                ]
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
    mocked_ws_conn, test_cli = mocked_app_test_cli
    mocked_ws_conn.recv.return_value = json.dumps(expected)
    response = await test_cli.post('/', json=jsonrpc_request, headers={'x-jussi-request-id': str(jsonrpc_request['id'])})
    assert response.status == 200
    assert response.headers['Content-Type'] == 'application/json'
    json_response = await response.json()
    assert json_response == expected


@pytest.mark.parametrize('jsonrpc_request, expected', [
    (utf8_request, ujson.dumps(utf8_request, ensure_ascii=False))
])
async def test_content_encoding(mocker, mocked_app_test_cli, jsonrpc_request,
                                expected):
    mocked_ws_conn, test_cli = mocked_app_test_cli
    mocked_ws_conn.recv.return_value = ujson.dumps(
        {'id': 1, 'jsonrpc': '2.0', 'result': 'ignore'}).encode()
    response = await test_cli.post('/', json=jsonrpc_request, headers={'x-jussi-request-id': str(jsonrpc_request['id'])})
    test_request = mocked_ws_conn.send.call_args[0][0]
    assert isinstance(test_request, type(expected))
    assert json.loads(test_request) == utf8_request
    assert json.loads(test_request)[
        'params'][2][0]['operations'][0][1]['body'] == "「又遲到了！」年輕人醒來的時候，已時八時三十分。"
