# -*- coding: utf-8 -*-
from jussi.empty import Empty
from jussi.empty import _empty


def test_bool():
    assert bool(_empty) is False
    empty = Empty()
    assert bool(empty) is False


def test_len():
    assert len(_empty) == 0
    empty = Empty()
    assert len(empty) == 0


def test_eq():
    empty = Empty()
    assert empty == _empty


def test_neq_false():
    assert _empty != False
    empty = Empty()
    assert empty != False


def test_neq_none():
    assert _empty is not None
    empty = Empty()
    assert empty is not None


def test_neq_empty_list():
    assert _empty != []
    empty = Empty()
    assert empty != []


def test_neq_empty_dict():
    assert _empty != {}
    empty = Empty()
    assert empty != {}


def test_isinstance():
    empty1 = Empty()
    assert isinstance(empty1, Empty)
    assert isinstance(_empty, Empty)


def test_id():
    empty1 = Empty()
    assert empty1 is _empty
    assert id(empty1) == id(_empty)
