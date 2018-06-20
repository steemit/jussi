wrk.method = "POST"
wrk.headers["Content-Type"] = "application/json"

function request()
    body = '[{"id":1000,"jsonrpc":"2.0","method":"get_block","params":[' .. math.random(1,20000000) .. ']},{"id":2000,"jsonrpc":"2.0","method":"get_block","params":[' .. math.random(1,20000000) .. ']},{"id":3000,"jsonrpc":"2.0","method":"get_block","params":[' .. math.random(1,20000000) .. ']},{"id":4000,"jsonrpc":"2.0","method":"get_block","params":[' .. math.random(1,20000000) .. ']},{"id":5000,"jsonrpc":"2.0","method":"get_block","params":[' .. math.random(1,20000000) .. ']}]'
    return wrk.format(nil,nil,nil,body)
end
