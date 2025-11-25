# jussi

A reverse proxy that only speaks json-rpc 2.0. Upstream routing is done using json-rpc method "namespaces".

## Building & Running

The easiest way to get up and running with jussi is by running it in a docker container.

1) Copy the example `DEV_config.json` to a local directory and make any necessary edits.
2) Run this docker command (replace `/path/to/config.json` with the path to your config file): 
```
docker run -it --env JUSSI_UPSTREAM_CONFIG_FILE=/app/config.json -v /path/to/config.json:/app/config.json -p 8080:8080 steemit/jussi:latest
```

You can build jussi using docker which will run it's full test suite with `docker build -t="myname/jussi:latest" .`

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

### Configuring and routing additional namespaces

Jussi comes with an example config file, `DEV_config.json`. You can add additional namespaces for routing different calls to different hosts.

Additional namespaces can be added to the upstreams array:

```
{
  "name": "foo",
  "urls": [["foo", "https://foo.host.name"]],
  "ttls": [["foo", 3]],
  "timeouts": [["foo", 5]]
}
```

Once the above upstream has been added to your local config and jussi, the following curl would work:
```
curl -s --data '{"jsonrpc":"2.0", "method":"foo.bar", "params":["baz"], "id":1}' http://localhost:9000
```

### Caching and Time to Live

For each namespace, you can configure a time to live (ttl). Jussi will cache any request for this namespace for however long you specify. Setting to `0` won't expire, `-1` won't be cached, and `-2` will be cached without expiration only if it is still irreversible on chain. Any positive number is te number of seconds to cache the request.

### Multiple routes

Each urls key can have multiple endpoints for each namespace. For example:

```
{
  "urls":[
    ["appbase", "https://api.steemitdev.com"]
  ]
}
```

… could be expaned to list specific additional methods in that namespace:

```
{
  "urls":[
    ["appbase","https://api.steemitdev.com"],
    ["appbase.condenser_api.get_account_history","https://api-for-account-history.steemitdev.com"],
    ["appbase.condenser_api.get_ops_in_block","https://api-for-get-ops-in-block.steemitdev.com"]
  ]
}
```

This makes it possible to forward specific calls to specific clusters of nodes.

### Redis

While it isn't required to function, for production scenarios we recommend using a separate redis database for jussi. You can specify your redis host by passing in an environment variable. You can learn more about redis here: https://redis.io/

### Environment variables

Certain features of jussi can be configured using environment variables. If you are running jussi in a docker container, you can pass them in using `--env ENVIRONMENT_VARIABLE=value`

`JUSSI_UPSTREAM_CONFIG_FILE` - Specifies the location of your config file
`JUSSI_REDIS_URL` - In the format of: `redis://host:port`
`JUSSI_JSONRPC_BATCH_SIZE_LIMIT` - The number of batch requests to allow
`JUSSI_SERVER_PORT` - The port to run on, default is `9000`
`JUSSI_STATSD_URL` - In the format of: `statsd://host:port`
`JUSSI_TEST_UPSTREAM_URLS` - This stops jussi from testing upstream URLs at startup. When pointing jussi to locally running test services, you may need to set this to `FALSE`.
`JUSSI_WEBSOCKET_POOL_MAXSIZE` - If connecting to a service using websockets, you can set the max pool size
`LOG_LEVEL` - Everyone likes more logs. If you do too, set this to `INFO`. Otherwise, `WARNING` is ok as well.

## What jussi does
### At Startup
1. parse the upstream config and build the routing, caching, timeout data structures
1. open websocket and/or http connections to upstreams
1. initialize memory cache and open connections to redis cache
1. register route and error handlers


### Request/Response Cycle

1. validate jsonrpc request
1. convert individual jsonrpc requests into `JSONRPCRequest` objects, which add its pseudo-urn and upstream configuration
1. generate cache key (pseudo-urn for the moment)
1. if a single jsonrpc request:
   1. check in-memory cache, if miss
   1. make a redis `get` call
1. if a batch call:
   1. check in-memory cache for all keys
   1. for any misses:
     1. make a redis `mget` request for any keys not found in memory cache
1. if all data loaded from cache:
   1. merge cached data with requests to form response
   1. send response
1. if any jsonrpc call results aren't in cache:
  1. determine which upstream url and protocol (websockets or http) to use to fetch them
1. start upsteam request timers
1. fetch missing jsonrpc calls
1. end upstream response timers
1. decide if response is a valid jsonrpc response and that it is not a jsonrpc error response
1. if response is valid, and response is not a jsonrpc error response, determine the cache ttl for that jsonrpc namespace.method
1. for some calls, verify the the response is a consensus response or not, and modify cache ttl for irreversible block responses
1. return single jsonrpc response or assembled jsonrpc responses for batch requests
1. cache response in redis cache
1. cache response in memory

## Additional documentation

For more indepth documentation on jussi including examples, check out the section on it in the steem dev portal: https://developers.steem.io/services/#services-jussi
