# jussi

A simple reverse proxy that only speaks json-rpc 2.0. Upstream routing is done using json-rpc method "namespaces".

## Namespaces
A json-rpc method namespace is a json-rpc method prefix joined to the method name with a period, so the a method in the `sbds` namespace begins with "sbds.":
```
{
  "method": "sbds.count_operations", 
  "params": {"operation":"account_creates"}, 
  "jsonrpc": "2.0", 
  "id": 1
}
```

### Default Namespace
Any json-rpc method with no dot in the method name is presumed to be in the "steemd" namespace and is forwared to a steemd endpoint

```
{
  "method": "get_block", 
  "params": [1], 
  "jsonrpc": "2.0", 
  "id": 1
}
```

At the moment, a method name which explicitly uses the "steemd" namespace will fail, so don't do this:
```
{
  "method": "steemd.get_block", 
  "params": [1], 
  "jsonrpc": "2.0", 
  "id": 1
}
```
