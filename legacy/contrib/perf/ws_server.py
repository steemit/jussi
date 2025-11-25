# -*- coding: utf-8 -*-
from sanic import Sanic
from sanic.response import json
import ujson
app = Sanic()

resp = {
    "id": 1,
    "jsonrpc": "2.0",
    "result": {
        "block_id": "000003e8b922f4906a45af8e99d86b3511acd7a5",
        "extensions": [],
        "previous": "000003e7c4fd3221cf407efcf7c1730e2ca54b05",
        "signing_key": "STM8GC13uCZbP44HzMLV6zPZGwVQ8Nt4Kji8PapsPiNq1BK153XTX",
        "timestamp": "2016-03-24T16:55:30",
        "transaction_ids": [],
        "transaction_merkle_root": "0000000000000000000000000000000000000000",
        "transactions": [],
        "witness": "initminer",
        "witness_signature": "207f15578cac20ac0e8af1ebb8f463106b8849577e21cca9fc60da146d1d95df88072dedc6ffb7f7f44a9185bbf9bf8139a5b4285c9f423843720296a44d428856"
    }
}
resp_json = ujson.dumps(resp).encode('utf8')


@app.route("/hello")
async def test(request):
    return json({"hello": "world"})


@app.websocket('/')
async def feed(request, ws):
    while True:
        await ws.send(resp_json)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
