# -*- coding: utf-8 -*-
import sanic.response
from sanic import Sanic

import pytest
from jussi.middlewares.jussi import add_jussi_request_id
from jussi.middlewares.jussi import add_jussi_response_id

request = {"id":"1","jsonrpc":"2.0","method":"get_block","params":[1000]}
response = {
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
        "transaction_ids": []
    }
}


def test_request_response_id_middleware():
    app = Sanic()

    @app.post('/')
    def handler(request):
        return sanic.response.text('Hello')


    app.request_middleware.append(add_jussi_request_id)
    app.response_middleware.append(add_jussi_response_id)
    _, response = app.test_client.get('/health',headers={'x-jussi-request-id':'test'})

    assert 'x-jussi-response-id' in response.headers
    assert response.headers['x-jussi-response-id'].startswith('test->')
