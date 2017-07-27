# -*- coding: utf-8 -*-
import argparse
import asyncio
import logging
import os
import sys
import time
from functools import partial
from multiprocessing import Pool

import aiohttp
import ujson

import http_client
import requests
import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


sys.path.append(os.path.dirname(__file__))

logger = logging.getLogger(__name__)

# pylint: skip-file
MAX_CHUNKSIZE = 1000000

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


def fetch_blocks(block_nums, max_procs, max_threads, steemd_http_url):

    max_workers = max_procs or os.cpu_count() or 1

    chunksize = len(block_nums) // max_workers
    if chunksize <= 0:
        chunksize = 1

    map_func = partial(
        block_adder_process_worker, steemd_http_url, max_threads=max_threads)

    chunks = chunkify(block_nums, chunksize)

    with Pool(processes=max_workers) as pool:
        results = pool.map(map_func, chunks)

    # print(results)


def do_test(steemd_http_url, max_procs, max_threads, start=None, end=None):
    client = http_client.SimpleSteemAPIClient(url=steemd_http_url)
    try:
        start = start or 1
        end = end or client.block_height()

        missing_block_nums = list(range(start, end))

        # [2/2] adding missing blocks
        fetch_blocks(missing_block_nums, max_procs, max_threads,
                     steemd_http_url)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(e)
        raise e
    finally:
        os.killpg(os.getpgrp(), 9)


# pylint: disable=redefined-outer-name
def block_fetcher_thread_worker(rpc_url, block_nums, max_threads=None):
    rpc = http_client.SimpleSteemAPIClient(rpc_url, return_with_args=False)
    # pylint: disable=unused-variable
    for block in rpc.exec_batch('get_block',
                                block_nums):  # , max_workers=max_threads):
        yield block


def block_adder_process_worker(rpc_url, block_nums, max_threads=5):
    rpc = http_client.SimpleSteemAPIClient(rpc_url, return_with_args=False)
    for block in rpc.exec_batch('get_block',
                                block_nums):  # , max_workers=max_threads):
        print(block)


def test_requests(rpc_url, block_nums):
    s = requests.Session()
    for block_num in block_nums:
        yield s.post(rpc_url, json={"method": "get_block", "params": [block_num], "jsonrpc": "2.0", "id": 0}).json()

async def test_aiohttp(rpc_url, block_nums):
    async with aiohttp.ClientSession(json_serialize=ujson.dumps) as session:
        blocks = []
        for block_num in block_nums:
            async with session.post(rpc_url, json={"method": "get_block", "params": [block_num], "jsonrpc": "2.0", "id": 0}) as resp:
                blocks.append(await resp.json())
        return blocks

def perform_timed_operation(func, rpc_url, block_nums, *args, **kwargs):
    start = time.perf_counter()
    responses = list(func(rpc_url, block_nums))
    end = time.perf_counter()
    return start, responses, end

def perform_timed_operation_async(func, rpc_url, block_nums, *args, **kwargs):
    start = time.perf_counter()
    loop = asyncio.get_event_loop()
    responses = loop.run_until_complete(func(rpc_url, block_nums))
    end = time.perf_counter()
    return start, responses, end

# included only for debugging with pdb, all the above code should be called
# using the click framework
if __name__ == '__main__':
    parser = argparse.ArgumentParser('jussi perf test script')
    parser.add_argument('url', type=str)
    parser.add_argument('--max_procs', type=int, default=os.cpu_count() - 1)
    parser.add_argument('--max_threads', type=int, default=30)
    parser.add_argument('--start', type=int, default=1)
    parser.add_argument('--end', type=int, default=None)
    args = parser.parse_args()
    block_nums = list(range(100))
    #start, responses, end = perform_timed_operation(test_requests, args.url, block_nums)
    start, responses, end = perform_timed_operation_async(test_aiohttp, args.url, block_nums)

    elapsed = end - start
    spr = elapsed/len(block_nums)
    rps = len(block_nums)/elapsed

    print('elapsed: %s (%s/request) (%s requests/s)' % (elapsed, spr, rps))
    '''
    do_test(
        args.url,
        max_procs=args.max_procs,
        max_threads=args.max_threads,
        start=args.start,
        end=args.end)
    '''
