# -*- coding: utf-8 -*-

import datetime

import ujson


def test_health_check_get(app, healthcheck_path):
    _, response = app.test_client.get(
        healthcheck_path, server_kwargs=dict(workers=1))
    assert response.status == 200
    assert response.headers['Content-Type'] == 'application/json'
    json_response = ujson.loads(response.body.decode())
    assert json_response['status'] == 'OK'
    utcnow = datetime.datetime.utcnow().isoformat()
    assert json_response['datetime'][:14] == utcnow[:14]
