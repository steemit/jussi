wrk.method = "POST"
wrk.body   = '{"id":1,"jsonrpc":"2.0","method":"get_dynamic_global_properties"}'
wrk.headers["Content-Type"] = "application/json"
