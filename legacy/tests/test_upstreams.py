# -*- coding: utf-8 -*-
import pytest
import ujson


from jussi.errors import InvalidUpstreamHost
from jussi.errors import InvalidUpstreamURL
from jussi.upstream import _Upstreams

SIMPLE_CONFIG = {
    "limits": {},
    "upstreams":
    [
        {
            "name": "test",
            "translate_to_appbase": True,
            "urls": [
                ["test", 'http://test.com']
            ],
            "ttls": [
                ["test", 1]
            ],
            "timeouts": [
                ["test", 1]
            ]
        },
        {
            "name": "test2",
            "translate_to_appbase": False,
            "urls": [
                {
                    "prefix": "test2",
                    "upstream_url": "http://test2.com"
                }
            ],
            "ttls": [
                {
                    "prefix": "test2",
                    "upstream_ttl": 2
                }
            ],
            "timeouts": [
                {
                    "prefix": "test2",
                    "upstream_timeout": 2
                }
            ]
        }
    ]
}

VALID_HOSTNAME_CONFIG = {
    "limits": {},
    "upstreams": [
        {
            "name": "test",
            "translate_to_appbase": True,
            "urls": [
                ["test", 'http://google.com']
            ],
            "ttls": [
                ["test", 1]
            ],
            "timeouts": [
                ["test", 1]
            ]
        }
    ]}

INVALID_NAMESPACE1_CONFIG = {
    "limits": {},
    "upstreams": [
        {
            "name": "test_api",
            "urls": [
                ["test", 'http://google.com']
            ],
            "ttls": [
                ["test", 1]
            ],
            "timeouts": [
                ["test", 1]
            ]
        }
    ]}

INVALID_NAMESPACE2_CONFIG = {
    "limits": {},
    "upstreams": [
        {
            "name": "jsonrpc",
            "urls": [
                ["test", 'http://google.com']
            ],
            "ttls": [
                ["test", 1]
            ],
            "timeouts": [
                ["test", 1]
            ]
        }
    ]
}


def test_invalid_config():
    pass


def test_namespaces_config():
    upstreams = _Upstreams(SIMPLE_CONFIG, validate=False)
    assert upstreams.namespaces == frozenset(['test', 'test2'])


def test_namespaces_config_ends_with_api():
    with pytest.raises(AssertionError):
        upstreams = _Upstreams(INVALID_NAMESPACE1_CONFIG, validate=False)


def test_namespaces_config_is_jsonrpc():
    with pytest.raises(AssertionError):
        upstreams = _Upstreams(INVALID_NAMESPACE2_CONFIG, validate=False)


def test_urls_config():
    upstreams = _Upstreams(SIMPLE_CONFIG, validate=False)
    assert upstreams.urls == frozenset(['http://test.com', 'http://test2.com'])


def test_translate_to_appbase_config_true():
    from jussi.urn import URN
    urn = URN('test', 'api', 'method', False)
    upstreams = _Upstreams(SIMPLE_CONFIG, validate=False)
    assert upstreams.translate_to_appbase(urn) is True


def test_translate_to_appbase_config_false():
    from jussi.urn import URN
    urn = URN('test2', 'api', 'method', False)
    upstreams = _Upstreams(SIMPLE_CONFIG, validate=False)
    assert upstreams.translate_to_appbase(urn) is False


def test_url_pair():
    from jussi.urn import URN
    urn = URN('test', 'api', 'method', False)
    upstreams = _Upstreams(SIMPLE_CONFIG, validate=False)
    assert upstreams.url(urn) == 'http://test.com'


def test_url_object():
    from jussi.urn import URN
    urn = URN('test2', 'api', 'method', False)
    upstreams = _Upstreams(SIMPLE_CONFIG, validate=False)
    assert upstreams.url(urn) == 'http://test2.com'


def test_timeout_pair():
    from jussi.urn import URN
    urn = URN('test', 'api', 'method', False)
    upstreams = _Upstreams(SIMPLE_CONFIG, validate=False)
    assert upstreams.timeout(urn) == 1


def test_timeout_object():
    from jussi.urn import URN
    urn = URN('test2', 'api', 'method', False)
    upstreams = _Upstreams(SIMPLE_CONFIG, validate=False)
    assert upstreams.timeout(urn) == 2


def test_ttl_pair():
    from jussi.urn import URN
    urn = URN('test', 'api', 'method', False)
    upstreams = _Upstreams(SIMPLE_CONFIG, validate=False)
    assert upstreams.ttl(urn) == 1


def test_ttl_object():
    from jussi.urn import URN
    urn = URN('test2', 'api', 'method', False)
    upstreams = _Upstreams(SIMPLE_CONFIG, validate=False)
    assert upstreams.ttl(urn) == 2


def test_validate_urls_raises():
    with pytest.raises(InvalidUpstreamHost):
        upstreams = _Upstreams(SIMPLE_CONFIG)


def test_validate_urls():
    upstreams = _Upstreams(VALID_HOSTNAME_CONFIG, validate=True)
    assert isinstance(upstreams, _Upstreams)


def test_hash():
    upstreams = _Upstreams(SIMPLE_CONFIG, validate=False)
    upstreams_hash = hash(ujson.dumps(SIMPLE_CONFIG['upstreams']))
    assert hash(upstreams) == upstreams_hash


def test_hash_ineq():
    upstreams1 = _Upstreams(SIMPLE_CONFIG, validate=False)
    upstreams2 = _Upstreams(VALID_HOSTNAME_CONFIG, validate=False)
    assert hash(upstreams1) != hash(upstreams2)
