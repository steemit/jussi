# -*- coding: utf-8 -*-
import websockets

import asynctest


async def test_mock(test_cli):

    request = {"id": 1, "jsonrpc": "2.0", "method": "get_block", "params": [1000]}
    expected = {
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
            "transaction_ids": []
        }
    }

    with asynctest.patch('jussi.ws.pool.Pool') as mocked_pool:
        mocked_ws_conn = asynctest.MagicMock(spec=websockets.client.WebSocketClientProtocol)
        mocked_ws_conn.recv.return_value = expected
        mocked_pool.acquire.return_value = mocked_ws_conn
        response = await test_cli.post('/', json=request)
        assert await response.json() == expected
