blk_num = math.random(1, 20000000)
wrk.method = "POST"
wrk.body   = '{"id":1,"jsonrpc":"2.0","method":"condenser_api.get_block","params":[1000]}'
wrk.headers["Content-Type"] = "application/json"
