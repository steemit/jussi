# -*- coding: utf-8 -*-
import pytest


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
    jrpc_result = response_json['result']
    assert isinstance(jrpc_result, type(expected_result))

    if isinstance(expected_result, dict):
        result_keys = set(jrpc_result.keys())
        expected_keys = set(expected_result.keys())
        assert expected_keys == result_keys


def repeated_response_equality(
        steemd_requests_and_responses, requests_session, jussi_url):
    request, expected = steemd_requests_and_responses
    expected_result = expected['result']
    responses = []
    for i in range(100000):
        response = requests_session.post(jussi_url, json=request)
        response.raise_for_status()
        jrpc_result = response.json()['result']
        responses.append(jrpc_result)
    for jrpc_result in responses:
        assert isinstance(jrpc_result, type(expected_result))
        if isinstance(expected_result, dict):
            result_keys = set(jrpc_result.keys())
            expected_keys = set(expected_result.keys())
            assert expected_keys == result_keys


@pytest.mark.live
def test_long_request_live(long_request, requests_session, jussi_url,
                           steemd_jrpc_response_validator,):
    response = requests_session.post(jussi_url, json=long_request)
    response.raise_for_status()
    response_json = response.json()
    assert steemd_jrpc_response_validator(response_json) is None
