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


@pytest.mark.parametrize(
    'jsonrpc_request, expected',
    [
        (
            # single jsonrpc steemd request
            dict(id=1, jsonrpc='2.0', method='get_block', params=[1000]),
            correct_get_block_1000_response
        ),
        # batch jsronrpc steemd request
        (
            [
                dict(id=1, jsonrpc='2.0', method='get_block', params=[1000]),
                dict(id=1, jsonrpc='2.0', method='get_block', params=[1000])
            ],
            [correct_get_block_1000_response, correct_get_block_1000_response]
        ),
        (
            # single jsonrpc old-style steemd requests
            dict(
                id=1,
                jsonrpc='2.0',
                method='call',
                params=['database_api', 'get_block', [1000]]),
            correct_get_block_1000_response
        ),
        (
            # batch jsonrpc old-style steemd request
            [
                dict(
                    id=1,
                    jsonrpc='2.0',
                    method='call',
                    params=['database_api', 'get_block', [1000]]),
                dict(
                    id=1,
                    jsonrpc='2.0',
                    method='call',
                    params=['database_api', 'get_block', [1000]])
            ],
            [correct_get_block_1000_response, correct_get_block_1000_response]
        ),
        (
            # batch jsonrpc mixed-style steemd request
            [
                dict(id=1, jsonrpc='2.0', method='get_block', params=[1000]),
                dict(id=1, jsonrpc='2.0', method='call', params=[
                     'database_api', 'get_block', [1000]])
            ],
            [correct_get_block_1000_response, correct_get_block_1000_response]
        )
    ])
async def steemd_multi_format_requests(mocked_app_test_cli, jsonrpc_request, expected, steemd_jrpc_response_validator, mocker):

    with mocker.patch('jussi.handlers.random',
                      getrandbits=lambda x: 1) as mocked_rand:
        mocked_ws_conn, test_cli = mocked_app_test_cli
        mocked_ws_conn.recv.return_value = mocked_ws_conn.send.call_args.dumps(
            correct_get_block_1000_response)

        response = await test_cli.post('/', json=jsonrpc_request, headers={'x-jussi-request-id': '1'})
        assert response.status == 200
        assert response.headers['Content-Type'] == 'application/json'
        json_response = await response.json()
        assert steemd_jrpc_response_validator(json_response) is None
        assert json_response == expected


async def test_mocked_steemd_calls(mocked_app_test_cli, steemd_jrpc_response_validator, steemd_request_and_response, mocker):
    compare_key_only_ids = (6, 48)
    jrpc_req, jrpc_resp = steemd_request_and_response

    mocked_ws_conn, test_cli = mocked_app_test_cli
    mocked_ws_conn.recv.return_value = json.dumps(jrpc_resp)

    response = await test_cli.post('/', json=jrpc_req, headers={'x-jussi-request-id': str(jrpc_req['id'])})
    assert response.status == 200
    assert response.headers['Content-Type'] == 'application/json'
    assert 'x-jussi-cache-hit' not in response.headers
    json_response = await response.json()
    assert steemd_jrpc_response_validator(json_response) is None
    assert 'error' not in json_response
    assert json_response['id'] == jrpc_req['id']
    if jrpc_req['id'] in compare_key_only_ids:
        if isinstance(json_response['result'], dict):
            assert json_response['result'].keys() == jrpc_resp['result'].keys()
        else:
            assert len(json_response['result']) == len(jrpc_resp['result'])
    else:
        assert json_response == jrpc_resp


def jrpc_response_with_updated_id(m, jrpc):
    jrpc['id'] = json.loads(m.send.call_args[0][0])['id']
    return json.dumps(jrpc)
