# -*- coding: utf-8 -*-

from typing import Dict
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Union

import ujson


class JussiJSONRPCRequest(NamedTuple):
    id: Optional[Union[str, int, float, type(None)]]
    jsonrpc: str
    method: str
    params: Optional[Union[Dict, List]]
    urn: NamedTuple
    upstream: NamedTuple
    amzn_trace_id: str
    jussi_request_id: str
    batch_index: int

    # pylint: disable=no-member
    @classmethod
    def from_request(cls, sanic_request, batch_index: int, request: Dict[str, any]) -> NamedTuple:
        from .urn import URN
        from .upstream import Upstream

        assert isinstance(request, dict), 'request must be dict'
        upstreams = sanic_request.app.config.upstreams

        _id = request.get('id', None)
        jsonrpc = request['jsonrpc']
        method = request['method']
        params = request.get('params', None)
        urn = URN.from_request(request, namespaces=upstreams.namespaces)
        upstream = Upstream.from_urn(urn, upstreams=upstreams)

        return cls(_id,
                   jsonrpc,
                   method,
                   params,
                   urn,
                   upstream,
                   sanic_request.headers.get('x-amzn-trace-id'),
                   sanic_request['jussi_request_id'],
                   batch_index)

    # pylint: enable=no-member

    def to_dict(self):
        return {k: getattr(self, k, False) for k in
                {'id', 'jsonrpc', 'method', 'params'} if k is not None}

    def json(self):
        return ujson.dumps(self.to_dict(), ensure_ascii=False)

    def to_upstream_request(self, as_json=True):
        jrpc_dict = self.to_dict()
        jrpc_dict.update({'id': self.upstream_id})
        if as_json:
            return ujson.dumps(jrpc_dict, ensure_ascii=False)
        return jrpc_dict

    @property
    def upstream_headers(self):
        headers = {'x-jussi-request-id': self.jussi_request_id}
        if self.amzn_trace_id:
            headers['x-amzn-trace-id'] = self.amzn_trace_id
        return headers

    @property
    def upstream_id(self):
        return int(self.jussi_request_id) + self.batch_index

    def log_extra(self, extra=None):
        base_extra = {
            'x-amzn-trace-id': self.amzn_trace_id,
            'jussi_request_id': self.jussi_request_id,
            'urn': self.urn._asdict(),
            'batch_index': self.batch_index,
            'upstream': self.upstream._asdict(),
            'upstream_request_id': self.upstream_id,
        }

        if extra:
            base_extra.update(extra)
        return base_extra

    def __hash__(self):
        return hash(str(self.urn))
