# -*- coding: utf-8 -*-
from time import perf_counter


class TimingsPy:

    def __init__(self, prefix: bytes):
        self.prefix = prefix
        self.timings = []
        self.names = ['created']

    def record(self, name: str):
        self.timings.append(perf_counter())
        self.names.append(name)

    def calculate_elapsed(self, timings):
        results = []
        for i in range(1, len(timings)):
            time1 = timings[i - 1]
            time2 = timings[i]
            elapsed = ((time2 - time1) * 1000)
            results.append(elapsed)
        return results

    def stats(self):
        elapsed = self.calculate_elapsed(self.timings)
        prefix = self.prefix.decode()
        return [f'{prefix}.{name}:{stat:0.6f}|ms' for name, stat in zip(self.names, elapsed)]
