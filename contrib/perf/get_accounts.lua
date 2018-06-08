wrk.method = "POST"
wrk.body   = '{"id":1,"jsonrpc":"2.0","method":"condenser_api.get_accounts","params":[["steemit"]]}'
wrk.headers["Content-Type"] = "application/json"
