# -*- coding: utf-8 -*-
from typing import Dict
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Union

import ujson

from .upstream import Upstream
from .urn import URN


class JussiJSONRPCRequest(NamedTuple):
    id: Optional[Union[str, int, float, type(None)]]
    jsonrpc: str
    method: str
    params: Optional[Union[Dict, List]]
    urn: URN
    upstream: Upstream

    # pylint: disable=no-member
    @classmethod
    def from_request(cls, request: Dict[str, any]) -> NamedTuple:
        if not isinstance(request, dict):
            raise ValueError('request must be dict')

        _id = request.get('id', False)
        jsonrpc = request['jsonrpc']
        method = request['method']
        params = request.get('params', False)
        urn = URN.from_request(request)
        upstream = Upstream.from_urn(urn)

        return cls(_id, jsonrpc, method, params, urn, upstream)
    # pylint: enable=no-member

    def to_dict(self):
        return {k: getattr(self, k, False) for k in
                {'id', 'jsonrpc', 'method', 'params'} if k is not False}

    def json(self):
        return ujson.dumps(self.to_dict(), ensure_ascii=False)

    def to_upstream_request(self, upstream_id, as_json=True):
        jrpc_dict = self.to_dict()
        jrpc_dict.update({'id': upstream_id})
        if as_json:
            return ujson.dumps(jrpc_dict, ensure_ascii=False)
        return jrpc_dict

    def __hash__(self):
        return hash(str(self.urn))
