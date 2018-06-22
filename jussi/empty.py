# -*- coding: utf-8 -*-
class Singleton(type):
    _instance = None

    def __call__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instance


class Empty(metaclass=Singleton):
    def __bool__(self):
        return False

    def __repr__(self):
        return '<Empty>'

    def __str__(self):
        return '<Empty>'

    def __len__(self):
        return 0

    def __eq__(self, other):
        return isinstance(other, Empty)


_empty = Empty()
