# -*- coding: utf-8 -*-
import time
from collections import defaultdict


class Timer(object):
    __slots__ = ('_start_time', '_end_time')

    def __init__(self, start_time=None, end_time=None):
        self._start_time = start_time or time.time()
        self._end_time = end_time

    def start(self, start_time=None):
        if start_time:
            self._start_time = start_time

    def restart(self):
        self._start_time = time.time()

    def end(self, end_time=None):
        self._end_time = self._end_time or end_time or time.time()

    @property
    def elapsed(self):
        end = self._end_time or time.time()
        return int((end - self._start_time) * 1000)

    @property
    def final(self):
        self.end()
        return self.elapsed

    def __str__(self):
        return str(self.elapsed)

    def __repr__(self):
        return 'Timer(start_time=%s end_time=%s elapsed=%s)' % (
            self._start_time, self._end_time, self.elapsed)

    def __enter__(self, start_time=None):
        if start_time:
            self.start(start_time=start_time)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.end()


def init_timers(start_time=None):
    return defaultdict(lambda: Timer(start_time=start_time))


def end_timers(timers, end_time=None):
    for timer in timers.values():
        if end_time:
            timer.end(end_time)
    return timers


def display_timers(timers, end_time=None):
    for name, timer in timers.items():
        if end_time:
            timer.end(end_time)
        print('%s %s' % (name, timer))


def log_timers(timers, log_func):
    for name, timer in timers.items():
        log_func('%s %s' % (name, timer))
