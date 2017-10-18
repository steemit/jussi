# -*- coding: utf-8 -*-
"""
Upstream TIMEOUT Settings
---------------
- Each tuple in the TIMEOUT_SETTING's list of tuples is a setting
- Each setting is a two-tuple of `prefix` and `url_reference`, eg, ('steemd.database_api.get_block', 'steemd_default')
- Settings are stored in a trie structure, the longest matching prefix for a method is it's setting

"""
import logging
from typing import Optional

import pygtrie

from ..typedefs import SingleJsonRpcRequest
from .urn import urn as get_urn

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 2  # seconds
NO_TIMEOUT = None  # disable timeout

TIMEOUT_SETTINGS = (
    # global default
    ('', DEFAULT_TIMEOUT),

    # sbds default
    ('hivemind', DEFAULT_TIMEOUT),

    # sbds default
    ('overseer', DEFAULT_TIMEOUT),

    # sbds default
    ('sbds', DEFAULT_TIMEOUT),

    # steemd default
    ('steemd', DEFAULT_TIMEOUT),

    # yo default
    ('yo', DEFAULT_TIMEOUT),

    # don't timeout steemd transaction/block broadcasts
    ('steemd.network_broadcast_api', NO_TIMEOUT)

)

TIMEOUTS = pygtrie.StringTrie(TIMEOUT_SETTINGS, separator='.')


def timeout_from_urn(urn: str) -> Optional[int]:
    _, timeout = TIMEOUTS.longest_prefix(urn)
    logger.debug(f'ttl from urn:{urn} ttl:{timeout}')
    return timeout


def timeout_from_request(request: SingleJsonRpcRequest) -> Optional[int]:
    urn = get_urn(request)
    return timeout_from_urn(urn)
