# -*- coding: utf-8 -*-

import json

import ujson

import pytest


async def return_value_async(val, mocked=None):
    if mocked:
        mocked.return_value = return_value_async(val, mocked)
    return val



def correct_get_block_1000_response(_ids):
    result = []
    for _id in _ids:
        result.append({
        "id": _id,
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
    })
    if len(result) == 1:
        return result[0]
    return result


GDGP_RESULT = {
    "id": 1,
    "result": {
       "id": 0,
       "head_block_number": 15091602,
       "head_block_id": "00e647927f2c1e088ca7abf8f5f0c41d9bd31d7a",
       "time": "2017-09-01T18:00:33",
       "current_witness": "liondani",
       "total_pow": 514415,
       "num_pow_witnesses": 172,
       "virtual_supply": "256990806.124 STEEM",
       "current_supply": "254617838.496 STEEM",
       "confidential_supply": "0.000 STEEM",
       "current_sbd_supply": "3495381.317 SBD",
       "confidential_sbd_supply": "0.000 SBD",
       "total_vesting_fund_steem": "182911294.809 STEEM",
       "total_vesting_shares": "377157836143.023703 VESTS",
       "total_reward_fund_steem": "0.000 STEEM",
       "total_reward_shares2": "0",
       "pending_rewarded_vesting_shares":"298753448.572389 VESTS",
       "pending_rewarded_vesting_steem": "144587.895 STEEM",
       "sbd_interest_rate": 0,
       "sbd_print_rate": 10000,
       "maximum_block_size": 65536,
       "current_aslot": 15151211,
       "recent_slots_filled": "340282366920938463463374607431768211455",
       "participation_count": 128,
       "last_irreversible_block_num": 15091586,
       "vote_power_reserve_rate": 10,
       "current_reserve_ratio": 200000000,
       "average_block_size": 7180,
       "max_virtual_bandwidth": "264241152000000000000"
    }
}





@pytest.mark.timeout(30)
@pytest.mark.parametrize(
    'jsonrpc_request, expected',
    [
        (
            # single jsonrpc steemd request
            dict(id=1, jsonrpc='2.0', method='get_block', params=[1000]),
            correct_get_block_1000_response(_ids=[1])
        ),
        # batch jsronrpc steemd request
        (
            [
                dict(id=2, jsonrpc='2.0', method='get_block', params=[1000]),
                dict(id=3, jsonrpc='2.0', method='get_block', params=[1000])
            ],
            correct_get_block_1000_response(_ids=[2,3])
        ),
        (
            # single jsonrpc old-style steemd requests
            dict(
                id=4,
                jsonrpc='2.0',
                method='call',
                params=['database_api', 'get_block', [1000]]),
            correct_get_block_1000_response(_ids=[4])
        ),
        (
            # batch jsonrpc old-style steemd request
            [
                dict(
                    id=5,
                    jsonrpc='2.0',
                    method='call',
                    params=['database_api', 'get_block', [1000]]),
                dict(
                    id=6,
                    jsonrpc='2.0',
                    method='call',
                    params=['database_api', 'get_block', [1000]])
            ],
            correct_get_block_1000_response(_ids=[5,6])
        ),
        (
            # batch jsonrpc mixed-style steemd request
            [
                dict(id=7, jsonrpc='2.0', method='get_block', params=[1000]),
                dict(id=8, jsonrpc='2.0', method='call',params=['database_api', 'get_block', [1000]])
            ],
            correct_get_block_1000_response(_ids=[7,8])
        )
    ])
def test_jsonrpc_request(jsonrpc_request, expected, app, mocker, steemd_jrpc_response_validator):
    class WSProto:
        open = True

        def __init__(self, request=None, expected=None):
            self.expected = expected
            self.request = request
            self.send_data = None

        @classmethod
        async def connect(cls):
            return cls()

        async def close(self):
            return None

        async def send(self, data):
            self.send_data = ujson.loads(data.decode())

        async def recv(self):
            return json.dumps(correct_get_block_1000_response(_ids=[self.send_data.get('id', 1)]))

    mocked_ws = mocker.patch('jussi.listeners.websockets_connect', autospec=True)
    mocked_ws.return_value = return_value_async(WSProto(jsonrpc_request, expected))

    _, response = app.test_client.post('/', json=jsonrpc_request)
    assert response.status == 200
    assert response.headers['Content-Type'] == 'application/json'
    json_response = ujson.loads(response.body.decode())
    assert steemd_jrpc_response_validator(json_response) is None
    assert json_response == expected


def test_mocked_steemd_calls(app, steemd_jrpc_response_validator, mocker, steemd_requests_and_responses):
    class WSProto:
        open = True

        def __init__(self, request=None, expected=None):
            self.expected = expected
            self.request = request
            self.send_data = None

        @classmethod
        async def connect(cls):
            return cls()

        async def close(self):
            return None

        async def send(self, data):
            self.send_data = ujson.loads(data.decode())

        async def recv(self):
            return json.dumps(self.expected)

    jrpc_req, jrpc_resp = steemd_requests_and_responses
    mocked = mocker.patch('jussi.jobs.requester')

    if jrpc_req['method'] == 'get_dynamic_global_properties':
        mocked.return_value = return_value_async(jrpc_resp,mocked)
    elif jrpc_req['method'] == 'call' and jrpc_req['params'][1] == 'get_dynamic_global_properties':
        mocked.return_value = return_value_async(jrpc_resp)
    else:
        mocked.return_value = return_value_async(GDGP_RESULT)

    mocked_ws = mocker.patch('jussi.listeners.websockets_connect', autospec=True)
    mocked_ws.return_value = return_value_async(WSProto(jrpc_req, jrpc_resp))

    _, response = app.test_client.post('/', json=jrpc_req)
    assert response.status == 200
    assert response.headers['Content-Type'] == 'application/json'
    json_response = ujson.loads(response.body.decode())
    assert steemd_jrpc_response_validator(json_response) is None
    assert 'error' not in json_response
    assert json_response['id'] == jrpc_req['id']
    assert json_response == jrpc_resp


    mocked_ws.return_value = return_value_async(WSProto(jrpc_req, jrpc_resp))
    _, response = app.test_client.post('/', json=jrpc_req)
    assert response.status == 200
    assert response.headers['Content-Type'] == 'application/json'
    assert 'x-jussi-cache-hit' in response.headers
    json_response = ujson.loads(response.body.decode())
    assert steemd_jrpc_response_validator(json_response) is None
    assert 'error' not in json_response
    assert json_response['id'] == jrpc_req['id']
    assert json_response == jrpc_resp

'''
@pytest.mark.timeout(30)
@pytest.mark.live_steemd
def test_all_steemd_calls(app, steemd_jrpc_response_validator, steemd_requests_and_responses):
    jrpc_req, jrpc_resp = steemd_requests_and_responses
    _, response = app.test_client.post('/', json=jrpc_req)
    assert response.status == 200
    assert response.headers['Content-Type'] == 'application/json'
    json_response = ujson.loads(response.body.decode())
    assert steemd_jrpc_response_validator(json_response) is None
    assert 'error' not in json_response
    assert json_response['id'] == jrpc_req['id']
    assert isinstance(json_response['result'], type(jrpc_resp['result']))
    if isinstance(json_response['result'], dict):
        assert json_response['result'].keys() == jrpc_resp['result'].keys()
'''
