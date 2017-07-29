# -*- coding: utf-8 -*-
# pylint: skip-file
import asyncio

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
    def __init__(self, url, block_nums, batch_size=100, batches_per_chunk=10):
        self.url = url
        self.block_nums = block_nums
        self.batch_size = batch_size
        self.session = aiohttp.ClientSession(json_serialize=ujson.dumps)
        self.requests =  ({"method": "get_block", "params": [block_num], "jsonrpc": "2.0", "id": 0} for block_num in self.block_nums)
        self.batches = chunkify(self.requests, self.batch_size)
        self.batches_per_chunk=batches_per_chunk


    async def fetch_batch(self, batch):
        async with self.session.post(self.url, json=batch) as resp:
            try:
                return await resp.json()
            except Exception as e:
                print(e)
                print(await resp.text())

    async def __aiter__(self):
        return self



    async def gen_yield(self):
        all_batch_requests = (asyncio.ensure_future(self.fetch_batch(batch)) for batch in self.batches)
        chunked_batches = chunkify(all_batch_requests, self.batches_per_chunk)
        for i,chunk in enumerate(chunked_batches):
            for j,batch in enumerate(asyncio.as_completed(chunk)):
                print('chunk: %s batch: %s' % (i,j))
                try:
                    data = await batch
                except Exception as e:
                    print(e)
                else:
                    if data:
                        yield data

async def run(block_nums, url='https://api.steemitdev.com', batch_size=100):
    block_iter = AsyncBlockIterator(url, block_nums,batch_size=batch_size)
    responses = []
    async for batch in block_iter:
        responses.extend(batch)
    return responses

async def run2(block_nums, url=None, batch_size=None, batches_per_chunk=None):
    block_iter = AsyncBlockIterator(url, block_nums,batch_size=batch_size, batches_per_chunk=batches_per_chunk)
    responses = []
    count = 0
    async for batch in block_iter.gen_yield():
        count += len(batch)
        print('%s' % count)
    return responses


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser('jussi perf test script')
    parser.add_argument('--blocks', type=int, default=1000)
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--url', type=str, default='https://api.steemitdev.com')
    parser.add_argument('--batch_size', type=int, default=100)
    parser.add_argument('--batches_per_chunk', type=int, default=10)

    parser.add_argument('--print', type=bool, default=False)
    args = parser.parse_args()
    block_nums = list(range(args.offset, args.blocks))
    loop = asyncio.get_event_loop()
    responses = loop.run_until_complete(run2(block_nums, url=args.url, batch_size=args.batch_size, batches_per_chunk=args.batches_per_chunk))
    print(sum(len(r) for r in responses))
    if args.print:
        print(responses)
