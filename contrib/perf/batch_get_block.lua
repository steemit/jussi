wrk.method = "POST"
wrk.body   = '[{"id":1000,"jsonrpc":"2.0","method":"get_block","params":[1000]},{"id":2000,"jsonrpc":"2.0","method":"get_block","params":[2000]},{"id":3000,"jsonrpc":"2.0","method":"get_block","params":[3000]},{"id":4000,"jsonrpc":"2.0","method":"get_block","params":[4000]},{"id":5000,"jsonrpc":"2.0","method":"get_block","params":[5000]}]'
wrk.headers["Content-Type"] = "application/json"
