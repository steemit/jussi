# -*- coding: utf-8 -*-

import ujson

import pytest

CORRECT_GET_BLOCK_1000_RESPONSE = {
    "id": 1,
    "result": {
        "previous":
        "000003e7c4fd3221cf407efcf7c1730e2ca54b05",
        "timestamp":
        "2016-03-24T16:55:30",
        "witness":
        "initminer",
        "transaction_merkle_root":
        "0000000000000000000000000000000000000000",
        "extensions": [],
        "witness_signature":
        "207f15578cac20ac0e8af1ebb8f463106b8849577e21cca9fc60da146d1d95df88072dedc6ffb7f7f44a9185bbf9bf8139a5b4285c9f423843720296a44d428856",
        "transactions": [],
        "block_id":
        "000003e8b922f4906a45af8e99d86b3511acd7a5",
        "signing_key":
        "STM8GC13uCZbP44HzMLV6zPZGwVQ8Nt4Kji8PapsPiNq1BK153XTX",
        "transaction_ids": []
    }
}

@pytest.mark.timeout(5)
@pytest.mark.parametrize(
    'request',
    [
        # single jsonrpc steemd request
        dict(id=1, jsonrpc='2.0', method='get_block', params=[1000]),

        # batch jsronrpc steemd request
        [
            dict(id=2, jsonrpc='2.0', method='get_block', params=[1000]),
            dict(id=3, jsonrpc='2.0', method='get_block', params=[1000])
        ],

        # single jsonrpc old-style steemd requests
        dict(
            id=1,
            jsonrpc='2.0',
            method='call',
            params=['database_api', 'get_block', [1000]]),

        # batch jsonrpc old-style steemd request
        [
            dict(
                id=4,
                jsonrpc='2.0',
                method='call',
                params=['database_api', 'get_block', [1000]]),
            dict(
                id=5,
                jsonrpc='2.0',
                method='call',
                params=['database_api', 'get_block', [1000]]),
        ],

        # batch jsonrpc mixed-style steemd request
        [
            dict(id=6, jsonrpc='2.0', method='get_block', params=[1000]),
            dict(
                id=7,
                jsonrpc='2.0',
                method='call',
                params=['database_api', 'get_block', [1000]]),
        ]
    ])
def test_jsonrpc_request(app, request):
    _, response = app.test_client.post(
        '/', json=request, server_kwargs=dict(workers=1))
    assert response.status == 200
    assert response.headers['Content-Type'] == 'application/json'
    json_response = ujson.loads(response.body.decode())
    if isinstance(request, list):
        assert isinstance(json_response, list)
        for i, resp in enumerate(json_response):
            assert isinstance(resp, dict)
            assert request[i]['id'] == resp['id']
            assert 'error' not in resp
    if isinstance(request, dict):
        assert request['id'] == json_response['id']
        assert isinstance(json_response, dict)
        assert 'error' not in json_response

@pytest.mark.timeout(5)
def test_batch_jsonrpc_requests(app, random_jrpc_batch):
    _, response = app.test_client.post(
        '/', json=random_jrpc_batch, server_kwargs=dict(workers=1))
    assert response.status == 200
    assert response.headers['Content-Type'] == 'application/json'
    json_response = ujson.loads(response.body.decode())
    assert isinstance(json_response, list)
    assert len(json_response) == len(random_jrpc_batch)
    for i, item in enumerate(json_response):
        assert item['id'] == random_jrpc_batch[i]['id']
        assert 'result' in item
        assert 'error' not in item


def test_all_steemd_calls(app, all_steemd_jrpc_calls):
    _, response = app.test_client.post(
        '/', json=all_steemd_jrpc_calls, server_kwargs=dict(workers=1))
    assert response.status == 200
    assert response.headers['Content-Type'] == 'application/json'
    json_response = ujson.loads(response.body.decode())
    assert 'id' in json_response
    assert 'result' in json_response
    assert 'error' not in json_response
