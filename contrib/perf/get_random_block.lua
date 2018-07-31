wrk.method = "POST"
wrk.headers["Content-Type"] = "application/json"

function request()
   body   = '{"id":1,"jsonrpc":"2.0","method":"condenser_api.get_block","params":['.. math.random(1,20000000) .. ']}'
   return wrk.format(nil, nil, nil, body)
end
