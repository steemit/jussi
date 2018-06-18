wrk.method = "POST"
wrk.body   = '{"id":1,"jsonrpc":"2.0","method":"condenser_api.get_block","params":[1000]}'
wrk.headers["Content-Type"] = "application/json"
