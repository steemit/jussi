# -*- coding: utf-8 -*-
import datetime
import itertools

import pytest
import requests


@pytest.mark.live
def test_healtcheck_routes(healthcheck_url):
    session = requests.Session()
    response = session.get(healthcheck_url)
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'application/json'
    response_json = response.json()
    assert response_json['status'] == 'OK'
    utcnow = datetime.datetime.utcnow().isoformat()
    assert response_json['datetime'][:14] == utcnow[:14]
