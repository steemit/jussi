#! /usr/bin/env python
# -*- coding: utf-8 -*-
import json
import sys

import requests

session = requests.Session()

def make_jrpc_call(url, jrpc_call):
    response = session.post(url, json=jrpc_call)
    return response.json()

if __name__ == '__main__':
    calls = sys.argv[1]
    url = sys.argv[2]
    with open(calls) as f:
        jrpc_calls = json.load(f)
    call_count = len(jrpc_calls)
    errors = []
    for i,jrpc_call in enumerate(jrpc_calls,1):

        method = jrpc_call['method']
        params = jrpc_call['params']
        print('%s/%s\t%s%s' % (i,call_count,method,params))
        print('\t-->\n\t%s' % json.dumps(jrpc_call))
        response = make_jrpc_call(url, jrpc_call)
        print('\t<--\n\t%s' % json.dumps(response))
        if 'error' in response:
            errors.append((jrpc_call,method,params,response))
    error_count = len(errors)
    print('%s errors encountered' % error_count)
    for i,error in enumerate(errors,1):
        print('ERROR %s/%s\t%s%s' % (i,error_count,error[1],error[2]))
        print('\t%s' % error[3]['error'].get('message'))
