# -*- coding: utf-8 -*-
import argparse
import os
import sys
import logging
sys.path.append(os.path.dirname(__file__))

from multiprocessing import Pool
from functools import partial

import http_client

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


def fetch_blocks(block_nums,
                            max_procs,
                            max_threads,
                            steemd_http_url):


    max_workers = max_procs or os.cpu_count() or 1

    chunksize = len(block_nums) // max_workers
    if chunksize <= 0:
        chunksize = 1

    map_func = partial(
        block_adder_process_worker,
        steemd_http_url,
        max_threads=max_threads)

    chunks = chunkify(block_nums, 10000)

    with Pool(processes=max_workers) as pool:
        results = pool.map(map_func, chunks)

    print(results)

def do_test(steemd_http_url, max_procs, max_threads, start=None, end=None):
    client = http_client.SimpleSteemAPIClient(url=steemd_http_url)
    print(client.get_dynamic_global_properties())
    try:


        start = start or 1
        end = end or client.block_height()
	
        missing_block_nums = list(range(start,end))


        # [2/2] adding missing blocks
        fetch_blocks(
            missing_block_nums,
            max_procs,
            max_threads,
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
    for block in rpc.exec_multi_with_futures(
            'get_block', block_nums, max_workers=max_threads):
        yield block


def block_adder_process_worker(
                               rpc_url,
                               block_nums,
                               max_threads=5):

    for raw_block in block_fetcher_thread_worker(rpc_url, block_nums, max_threads=max_threads):
        print(raw_block)
    return True

# included only for debugging with pdb, all the above code should be called
# using the click framework
if __name__ == '__main__':
    parser = argparse.ArgumentParser('jussi perf test script')
    parser.add_argument('url',type=str)
    parser.add_argument('--max_procs',type=int, default=os.cpu_count() -1)
    parser.add_argument('--max_threads',type=int, default=30) 
    parser.add_argument('--start',type=int, default=1) 
    parser.add_argument('--end',type=int, default=None) 
    args = parser.parse_args()
    do_test(args.url, max_procs=args.max_procs, max_threads=args.max_threads,start=args.start, end=args.end)
