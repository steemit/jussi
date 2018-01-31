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

        _id = request.get('id', False)
        jsonrpc = request['jsonrpc']
        method = request['method']
        params = request.get('params', False)
        urn = URN.from_request(request)
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
                ('id', 'jsonrpc', 'method', 'params') if getattr(self, k, False) is not False}

    def json(self):
        return ujson.dumps(self.to_dict(), ensure_ascii=False)

    def to_upstream_request(self, as_json=True, translate_to_appbase=False):
        if translate_to_appbase:
            jrpc_dict = self.translate_to_appbase()
        else:
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

    def translate_to_appbase(self):
        params = self.urn.params
        if params is False:
            params = []
        return {
            'id': self.id,
            'jsonrpc': self.jsonrpc,
            'method': 'call',
            'params': ['condenser_api', self.urn.method, params]
        }

    def log_extra(self, **kwargs):
        try:
            base_extra = {
                'x-amzn-trace-id': self.amzn_trace_id,
                'jussi_request_id': self.jussi_request_id,
                'jsonrpc_id': self.id,
                'batch_index': self.batch_index,
                'urn': self.urn._asdict(),
                'upstream': self.upstream._asdict(),
                'upstream_request_id': self.upstream_id,
            }
            base_extra.update(**kwargs)
            return base_extra

        except Exception:
            return None

    def __hash__(self):
        return hash(self.urn)
