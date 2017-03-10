# jussi

A simple reverse proxy that only speaks json-rpc 2.0. Upstream routing is done using json-rpc method "namespaces".

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

At the moment, a method name which explicitly uses the `steemd.` namespace will fail, so don't do this:
```
POST / HTTP/1.1
Content-Type: application/json

{
  "method": "steemd.get_block", 
  "params": [1], 
  "jsonrpc": "2.0", 
  "id": 1
}
```
