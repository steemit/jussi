# 配置文件重构和优化计划

## 问题分析

### 1. 配置优先级和环境变量对齐
- **当前问题**：
  - Redis 配置不匹配：代码期望 `RedisURL`，配置文件使用 `redis.address`
  - 环境变量和配置文件字段名不一致
  - Viper 加载顺序：默认值 < 配置文件 < 环境变量（环境变量会覆盖配置文件）
  
- **解决方案**：
  - 统一配置结构，支持从配置文件读取 Redis 配置（address/password/db）并转换为 URL
  - 明确配置优先级策略：配置文件作为基础，环境变量可以覆盖
  - 对齐所有配置项的环境变量命名

### 2. 上游配置简化
- **当前问题**：
  - `upstream.config_file` 字段未使用，造成困惑
  - `upstreams` 和 `upstreams_raw` 命名混淆
  - WebSocket 配置存在但功能暂不需要
  
- **解决方案**：
  - 移除 `upstream.config_file` 字段（当前配置直接从主配置文件读取）
  - 重命名 `upstreams_raw` 为 `upstreams`（更直观）
  - 将 WebSocket 配置标记为可选/禁用，默认不启用

### 3. TTL 细粒度支持
- **当前问题**：
  - 只支持 namespace/API 级别的 TTL
  - Legacy 版本支持方法级别和参数级别的 TTL（如 `steemd.database_api.get_block`, `steemd.database_api.get_state.params=['/trending']`）
  
- **解决方案**：
  - 恢复 Legacy 格式的 `upstreams` 数组配置
  - 支持 `urls`, `ttls`, `timeouts` 的细粒度配置
  - 实现 Trie 结构支持最长前缀匹配（namespace.api.method.params）
  - 保持向后兼容，支持简化的 `upstreams_raw` 格式作为快速配置选项

### 4. Prometheus 端口配置澄清
- **当前问题**：
  - `port` 和 `metrics_port` 两个端口配置，用途不明确
  - `separate_port` 标志存在但未实现独立端口服务器
  
- **解决方案**：
  - 澄清端口用途：`port` 用于与主服务同一端口（`/metrics` 路径），`metrics_port` 用于独立端口
  - 实现 `separate_port=true` 时的独立 HTTP 服务器
  - 或简化配置：移除 `separate_port`，统一使用主服务端口

## 实施步骤

### 阶段 1: 配置结构统一

**文件**: `internal/config/config.go`

1. **修复 Redis 配置结构**
   - 添加 `Redis` 嵌套结构体（address, password, db, pool_size 等）
   - 添加方法将 Redis 配置转换为 URL 格式
   - 保持 `RedisURL` 字段用于环境变量直接注入

2. **统一配置加载逻辑**
   - 确保所有配置项都有对应的环境变量支持
   - 添加配置验证，检查必需字段

### 阶段 2: 上游配置重构

**文件**: `internal/config/config.go`, `internal/upstream/router.go`, `DEV_config.json`

1. **移除无用字段**
   - 删除 `UpstreamConfig.ConfigFile` 字段
   - 更新配置文档说明

2. **重命名和简化**
   - 将 `upstreams_raw` 重命名为 `upstreams`
   - 更新 `UpstreamRawConfig` 结构体名称

3. **WebSocket 配置处理**
   - 添加 `websocket_enabled` 标志，默认 `false`
   - 当 `websocket_enabled=false` 时跳过 WebSocket 池初始化

### 阶段 3: TTL 细粒度支持

**文件**: `internal/config/config.go`, `internal/upstream/router.go`, `internal/cache/ttl.go`

1. **恢复 Legacy 格式支持**
   - 添加 `UpstreamDefinition` 结构体（已在代码中定义但未使用）
   - 支持 `upstreams` 数组格式，包含：
     - `name`: 命名空间名称
     - `urls`: `[["namespace", "url"]]` 格式
     - `ttls`: `[["namespace.api.method", ttl]]` 格式，支持参数级别
     - `timeouts`: `[["namespace.api.method", timeout]]` 格式

2. **实现细粒度 TTL 匹配**
   - 扩展 Trie 结构支持方法级别和参数级别匹配
   - 实现最长前缀匹配算法（支持 `steemd.database_api.get_block` 和 `steemd.database_api.get_state.params=['/trending']`）
   - 更新 `router.GetUpstream()` 方法返回正确的 TTL 和 Timeout

3. **保持向后兼容**
   - 支持简化的 `upstreams` 对象格式（当前格式）作为快速配置
   - 优先使用 Legacy 格式（如果存在），否则回退到简化格式

### 阶段 4: Prometheus 端口配置

**文件**: `internal/app/app.go`, `internal/config/config.go`, `DEV_config.json`

1. **实现独立端口服务器**（如果保留该功能）
   - 当 `separate_port=true` 时，启动独立的 HTTP 服务器监听 `metrics_port`
   - 或简化配置：移除 `separate_port` 和 `metrics_port`，统一使用主服务端口

2. **配置文档更新**
   - 明确说明端口配置的用途
   - 更新示例配置

### 阶段 5: 配置迁移和文档

**文件**: `DEV_config.json`, `docs/CONFIGURATION.md`

1. **更新示例配置**
   - 迁移到新的配置格式
   - 提供 Legacy 格式和简化格式的示例

2. **更新文档**
   - 说明配置优先级（环境变量覆盖配置文件）
   - 说明 TTL 配置的粒度级别
   - 说明 Prometheus 端口配置

## 关键文件修改

- `internal/config/config.go`: 统一配置结构，修复 Redis 配置，支持 Legacy upstreams 格式
- `internal/upstream/router.go`: 实现细粒度 TTL 匹配，支持参数级别配置
- `internal/app/app.go`: 处理 WebSocket 可选配置，实现 Prometheus 独立端口（如需要）
- `DEV_config.json`: 更新为新的配置格式
- `docs/CONFIGURATION.md`: 更新配置文档

## 决策点

1. **Prometheus 独立端口**：是否需要保留？建议简化，统一使用主服务端口
2. **配置格式兼容性**：是否同时支持 Legacy 格式和简化格式？建议都支持，优先 Legacy
3. **WebSocket 功能**：完全移除还是保留但默认禁用？建议保留但默认禁用

## 实施任务清单

1. ✅ 统一 Redis 配置结构：支持从配置文件（address/password/db）和环境变量（RedisURL）两种方式，内部转换为统一格式
2. ✅ 对齐所有配置项的环境变量命名，确保配置文件字段和环境变量一一对应
3. ✅ 移除 upstream.config_file 字段，简化上游配置结构
4. ✅ 将 upstreams_raw 重命名为 upstreams，更新相关代码和配置
5. ✅ 添加 websocket_enabled 标志，默认 false，禁用 WebSocket 功能
6. ✅ 恢复 Legacy 格式的 upstreams 数组配置支持（包含 urls/ttls/timeouts）
7. ✅ 实现细粒度 TTL 匹配：支持方法级别和参数级别（如 steemd.database_api.get_block, steemd.database_api.get_state.params=[...]）
8. ✅ 澄清 Prometheus 端口配置：实现 separate_port 功能或简化配置移除该选项
9. ✅ 更新 DEV_config.json 为新的配置格式，提供 Legacy 格式示例
10. ✅ 更新 CONFIGURATION.md 文档，说明配置优先级、TTL 粒度、端口配置等

## 配置优先级说明

Viper 的配置加载顺序：
1. **默认值** (setDefaults) - 最低优先级
2. **配置文件** (JSON/YAML) - 中等优先级
3. **环境变量** (JUSSI_* 前缀) - **最高优先级，会覆盖配置文件**

这意味着：
- 配置文件提供基础配置
- 环境变量可以覆盖配置文件中的任何值
- 适合生产环境：通过环境变量注入敏感信息（如 Redis 密码）而不修改配置文件

## 参考

- Legacy 配置文件：`legacy/DEV_config.json`
- 当前配置文件：`DEV_config.json`
- 配置加载代码：`internal/config/config.go`
- 上游路由代码：`internal/upstream/router.go`

