# -*- coding: utf-8 -*-
import pytest


@pytest.mark.live
def test_response_results_type(
        steemd_requests_and_responses, requests_session, jussi_url):
    request, expected = steemd_requests_and_responses
    expected_result = expected['result']
    response = requests_session.post(jussi_url, json=request)
    response.raise_for_status()
    jrpc_result = response.json()['result']
    assert type(jrpc_result) is type(expected_result)
    if isinstance(expected_result, dict):
        result_keys = set(jrpc_result.keys())
        expected_keys = set(expected_result.keys())
        assert expected_keys == result_keys


@pytest.mark.live
def test_repeated_response_equality(
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
        assert type(jrpc_result) is type(expected_result)
        if isinstance(expected_result, dict):
            result_keys = set(jrpc_result.keys())
            expected_keys = set(expected_result.keys())
            assert expected_keys == result_keys
