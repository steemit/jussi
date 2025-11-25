# -*- coding: utf-8 -*-
from jussi.request.jsonrpc import JSONRPCRequest


def test_id_translation(steemd_jussi_request_and_dict):
    jussi_request, jsonrpc_request = steemd_jussi_request_and_dict
    urn = jussi_request.urn
    translated_request_dict = JSONRPCRequest.translate_to_appbase(jsonrpc_request, urn)
    assert translated_request_dict['id'] == jussi_request.id


def test_jsonrpc_translation(steemd_jussi_request_and_dict):
    jussi_request, jsonrpc_request = steemd_jussi_request_and_dict
    urn = jussi_request.urn
    translated_request_dict = JSONRPCRequest.translate_to_appbase(jsonrpc_request, urn)
    assert translated_request_dict['jsonrpc'] == jussi_request.jsonrpc


def test_jrpc_method_translation(steemd_jussi_request_and_dict):
    jussi_request, jsonrpc_request = steemd_jussi_request_and_dict
    urn = jussi_request.urn
    translated_request_dict = JSONRPCRequest.translate_to_appbase(jsonrpc_request, urn)
    assert translated_request_dict['method'] == 'call'


def test_params_api_translation(steemd_jussi_request_and_dict):
    jussi_request, jsonrpc_request = steemd_jussi_request_and_dict
    urn = jussi_request.urn
    translated_request_dict = JSONRPCRequest.translate_to_appbase(jsonrpc_request, urn)
    assert translated_request_dict['params'][0] == 'condenser_api'


def test_params_method_translation(steemd_jussi_request_and_dict):
    jussi_request, jsonrpc_request = steemd_jussi_request_and_dict
    urn = jussi_request.urn
    translated_request_dict = JSONRPCRequest.translate_to_appbase(jsonrpc_request, urn)
    assert translated_request_dict['params'][1] == jussi_request.urn.method


def test_params_param_translation(steemd_jussi_request_and_dict):
    jussi_request, jsonrpc_request = steemd_jussi_request_and_dict
    urn = jussi_request.urn
    translated_request_dict = JSONRPCRequest.translate_to_appbase(jsonrpc_request, urn)
    if jussi_request.urn.params is False:
        assert translated_request_dict['params'][2] == []
    else:
        assert translated_request_dict['params'][2] == jussi_request.urn.params
