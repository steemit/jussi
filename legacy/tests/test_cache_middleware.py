# -*- coding: utf-8 -*-
import json


import pytest


req = {"id": 1, "jsonrpc": "2.0", "method": "get_dynamic_global_properties"}

expected_steemd_response = {
    "id": "1",
    "result": {
        "average_block_size": 16112,
        "confidential_sbd_supply": "0.000 SBD",
        "confidential_supply": "0.000 STEEM",
        "current_aslot": 19615022,
        "current_reserve_ratio": 1243817,
        "current_sbd_supply": "8016379.428 SBD",
        "current_supply": "263590437.017 STEEM",
        "current_witness": "good-karma",
        "head_block_id": "012a58ebf2e150d2200da72acff4c6b272915e08",
        "head_block_number": 19552491,
        "id": 0,
        "last_irreversible_block_num": 19552476,
        "max_virtual_bandwidth": "1643338184785920000",
        "maximum_block_size": 65536,
        "num_pow_witnesses": 172,
        "participation_count": 128,
        "pending_rewarded_vesting_shares": "298814345.817945 VESTS",
        "pending_rewarded_vesting_steem": "145258.167 STEEM",
        "recent_slots_filled": "340282366920938463463374607431768211455",
        "sbd_interest_rate": 0,
        "sbd_print_rate": 10000,
        "time": "2018-02-03T17:51:06",
        "total_pow": 514415,
        "total_reward_fund_steem": "0.000 STEEM",
        "total_reward_shares2": "0",
        "total_vesting_fund_steem": "195640068.504 STEEM",
        "total_vesting_shares": "400228023408.017941 VESTS",
        "virtual_supply": "265290623.534 STEEM",
        "vote_power_reserve_rate": 10
    }
}


expected_response = {
    "id": 1,
    "jsonrpc": "2.0",
    "result": {
        "average_block_size": 16112,
        "confidential_sbd_supply": "0.000 SBD",
        "confidential_supply": "0.000 STEEM",
        "current_aslot": 19615022,
        "current_reserve_ratio": 1243817,
        "current_sbd_supply": "8016379.428 SBD",
        "current_supply": "263590437.017 STEEM",
        "current_witness": "good-karma",
        "head_block_id": "012a58ebf2e150d2200da72acff4c6b272915e08",
        "head_block_number": 19552491,
        "id": 0,
        "last_irreversible_block_num": 19552476,
        "max_virtual_bandwidth": "1643338184785920000",
        "maximum_block_size": 65536,
        "num_pow_witnesses": 172,
        "participation_count": 128,
        "pending_rewarded_vesting_shares": "298814345.817945 VESTS",
        "pending_rewarded_vesting_steem": "145258.167 STEEM",
        "recent_slots_filled": "340282366920938463463374607431768211455",
        "sbd_interest_rate": 0,
        "sbd_print_rate": 10000,
        "time": "2018-02-03T17:51:06",
        "total_pow": 514415,
        "total_reward_fund_steem": "0.000 STEEM",
        "total_reward_shares2": "0",
        "total_vesting_fund_steem": "195640068.504 STEEM",
        "total_vesting_shares": "400228023408.017941 VESTS",
        "virtual_supply": "265290623.534 STEEM",
        "vote_power_reserve_rate": 10
    }
}


@pytest.mark.live
async def test_cache_response_middleware(test_cli):
    response = await test_cli.post('/', json=req)
    assert await response.json() == expected_steemd_response
    response = await test_cli.post('/', json=req)
    assert response.headers['x-jussi-cache-hit'] == 'steemd.database_api.get_dynamic_global_properties'


async def test_mocked_cache_response_middleware(mocked_app_test_cli):
    mocked_ws_conn, test_cli = mocked_app_test_cli
    mocked_ws_conn.recv.return_value = json.dumps(expected_response)
    response = await test_cli.post('/', json=req, headers={'x-jussi-request-id': '1'})
    assert 'x-jussi-cache-hit' not in response.headers
    assert await response.json() == expected_response

    response = await test_cli.post('/', json=req, headers={'x-jussi-request-id': '1'})
    assert response.headers['x-jussi-cache-hit'] == 'steemd.database_api.get_dynamic_global_properties'
    assert await response.json() == expected_response
