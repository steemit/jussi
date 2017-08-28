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

URL_SETTINGS = (
    # steemd default
    ('steemd', 'steemd_default'),

    # sbds default
    ('sbds', 'sbds_default'), )

URLS = pygtrie.StringTrie(URL_SETTINGS, separator='.')


def deref_urls(url_mapping: dict,
               url_settings: Tuple[Tuple[str, str], ...]=URL_SETTINGS
               ) -> pygtrie.StringTrie:
    dereferenced_urls = []
    for prefix, url_ref in url_settings:
        dereferenced_urls.append((prefix, url_mapping[url_ref]))
    return pygtrie.StringTrie(dereferenced_urls, separator='.')
