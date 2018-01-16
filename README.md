# jussi

A reverse proxy that only speaks json-rpc 2.0. Upstream routing is done using json-rpc method "namespaces".

## Namespaces
A json-rpc method namespace is a json-rpc method prefix joined to the method name with a period, so a method in the "sbds" namespace begins with `sbds.` and will be forwarded to a sbds endpoint:
```
POST / HTTP/1.1
Content-Type: application/json

{
  "method": "sbds.count_operations",
  "params": {"operation":"account_creates"},
  "jsonrpc": "2.0",
  "id": 1
}
```

### Default Namespace
Any json-rpc method with no period in the method name is presumed to be in the "steemd" namespace and will be forwarded to a steemd endpoint:

```
POST / HTTP/1.1
Content-Type: application/json

{
  "method": "get_block",
  "params": [1],
  "jsonrpc": "2.0",
  "id": 1
}
```

## What jussi does
### At Startup
1. begin a task make a `steemd.get_dynamic_global_properties` every 3 seconds to know the current `last_irreversible_block`
1. create statsd stats queue to hold stats between flush intervals
1. begin a a task to flush the statsd stats queue every flush interval
1. open websocket and/or http connections to upstreams
1. initialize memory cache and open connections to redis cache
1. register route and error handler


### Request/Response Cycle

1. validate jsonrpc request
1. log call
1. start statsd downsteam request timers and increment request counters
1. canonicalize both forms of steemd jsonrpc api calls for cache key generation
1. generate cache key
1. if a single jsonrpc request:
   1. check in memory cache, if miss
   1. make a redis `get` call
1. if a batch call:
   1. check in memory cache for all keys
   1. for any misses:
     1. make a redis `mget` request for any keys not found in memory cache
1. if all data loaded from cache:
   1. merge cached data with requests to form responses
   1. send response
1. if any jsonrpc call results arent in cache:
  1. determine which upstream url and protocol (websockets or http) to use to fetch them
1. start upsteam request timers
1. fetch missing jsonrpc calls, retry fetching if there are errors
1. end upstream response timers and increment statsd counters
1. log response
1. decide if response is a valid jsonrpc response and that it is not a jsonrpc error response
1. if not an jsonrpc error response, determine the cache ttl for that jsonrpc namespace.method
1. for some calls, verify the the response is a consensus response or not, and modify cache ttl for irreversible block responses
1. cache response in redis cache
1. cache response in memory
1. return single jsonrpc response or assembled jsonrpc responses for batch requests
