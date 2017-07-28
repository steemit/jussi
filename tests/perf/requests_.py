# -*- coding: utf-8 -*-
# pylint: skip-file

import logging
import os
import sys

import requests

sys.path.append(os.path.dirname(__file__))
logger = logging.getLogger(__name__)

def chunkify(iterable, chunksize=10000):
    i = 0
    chunk = []
    for item in iterable:
        chunk.append(item)
        i += 1
        if i == chunksize:
            yield chunk
            i = 0
            chunk = []
    if len(chunk) > 0:
        yield chunk


def run(block_nums, url='https://api.steemitdev.com', batch_size=100):
    s = requests.Session()
    jrpc_requests =  ({"method": "get_block", "params": [block_num], "jsonrpc": "2.0", "id": 0} for block_num in block_nums)
    batched_jrpc_requests = chunkify(jrpc_requests, batch_size)
    responses = []
    for batch in batched_jrpc_requests:
        responses.append(s.post(url, json=batch).json())
    return responses


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser('jussi perf test script')
    parser.add_argument('--blocks', type=int, default=1000)
    parser.add_argument('--url', type=str, default='https://api.steemitdev.com')
    parser.add_argument('--batch_size', type=int, default=100)
    args = parser.parse_args()
    block_nums = list(range(args.blocks))
    responses = run(block_nums, url=args.url, batch_size=args.batch_size)
