# -*- coding: utf-8 -*-
# pylint: skip-file
import argparse
import asyncio
import logging
import os
import sys
import time

import aiohttp
import ujson

import requests

s = requests.Session()


sys.path.append(os.path.dirname(__file__))

logger = logging.getLogger(__name__)


# set up for clean exit


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


def make_batch_request(rpc_url, batch):

    resp = s.post(rpc_url, json=batch)
    return resp


def show_results(results, total=2000):
    for batch_size, start, end, resp_time in results:
        elapsed = end - start
        spr = elapsed / batch_size
        rps = batch_size / elapsed
        sync_time = (13000000 / rps) / 360
        print('batch size: %s elapsed: %s %s (%s/request) (%s requests/s) sync time: %s hours' %
              (batch_size, elapsed, resp_time, spr, rps, sync_time))


if __name__ == '__main__':
    block_nums = list(range(2000))
    rpc_reqs = [{"method": "get_block", "params": [block_num],
                 "jsonrpc": "2.0", "id": 0} for block_num in block_nums]
    results = []
    for batch_size in range(1, 400, 10):
        print('Making JSONRPc request in batch of %s' % batch_size)

        # print(resp)
        for test in range(1, 3):
            batches = list(chunkify(rpc_reqs, batch_size))
            resp = make_batch_request('https://api.steemitdev.com', batches[0])
            start = time.perf_counter()
            resp = make_batch_request('https://api.steemitdev.com', batches[0])
            end = time.perf_counter()
            results.append((batch_size, start, end, resp.elapsed))
    show_results(results)
