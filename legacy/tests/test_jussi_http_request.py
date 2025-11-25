# -*- coding: utf-8 -*-
from urllib.parse import urlunparse

import pytest

from jussi.errors import InvalidRequest
from jussi.errors import ParseError
from jussi.request.http import _empty
from .conftest import make_request


def test_json_lazy_parsing():
    request = make_request(body=b'[{')
    assert request._parsed_json is _empty


@pytest.mark.parametrize('req', [
    make_request(method='GET', body=b'[{'),
    make_request(method='HEAD', body=b'[{'),
    make_request(method='OPTIONS', body=b'[{')])
def test_json_ignore_for_not_post(req):
    _ = req.jsonrpc
    assert req._parsed_json is _empty


@pytest.mark.parametrize('req', [
    make_request(method='GET', body=b'[{'),
    make_request(method='HEAD', body=b'[{'),
    make_request(method='OPTIONS', body=b'[{')])
def test_jsonrpc_ignore_for_not_post(req):
    _ = req.jsonrpc
    assert req._parsed_jsonrpc is _empty


def test_jsonrpc_lazy_parsing():
    request = make_request(body=b'[{')
    assert request._parsed_jsonrpc is _empty


def test_json_invalid():
    req = make_request(body=b'[')
    with pytest.raises(ParseError):
        _ = req.jsonrpc


def test_jsonrpc_blank_body():
    req = make_request(body=None)
    with pytest.raises(ParseError):
        _ = req.jsonrpc


def test_jsonrpc_empty_body():
    req = make_request(body=b'')
    with pytest.raises(ParseError):
        _ = req.jsonrpc


def test_jsonrpc_empty_dict():
    req = make_request(body=b'{}')
    with pytest.raises(InvalidRequest):
        _ = req.jsonrpc


def test_jsonrpc_empty_list():
    req = make_request(body=b'[]')
    with pytest.raises(InvalidRequest):
        _ = req.jsonrpc


def test_jsonrpc():
    pass


def test_ip():
    req = make_request()
    assert req.ip is None


def test_port():
    req = make_request()
    assert req.port is None


def test_socket():
    req = make_request()
    assert req.socket is None


def test_scheme():
    req = make_request()
    assert req.scheme == 'http'


def test_host():
    req = make_request()
    assert req.host == ''


def test_default_content_type():
    req = make_request()
    assert req.content_type == 'application/json'


def test__content_type():
    req = make_request(headers={'Content-Type': 'text/plain'})
    assert req.content_type == 'text/plain'


def test_match_info():
    # FIXME
    pass


def test_path():
    req = make_request()
    assert req.path == '/'


def test_query_string():
    req = make_request()
    assert req.query_string == ''


def test_url():
    req = make_request()
    assert req.url == urlunparse(('http', '', '/', None, '', None))


def test_jussi_request_id():
    req = make_request()
    assert req.jussi_request_id == '123'


def test_amzn_trace_id():
    req = make_request()
    assert req.amzn_trace_id == '123'
