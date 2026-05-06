# TTLS 和 TIMEOUTS 配置中的 Name（Prefix）定义分析

## 概述

在 Jussi 的配置文件中，`ttls` 和 `timeouts` 配置项使用 **prefix**（前缀字符串）来匹配请求的 URN（Uniform Resource Name）。这个 prefix 在配置中通常被称为 "name"，但实际上是一个用于前缀匹配的字符串。

## 配置格式

### 1. 数组格式（推荐）

```json
"ttls": [
  ["prefix_string", ttl_value],
  ["another_prefix", ttl_value]
],
"timeouts": [
  ["prefix_string", timeout_value],
  ["another_prefix", timeout_value]
]
```

### 2. 对象格式（备选）

```json
"ttls": [
  {
    "prefix": "prefix_string",
    "upstream_ttl": ttl_value
  }
],
"timeouts": [
  {
    "prefix": "prefix_string",
    "upstream_timeout": timeout_value
  }
]
```

## Prefix（Name）的层级结构

Prefix 遵循 URN 的层级结构，使用点号（`.`）分隔不同层级：

```
namespace.api.method.params=[...]
```

### 层级说明

1. **namespace** - 命名空间（如 `steemd`, `appbase`, `hivemind`）
2. **api** - API 名称（如 `database_api`, `condenser_api`, `network_broadcast_api`）
3. **method** - 方法名（如 `get_block`, `get_state`, `get_content`）
4. **params** - 参数（可选，格式为 `params=[...]` 或 `params={...}`）

## Prefix 匹配规则

系统使用 **最长前缀匹配**（Longest Prefix Match）算法：

- 使用 `pygtrie.StringTrie` 构建前缀树
- 通过 `longest_prefix()` 方法查找最匹配的前缀
- **更具体的前缀会覆盖更通用的前缀**

## 配置示例分析

### 示例 1：基础层级配置

```json
{
  "name": "steemd",
  "ttls": [
    ["steemd", 3],                          // 默认 TTL：3 秒
    ["steemd.login_api", -1],                // login_api 不缓存
    ["steemd.database_api", 3],              // database_api 默认 3 秒
    ["steemd.database_api.get_block", -2]    // get_block 特殊处理
  ],
  "timeouts": [
    ["steemd", 5],                          // 默认超时：5 秒
    ["steemd.network_broadcast_api", 0]      // network_broadcast_api 无超时
  ]
}
```

**匹配逻辑：**
- 请求 `steemd.database_api.get_block` → 匹配 `steemd.database_api.get_block`（TTL: -2）
- 请求 `steemd.database_api.get_content` → 匹配 `steemd.database_api`（TTL: 3）
- 请求 `steemd.login_api.xxx` → 匹配 `steemd.login_api`（TTL: -1）
- 请求 `steemd.other_api.xxx` → 匹配 `steemd`（TTL: 3）

### 示例 2：带参数的配置

```json
{
  "name": "steemd",
  "ttls": [
    ["steemd.database_api.get_state", 1],
    ["steemd.database_api.get_state.params=['/trending']", 30],
    ["steemd.database_api.get_state.params=['/hot']", 30],
    ["steemd.database_api.get_state.params=['/created']", 10]
  ]
}
```

**匹配逻辑：**
- 请求 `steemd.database_api.get_state.params=['/trending']` → 匹配具体参数配置（TTL: 30）
- 请求 `steemd.database_api.get_state.params=['/other']` → 匹配通用配置（TTL: 1）

### 示例 3：完整层级示例

```json
{
  "name": "namespace",
  "ttls": [
    ["namespace", 3],                                    // 层级 1：namespace
    ["namespace.method", 4],                             // 层级 2：namespace + method
    ["namespace.api.method", 5],                         // 层级 3：namespace + api + method
    ["namespace.api.method.params=[666]", 6]             // 层级 4：包含参数
  ]
}
```

## 代码实现

### 构建前缀树

在 `jussi/upstream.py` 中：

```python
def __build_trie(self, key):
    trie = pygtrie.StringTrie(separator='.')
    for item in it.chain.from_iterable(c[key] for c in self.config):
        if isinstance(item, list):
            prefix, value = item
        else:
            # 对象格式处理
            keys = list(item.keys())
            prefix_key = 'prefix'
            value_key = keys[keys.index(prefix_key) - 1]
            prefix = item[prefix_key]
            value = item[value_key]
        trie[prefix] = value
    return trie
```

### 匹配 TTL 和 Timeout

```python
@functools.lru_cache(8192)
def ttl(self, request_urn) -> int:
    _, ttl = self.__TTLS.longest_prefix(str(request_urn))
    return ttl

@functools.lru_cache(8192)
def timeout(self, request_urn) -> int:
    _, timeout = self.__TIMEOUTS.longest_prefix(str(request_urn))
    if timeout == 0:
        timeout = None
    return timeout
```

## URN 字符串格式

根据 `jussi/urn.py`，URN 的字符串表示格式为：

```python
def __str__(self) -> str:
    # 格式：namespace.api.method.params=...
    # 例如：steemd.database_api.get_block
    # 例如：steemd.database_api.get_state.params=['/trending']
    return '.'.join(
        p for p in (
            self.namespace,
            api,
            self.method,
            params) if p is not _empty)
```

## 特殊值说明

### TTL 特殊值
- `0`: 不过期（NO EXPIRE）
- `-1`: 不缓存（NO CACHE）
- `-2`: 如果区块不可逆则不过期（NO EXPIRE IF IRREVERSIBLE）
- 正数: 缓存时间（秒）

### Timeout 特殊值
- `0`: 无超时（NO TIMEOUT）
- 正数: 超时时间（秒）

## 最佳实践

1. **从通用到具体**：先定义通用前缀，再定义具体前缀
2. **使用数组格式**：更简洁易读
3. **合理使用参数匹配**：对于需要特殊处理的参数组合，使用完整的 params 匹配
4. **命名空间限制**：
   - 不能以 `_api` 结尾
   - 不能使用 `jsonrpc` 作为命名空间

## 总结

配置中的 "name"（实际是 prefix）是一个**分层的前缀字符串**，用于：
- 匹配请求的 URN
- 通过最长前缀匹配算法找到最合适的配置
- 支持从通用到具体的多层级配置

这种设计允许灵活地为不同的 API、方法和参数组合配置不同的 TTL 和超时时间。
