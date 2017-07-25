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
        print('{call_num}/{call_count}\n\t-->\t{method}{params}'.format(call_num=call_num,
                                                                 call_count=call_count,
                                                                 method=method,
                                                                 params=params))
        if show_req:
            print('\t%s' % json.dumps(call))


def display_response(resp):
    resp_json = resp.json()
    status = resp.status_code
    if status >= 400 or has_error(resp):
        rpc_error = ''
        if 'error' in resp_json:
            rpc_error = 'JSONRPC Error'
        message = crayons.red('\t<--\t HTTP {status}{rpc_error}'.format(status=status, rpc_error=rpc_error))
    else:
        message = crayons.green('\t<--\t HTTP {status} No JSONRPC Error'.format(status=status))
    print(message)
    print('')

def display_error(error_num, error_count, jrpc_call, resp):
    resp_json = resp.json()
    if not is_batch_req(jrpc_call):
        jrpc_call = [jrpc_call]
        resp_json = [resp_json]
    for i,call in enumerate(jrpc_call):
        method = call['method']
        params = call['params']
        message = resp_json[i]['error']['message']
        print('ERROR {error_num}/{error_count}\t{method}{params}'.format(error_num=error_num,
                                                                         error_count=error_count,
                                                                         method=method,
                                                                         params=params))
        print('\t{message}'.format(message=message))


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
        display_error(error_num, error_count, jrpc_call, resp)


def test_batch_speed(url, jrpc_calls):
    total_individual = 0.0
    for jrpc_call in jrpc_calls:
        resp = make_jrpc_call(url, jrpc_call)
        total_individual += resp.elapsed.total_seconds()
    resp = make_jrpc_call(url, jrpc_calls)
    total_batch = resp.elapsed.total_seconds()
    print('%s - %s = %s' % (total_individual,total_batch,total_individual-total_batch))


def generate_test_requests_and_responses(url, jrpc_calls):
    #jrpc_calls += make_random_batches(jrpc_calls)
    pairs = []
    for jrpc_call in jrpc_calls:
        response = make_jrpc_call(url, jrpc_call)
        response.raise_for_status()
        assert not has_error(response)
        pairs.append([jrpc_call, response.json()])
        #print(json.dumps([jrpc_call, response.json()], ensure_ascii=False).encode())
    return pairs


if __name__ == '__main__':

    parser = argparse.ArgumentParser('jussi jsonrpc test script')
    parser.add_argument('jsonrpc_calls', type=open_json)
    parser.add_argument('url',type=str, default='http://localhost:8080')
    args = parser.parse_args()
    jrpc_calls = args.jsonrpc_calls
    url = args.url

    print(json.dumps(generate_test_requests_and_responses(url, jrpc_calls),ensure_ascii=False))

    #make_calls(url, jrpc_calls)
    #make_calls(url, make_random_batches(jrpc_calls))
    #test_batch_speed(url, jrpc_calls)
