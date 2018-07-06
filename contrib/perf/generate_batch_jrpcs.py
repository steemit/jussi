#! /usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: skip-file
import json
import os
import sys
import random

count = int(sys.argv[1])
batch_size = int(sys.argv[2])
filename = os.path.join(os.path.dirname(__file__),
                        'count_%s_batch_%s.json' % (count, batch_size))


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


requests = [dict(id=i, jsonrpc='2.0', method='get_block', params=[random.randint(1, 20_000_000)])
            for i in range(count)]
if batch_size > 1:
    requests = list(chunkify(requests, batch_size))

with open(filename, 'w') as f:
    json.dump(requests, f)
