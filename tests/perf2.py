# -*- coding: utf-8 -*-
# pylint: skip-file
import asyncio
import time

import aiohttp
import ujson

import uvloop

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


def chunkify(iterable, chunksize=10):
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

class AsyncBlockIterator:
    def __init__(self, url, block_nums):
        self.url = url
        self.block_nums = block_nums
        self.session = aiohttp.ClientSession(json_serialize=ujson.dumps)
        self.requests =  ({"method": "get_block", "params": [block_num], "jsonrpc": "2.0", "id": 0} for block_num in self.block_nums)
        self.batches = chunkify(self.requests, 500)


    async def fetch_batch(self, batch):
        async with self.session.post(self.url, json=batch) as resp:
            return await resp.json()

    async def __aiter__(self):
        return self
    async def __anext__(self):
        for batch in asyncio.as_completed([asyncio.ensure_future(self.fetch_batch(batch)) for batch in self.batches]):
            data = await batch
            if data:
                return data
            else:
                raise StopAsyncIteration
        raise StopAsyncIteration

async def run(block_nums):
    block_iter = AsyncBlockIterator('https://api.steemitdev.com', block_nums)
    responses = []
    async for batch in block_iter:
        responses.append(batch)
    return responses

if __name__ == '__main__':
    block_nums = list(range(1000))
    loop = asyncio.get_event_loop()
    start = time.perf_counter()
    responses = loop.run_until_complete(run(block_nums))
    end = time.perf_counter()
    elapsed = end - start
    spr = elapsed / len(block_nums)
    rps = len(block_nums) / elapsed
    sync_time = (13000000/rps)/360
    print(responses[0])

    print('elapsed: %s (%s/request) (%s requests/s) sync time: %s hours' % (elapsed, spr, rps, sync_time))
