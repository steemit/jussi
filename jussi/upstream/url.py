# -*- coding: utf-8 -*-
"""
Upstream URL Settings
---------------
- Each tuple in the METHOD_SETTING's list of tuples is a setting
- Each setting is a two-tuple of `prefix` and `url_reference`, eg, ('steemd.database_api.get_block', 'steemd_default')
- Settings are stored in a trie structure, the longest matching prefix for a method is it's setting

"""
from typing import Tuple

import pygtrie

from ..typedefs import SingleJsonRpcRequest
from .urn import urn

URL_SETTINGS = (
    # hivemind default
    ('hivemind', 'hivemind_default'),

    # jussi default
    ('jussi', 'jussi_default'),

    # overseer default
    ('overseer', 'overseer_default'),

    # sbds default
    ('sbds', 'sbds_default'),

    # steemd default
    ('steemd', 'steemd_default'),

    # yo default
    ('yo', 'yo_default')
)

URLS = pygtrie.StringTrie(URL_SETTINGS, separator='.')

NAMESPACES = frozenset(i[0] for i in URL_SETTINGS)


def deref_urls(url_mapping: dict,
               url_settings: Tuple[Tuple[str, str], ...]=URL_SETTINGS
               ) -> pygtrie.StringTrie:
    dereferenced_urls = []
    for prefix, url_ref in url_settings:
        dereferenced_urls.append((prefix, url_mapping[url_ref]))
    return pygtrie.StringTrie(dereferenced_urls, separator='.')


def url_from_urn(upstream_urls: pygtrie.StringTrie,
                 urn: str=None) -> str:
    _, url = upstream_urls.longest_prefix(urn)
    return url


def url_from_jsonrpc_request(upstream_urls: pygtrie.StringTrie,
                             jsonrpc_request: SingleJsonRpcRequest) -> str:
    return url_from_urn(upstream_urls, urn(jsonrpc_request))
