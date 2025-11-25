#! /usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import json
import random

import crayons
import requests

session = requests.Session()


def make_jrpc_call(url, jrpc_call):
    response = session.post(url, json=jrpc_call)
    return response


def make_random_batches(jrpc_calls):
    choices = random.sample(jrpc_calls, k=len(jrpc_calls))
    batches = []
    # pylint: disable=len-as-condition
    while len(choices) > 0:
        batch_size = random.randint(1, len(jrpc_calls) / 2)
        if batch_size > len(choices):
            batch_size = len(choices)
        batch = [choices.pop() for i in range(batch_size)]
        batches.append(batch)
    return batches


def open_json(filename):
    with open(filename) as f:
        return json.load(f)


def display_request(call_num, call_count, jrpc_call, show_req=False):
    if not is_batch_req(jrpc_call):
        jrpc_call = [jrpc_call]
    for call in jrpc_call:
        method = call['method']
        params = call['params']
        print(f'{call_num}/{call_count}\n\t-->\t{method} {params}')
        if show_req:
            print(f'\t{json.dumps(call)}')


def display_response(resp):
    resp_json = resp.json()
    status = resp.status_code
    if status >= 400 or has_error(resp):
        rpc_error = ''
        if 'error' in resp_json:
            rpc_error = 'JSONRPC Error'
        message = crayons.red(f'\t<--\tHTTP {status}{rpc_error}')
    else:
        message = crayons.green(f'\t<--\tHTTP {status} No JSONRPC Error')
    print(message)


def display_error(**kwargs):
    error_num = kwargs.pop('error_num')
    error_count = kwargs.pop('error_count')
    jrpc_call = kwargs.pop('jrpc_call')
    resp = kwargs.pop('resp')
    resp_json = resp.json()
    if not is_batch_req(jrpc_call):
        jrpc_call = [jrpc_call]
        resp_json = [resp_json]
    for i, call in enumerate(jrpc_call):
        method = call['method']
        params = call['params']
        message = resp_json[i]['error']['message']
        print(f'ERROR {error_num}/{error_count}\t{method}{params}')
        print(f'\t{message}')


def display_type_results(expected_type, actual_type):
    print(crayons.green(
        f'\t\texpected type:{expected_type} == actual type {actual_type}'))


def display_keys_results(expected_keys, actual_keys):
    print(crayons.green(
        f'\t\t{len(expected_keys)} expected keys equal {len(actual_keys)} actual keys'))


def display_response_equal_results(responses):
    print(crayons.green(f'\t\tall {len(responses)} responses are equal'))


def is_batch_resp(resp):
    if isinstance(resp.json(), list):
        return True
    return False


def is_batch_req(jrpc_call):
    if isinstance(jrpc_call, list):
        return True
    return False


def has_error(resp):
    rj = resp.json()
    if isinstance(rj, list):
        for r in rj:
            if 'error' in r:
                return True
    else:
        if 'error' in rj:
            return True
    return False


def make_calls(url, jrpc_calls):
    call_count = len(jrpc_calls)
    errors = []
    for call_num, jrpc_call in enumerate(jrpc_calls, 1):
        resp = make_jrpc_call(url, jrpc_call)

        display_request(call_num, call_count, jrpc_call)
        display_response(resp)
        if has_error(resp):
            errors.append((jrpc_call, resp))

    error_count = len(errors)
    print('%s errors encountered' % error_count)
    for error_num, error in enumerate(errors, 1):
        jrpc_call, resp = error
        display_error(error_num=error_num, error_count=error_count,
                      jrpc_call=jrpc_call, resp=resp)


def test_batch_speed(url, jrpc_calls):
    total_individual = 0.0
    for jrpc_call in jrpc_calls:
        resp = make_jrpc_call(url, jrpc_call)
        total_individual += resp.elapsed.total_seconds()
    resp = make_jrpc_call(url, jrpc_calls)
    total_batch = resp.elapsed.total_seconds()
    print('%s - %s = %s' %
          (total_individual, total_batch, total_individual - total_batch))


def generate_test_requests_and_responses(args):
    url = args.url
    jrpc_calls = args.jrpc_calls

    pairs = []
    for jrpc_call in jrpc_calls:
        response = make_jrpc_call(url, jrpc_call)
        response.raise_for_status()
        assert not has_error(response)
        pairs.append([jrpc_call, response.json()])
        print(json.dumps([jrpc_call, response.json()], ensure_ascii=False))
    return pairs


def test_response_results_type(request, expected, actual):
    actual_result = actual.get('result')
    ex_result = expected['result']

    assert isinstance(actual_result, type(ex_result))
    display_type_results(type(ex_result), type(actual_result))
    if isinstance(ex_result, dict):
        assert actual_result.keys() == ex_result.keys()
        display_keys_results(ex_result.keys(), actual_result.keys())


def test_response_equality(request, expected, actual, responses):
    for r in responses:
        assert responses[0] == r
    display_response_equal_results(responses)


def test_repetition(args):
    jrpc_calls = args.jrpc_calls
    repeat = args.repeat
    url = args.url
    call_count = len(jrpc_calls)
    errors = []
    for call_num, jrpc_call in enumerate(jrpc_calls, 1):
        request, expected = jrpc_call
        responses = []
        for i in range(repeat):
            response = make_jrpc_call(url, request)
            responses.append(response.json())
            display_request(f'{call_num}.{i}', call_count, request)
            display_response(response)
        if has_error(response):
            errors.append((request, response))
        try:
            test_response_results_type(
                request, expected, response.json(), responses, errors)
        except AssertionError as e:
            display_error(exception=e, request=request, response=response)
        try:
            test_response_equality(
                request, expected, response.json(), responses)
        except AssertionError as e:
            display_error(exception=e, request=request, response=response)

    error_count = len(errors)
    print('%s errors encountered' % error_count)
    for error_num, error in enumerate(errors, 1):
        request, resp = error
        display_error(error_num, error_count, request, resp)


def test_calls(args):
    make_calls(args.url, args.jrpc_calls)


def test_batch_calls():
    batch_jrpc_calls = make_random_batches(args.jrpc_calls)
    make_calls(args.url, args.batch_jrpc_calls)


def test_all_calls(url, jrpc_calls):
    make_calls(url, jrpc_calls)
    batch_jrpc_calls = make_random_batches(jrpc_calls)
    make_calls(url, batch_jrpc_calls)


if __name__ == '__main__':
    parser = argparse.ArgumentParser('jussi jsonrpc utils')
    subparsers = parser.add_subparsers()
    parser.add_argument('--url', type=str,
                        default='https://api.steemitdev.com')
    parser.add_argument('--jrpc_calls', type=open_json)
    parser.set_defaults(func=generate_test_requests_and_responses)

    parser_repeat = subparsers.add_parser('test-repetition')
    parser_repeat.add_argument('--repeat', type=int, default=10)
    parser_repeat.set_defaults(func=test_repetition)

    parser_test_calls = subparsers.add_parser('test-calls')
    parser_test_calls.set_defaults(func=test_calls)

    parser_test_batch_calls = subparsers.add_parser('test-batch-calls')
    parser_test_batch_calls.set_defaults(func=test_batch_calls)

    parser_test_all_calls = subparsers.add_parser('test-all-calls')
    parser_test_all_calls.set_defaults(func=test_all_calls)

    parser_make_api_calls = subparsers.add_parser('make-api-calls')
    parser_test_all_calls.set_defaults(func=generate_test_requests_and_responses)

    args = parser.parse_args()

    args.func(args)

    #print(json.dumps(generate_test_requests_and_responses(url, jrpc_calls),ensure_ascii=False))

    #test_batch_speed(url, jrpc_calls)
