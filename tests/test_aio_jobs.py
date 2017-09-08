# -*- coding: utf-8 -*-

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


class WSProto:
    @classmethod
    async def connect(kls):
        return kls()

    async def close(self):
        return None


async def return_value_async(val, mocked=None):
    if mocked:
        mocked.return_value = return_value_async(val, mocked)
    return val


def test_aio_job_scheduled(app, mocker):

    mocked_ws = mocker.patch('jussi.listeners.websockets_connect',autospec=True)
    mocked_ws.return_value = return_value_async(WSProto(), mocked_ws)

    mocked = mocker.patch('jussi.jobs.requester')
    mocked.return_value = return_value_async(GDGP_RESULT)

    assert 'last_irreversible_block_num' not in app.config
    _, _ = app.test_client.get('/health')
    assert app.config.last_irreversible_block_num == 15091586



def test_aio_job_caching(app, mocker):

    mocked_ws = mocker.patch('jussi.listeners.websockets_connect',autospec=True)
    mocked_ws.return_value = return_value_async(WSProto(), mocked_ws)

    mocked_requester = mocker.patch('jussi.jobs.requester')
    mocked_requester.return_value = return_value_async(GDGP_RESULT)

    mocked_fetch_ws = mocker.patch('jussi.handlers.fetch_ws')
    mocked_fetch_ws.return_value = return_value_async(GDGP_RESULT)

    assert 'last_irreversible_block_num' not in app.config
    _, _ = app.test_client.get('/health')
    assert app.config.last_irreversible_block_num == 15091586
    _, response = app.test_client.post(
        '/',
        json={
            "id": 4,
            "jsonrpc": "2.0",
            "method": "get_dynamic_global_properties"
        })
    assert response.headers[
        'x-jussi-cache-hit'] == 'steemd.database_api.get_dynamic_global_properties'

    assert response.json['id'] == 4
