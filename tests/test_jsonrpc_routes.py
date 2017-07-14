# -*- coding: utf-8 -*-

import ujson


def test_jsonrpc_route(app):
    _, response = app.test_client.post(
        '/',
        json=dict(id=1, jsonrpc='2.0', method='get_block', params=[1000]),
        server_kwargs=dict(workers=1))
    assert response.status == 200
    assert response.headers['Content-Type'] == 'application/json'
    json_response = ujson.loads(response.body.decode())
    assert isinstance(json_response, dict)
    #jrpc_response_validator.validate(json_response)
