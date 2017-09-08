# -*- coding: utf-8 -*-
import datetime
import itertools

import pytest
import requests


def test_docker_jsonrpc_routes(jussi_docker_service, all_steemd_jrpc_calls):
    session = requests.Session()
    response = session.post(jussi_docker_service, json=all_steemd_jrpc_calls)
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'application/json'
    response_json = response.json()
    assert all_steemd_jrpc_calls.get('id') == response_json.get('id')
    assert 'result' in response_json
    assert 'error' not in response_json


def test_docker_healtcheck_routes(jussi_docker_service, healthcheck_path):
    session = requests.Session()
    url = ''.join([jussi_docker_service, healthcheck_path])
    response = session.get(url)
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'application/json'
    response_json = response.json()
    assert response_json['status'] == 'OK'
    utcnow = datetime.datetime.utcnow().isoformat()
    assert response_json['datetime'][:14] == utcnow[:14]

http_methods = ['GET','HEAD','POST','PUT','DELETE','CONNECT','OPTIONS','PATCH']
healthcheck_paths= ['/', '/health', '/.well-known/healthcheck.json']


def make_params(path,allowed, not_allowed_status_code=403):
    for m in http_methods:
        if m in allowed:
            yield (path, m, 200)
        else:
            yield (path, m, not_allowed_status_code)

params1 = make_params('/', ['GET','HEAD','OPTIONS','POST'])
params2 = make_params('/health', ['GET','HEAD','OPTIONS'])
params3 = make_params('/.well-known/healthcheck.json',['GET','HEAD','OPTIONS'])
params4 = make_params('/index.html',[])
params5 = make_params('/stats',[])
params6 = make_params('/nginx_status',[])


@pytest.mark.parametrize('path,method,expected_status',
                          itertools.chain(params1,params2,params3,params4,params5),
                          ids=lambda a,b,c: '%s %s' % (a, b))
def test_docker_restricted_routes(jussi_docker_service,path,method,expected_status):
    session = requests.Session()
    url = ''.join([jussi_docker_service, path])
    response = session.request(method, url)
    assert response.status_code == expected_status
