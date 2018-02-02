# -*- coding: utf-8 -*-
import pytest

jrpc_request = {"id": "1", "jsonrpc": "2.0", "method": "get_block", "params": [1000]}


@pytest.mark.live
def test_response_results_type(
    steemd_requests_and_responses,
        requests_session,
        jussi_url,
        steemd_jrpc_response_validator,
        jrpc_request_validator,
        jrpc_response_validator):

    request, expected = steemd_requests_and_responses
    assert jrpc_request_validator(request) is None
    try:
        assert jrpc_response_validator(expected) is None
    except Exception as e:
        print(f'invalid jsonrpc response expected: {expected["id"]}')
    expected_result = expected['result']
    response = requests_session.post(jussi_url, json=request)
    response.raise_for_status()

    assert response.headers['Content-Type'] == 'application/json'
    assert 'x-jussi-request-id' in response.headers
    response_json = response.json()
    assert response_json['id'] == request['id']

    assert steemd_jrpc_response_validator(response_json) is None
    try:
        assert jrpc_response_validator(response_json) is None
    except Exception as e:
        print(f'invalid jsonrpc response: {response_json}')
    try:
        jrpc_result = response_json['result']
    except Exception as e:
        print('error:%s result:%s' % (e, response_json))
        raise e
    assert 'error' not in response_json, '%s' % response_json
    #assert isinstance(jrpc_result, type(expected_result))

    # if isinstance(expected_result, dict):
    #    result_keys = set(jrpc_result.keys())
    #    expected_keys = set(expected_result.keys())
    #    assert expected_keys == result_keys, '%s' % response_json


@pytest.mark.live
def test_appbase_translation_responses(
    translatable_steemd_requests_and_responses,
        requests_session,
        jussi_url,
        steemd_jrpc_response_validator,
        jrpc_request_validator,
        jrpc_response_validator):

    request, expected = translatable_steemd_requests_and_responses
    assert jrpc_request_validator(request) is None
    try:
        assert jrpc_response_validator(expected) is None
    except Exception as e:
        print(f'invalid jsonrpc response expected: {expected["id"]}')
    expected_result = expected['result']
    response = requests_session.post(jussi_url, json=request)
    response.raise_for_status()

    assert response.headers['Content-Type'] == 'application/json'
    assert 'x-jussi-request-id' in response.headers
    assert response.headers['Access-Control-Allow-Origin'] == "*"
    assert response.headers['Access-Control-Allow-Methods'] == "GET, POST, OPTIONS"
    assert response.headers['Access-Control-Allow-Headers'] == "DNT,Keep-Alive,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Content-Range,Range"
    assert response.headers['Strict-Transport-Security'] == "max-age=31557600; includeSubDomains; preload"
    assert response.headers['Content-Security-Policy'] == 'upgrade-insecure-requests'
    response_json = response.json()
    assert response_json['id'] == request['id']

    assert steemd_jrpc_response_validator(response_json) is None
    assert jrpc_response_validator(response_json) is None, f'invalid response {response_json}'
    assert 'result' in response_json, f' result not in {response_json}'
    assert 'error' not in response_json, '%s' % response_json
    try:
        assert isinstance(response_json['response'], type(expected_result))

        if isinstance(expected_result, dict):
            result_keys = set(response_json['response'].keys())
            expected_keys = set(expected_result.keys())
            assert expected_keys == result_keys, '%s' % response_json
    except Exception as e:
        print(f'WARNING: {e}')

        
@pytest.mark.live
@pytest.mark.parametrize('path,method', [
    ('/', 'GET'),
    ('/', 'OPTIONS'),
    ('/', 'HEAD'),
    ('/', 'POST'),
    ('/health', 'GET'),
    ('/.well-known/healthcheck.json', 'GET')
])
def test_response_headers(path, method, requests_session, jussi_url):
    json_data = None
    if method == 'POST':
        json_data = jrpc_request
    resp = requests_session.request(method, jussi_url + path, json=json_data)
    assert resp.headers['Access-Control-Allow-Origin'] == "*"
    assert resp.headers['Access-Control-Allow-Methods'] == "GET, POST, OPTIONS"
    assert resp.headers['Access-Control-Allow-Headers'] == "DNT,Keep-Alive,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Content-Range,Range"
    assert resp.headers['Strict-Transport-Security'] == "max-age=31557600; includeSubDomains; preload"
    assert resp.headers['Content-Security-Policy'] == 'upgrade-insecure-requests'
    if method == 'OPTIONS':
        assert resp.headers['Allow'] == 'GET,HEAD,OPTIONS,POST'


@pytest.mark.live
def test_long_request_live(long_request, requests_session, jussi_url,
                           steemd_jrpc_response_validator,):
    response = requests_session.post(jussi_url, json=long_request)
    response.raise_for_status()
    response_json = response.json()
    assert steemd_jrpc_response_validator(response_json) is None
