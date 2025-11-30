# Metrics Documentation

## Overview

Jussi exposes metrics in Prometheus format for monitoring and observability. This document describes both Prometheus server metrics (for monitoring Prometheus itself) and Jussi application metrics (for monitoring the Jussi service).

## Accessing Metrics

Jussi metrics are exposed on the same HTTP server as the main application:

- **Endpoint**: `http://<server>:<port>/metrics`
- **Default**: `http://localhost:8080/metrics`
- **Format**: Prometheus text format

The metrics endpoint can be secured using the `prometheus.localhost_only` configuration option or IP whitelisting.

## Beginner's Guide to Metrics

### What Are Metrics?

Think of metrics as **health checkups for your application**. Just like a doctor measures your heart rate, blood pressure, and temperature to understand your health, metrics measure various aspects of your application's performance and health.

**Simple Analogy**: Imagine you're running a restaurant:
- **Request metrics** = How many customers you serve per hour
- **Error metrics** = How many orders you mess up
- **Latency metrics** = How long customers wait for their food
- **Cache metrics** = How often you can serve food from the pre-made stock (cache) vs. cooking fresh (upstream)

### Types of Metrics

Before diving into specific metrics, let's understand the three main types:

#### 1. Counter (计数器)
- **What it is**: A number that only goes up (never down)
- **Real-world example**: Like an odometer in a car - it only increases
- **Use case**: Count total requests, total errors, total bytes transferred
- **Example**: `jussi_requests_total = 1,234,567` (this is the total since the server started)

#### 2. Gauge (仪表盘)
- **What it is**: A number that can go up or down
- **Real-world example**: Like a thermometer - the temperature can rise or fall
- **Use case**: Current memory usage, current number of connections, current cache size
- **Example**: `jussi_cache_hit_ratio = 0.85` (85% cache hit rate, can change over time)

#### 3. Histogram (直方图)
- **What it is**: Tracks how many times something happened within different time ranges
- **Real-world example**: Like tracking how many customers waited 0-1 minute, 1-2 minutes, 2-5 minutes, etc.
- **Use case**: Request durations, response sizes
- **Example**: Shows that 100 requests took < 0.1s, 50 took 0.1-0.5s, 10 took > 0.5s

### Understanding Labels

Labels are like **tags** that help you filter and group metrics. Think of them as categories:

- `namespace="steemd"` - Which API namespace (like different departments)
- `method="get_block"` - Which specific API method (like specific actions)
- `status="200"` - HTTP status code (200 = success, 500 = error)

Example: `jussi_requests_total{namespace="steemd", method="get_block", status="200"}` means:
"Total requests for the steemd namespace, get_block method, that returned status 200"

### Understanding Percentiles (p50, p95, p99)

When you see metrics like "p99 latency", here's what it means:

**Simple explanation:**
If you measure 100 requests:
- **p50 (median)**: The 50th slowest request (half are faster, half are slower)
- **p95**: The 95th slowest request (95% are faster)
- **p99**: The 99th slowest request (99% are faster, only 1% are slower)

**Why p99 matters:**
- p50 might be 100ms (most requests are fast)
- p99 might be 5 seconds (but 1% are very slow)
- p99 catches the "worst case" that affects some users

**Real-world example:**
- p50: 50ms (half of users wait 50ms or less)
- p95: 200ms (95% of users wait 200ms or less)
- p99: 2 seconds (99% wait 2s or less, but 1% wait longer)

## Prometheus Server Metrics

These metrics monitor the Prometheus server itself and are available at `http://prometheus:9090/metrics`. They help track Prometheus health and performance.

### Data Collection Metrics

#### Samples Appended (`prometheus_tsdb_head_samples_appended_total`)
- **Type**: Counter
- **Description**: Total number of samples appended to the time-series database head
- **Normal Range**: Varies based on scrape frequency and number of targets
- **Alert**: Sudden drops may indicate scraping failures

**What it means in simple terms:**
- Prometheus collects data points (called "samples") from your applications
- This metric counts how many data points Prometheus has successfully saved
- Think of it as: "How many data points have been written to the database?"

**Why it matters:**
- If this number stops increasing, Prometheus might not be collecting data anymore
- It should steadily increase over time (like a counter)
- A sudden drop = something broke

**Real-world analogy:**
Like counting how many receipts a cash register has printed. If the number stops growing, the register might be broken.

**What to watch for:**
- ✅ Good: Number steadily increasing
- ⚠️ Warning: Number stops increasing (Prometheus might not be scraping)
- ❌ Bad: Number suddenly drops to zero

#### Scrape Duration (`prometheus_target_interval_length_seconds`)
- **Type**: Histogram
- **Description**: Actual time between scrapes for each target
- **Labels**: `job`, `instance`
- **Normal Range**: Should be close to configured `scrape_interval` (e.g., 10s for jussi, 15s for prometheus)
- **Alert**: High values indicate slow scraping or network issues

**What it means in simple terms:**
- Prometheus "scrapes" (collects) metrics from your applications at regular intervals
- This metric measures how long each scrape actually takes
- Think of it as: "How long does it take Prometheus to collect data from each service?"

**Why it matters:**
- If scraping takes too long, Prometheus might fall behind
- Should be much shorter than the scrape interval (if you scrape every 10s, scraping should take < 1s)
- High values = network problems or slow applications

**Real-world analogy:**
Like timing how long it takes to check each store's inventory. If checking one store takes 30 minutes but you need to check every 10 minutes, you'll fall behind.

**What to watch for:**
- ✅ Good: Scrape duration < 10% of scrape interval (e.g., < 1s for 10s interval)
- ⚠️ Warning: Scrape duration > 50% of scrape interval
- ❌ Bad: Scrape duration > scrape interval (can't keep up)

### Memory Metrics

#### Memory Profile (`prometheus_process_resident_memory_bytes`, `prometheus_process_virtual_memory_bytes`)
- **Type**: Gauge
- **Description**: 
  - `process_resident_memory_bytes`: Physical memory (RSS) used by Prometheus
  - `process_virtual_memory_bytes`: Virtual memory used by Prometheus
- **Normal Range**: 
  - Resident memory: Typically 200-500 MiB for small deployments
  - Virtual memory: Typically 500 MiB - 1 GiB
- **Alert**: Rapid growth may indicate memory leaks or insufficient retention settings

**What it means in simple terms:**
- Shows how much RAM (memory) Prometheus is using
- **Resident memory** = actual physical RAM being used
- **Virtual memory** = total memory space (including swap/disk)
- Think of it as: "How much memory is Prometheus using right now?"

**Why it matters:**
- If memory keeps growing, Prometheus might run out of RAM and crash
- Memory should be relatively stable (not constantly growing)
- High memory = might need to reduce data retention or scrape less frequently

**Real-world analogy:**
Like checking how much space your phone is using. If it keeps growing, you'll run out of storage.

**What to watch for:**
- ✅ Good: Memory usage is stable or grows slowly
- ⚠️ Warning: Memory usage growing rapidly
- ❌ Bad: Memory usage approaching system limits (might crash)

### Storage Metrics

#### Active Appenders (`prometheus_tsdb_head_active_appenders`)
- **Type**: Gauge
- **Description**: Number of active appenders writing to the head block
- **Normal Range**: Should match the number of active scrape targets
- **Alert**: Zero values may indicate scraping issues

**What it means in simple terms:**
- Prometheus writes data to storage using "appenders" (writers)
- This counts how many appenders are currently active (writing data)
- Think of it as: "How many writers are currently saving data?"

**Why it matters:**
- Should match the number of services you're monitoring
- If it's zero, nothing is being written (big problem!)
- If it's too high, you might have too many monitoring targets

**Real-world analogy:**
Like counting how many cashiers are currently serving customers. If it's zero, the store is closed!

**What to watch for:**
- ✅ Good: Matches number of active scrape targets
- ⚠️ Warning: Lower than expected (some targets might be down)
- ❌ Bad: Zero (nothing is being written to storage)

#### Blocks Loaded (`prometheus_tsdb_blocks_loaded`)
- **Type**: Gauge
- **Description**: Number of blocks currently loaded in memory
- **Normal Range**: Typically 0 for new installations, increases over time
- **Alert**: Very high values may indicate storage issues

**What it means in simple terms:**
- Prometheus stores data in "blocks" (chunks of time-series data)
- This counts how many blocks are currently loaded in memory
- Think of it as: "How many data files are open in memory?"

**Why it matters:**
- New installations start at 0 (no historical data yet)
- Grows over time as Prometheus stores more data
- Too many blocks = high memory usage

**Real-world analogy:**
Like counting how many books you have open on your desk. More books = more memory used, but also more information available.

**What to watch for:**
- ✅ Good: Gradually increases over time (normal)
- ⚠️ Warning: Very high number (might indicate storage issues)
- ❌ Bad: Sudden drop to zero (data loss!)

#### Head Chunks (`prometheus_tsdb_head_chunks`)
- **Type**: Gauge
- **Description**: Number of chunks in the head block
- **Normal Range**: Grows with time-series data, typically 1K-5K for small deployments
- **Alert**: Rapid growth may indicate high cardinality issues

**What it means in simple terms:**
- The "head" is where Prometheus stores the most recent data
- Data is organized into "chunks" (small pieces)
- This counts how many chunks are in the head
- Think of it as: "How many pieces of recent data are stored?"

**Why it matters:**
- Grows as you collect more metrics
- Rapid growth = you might be collecting too many unique metrics (high cardinality)
- High cardinality = high memory usage

**Real-world analogy:**
Like counting how many different types of items you're tracking in inventory. Too many unique items = harder to manage.

**What to watch for:**
- ✅ Good: Steady, gradual growth
- ⚠️ Warning: Rapid growth (check for high cardinality metrics)
- ❌ Bad: Extremely high numbers (memory issues)

#### WAL Corruptions (`prometheus_tsdb_wal_corruptions_total`)
- **Type**: Counter
- **Description**: Total number of WAL (Write-Ahead Log) corruptions detected
- **Normal Range**: Should always be 0
- **Alert**: Any non-zero value indicates data corruption and requires investigation

**What it means in simple terms:**
- WAL = Write-Ahead Log (a safety mechanism)
- Prometheus writes data to a log first, then to storage
- This counts how many times the log was corrupted (damaged)
- Think of it as: "How many times did the safety log get corrupted?"

**Why it matters:**
- Should ALWAYS be 0
- Any corruption = potential data loss
- Requires immediate investigation

**Real-world analogy:**
Like checking if your backup drive is corrupted. If it is, you might lose data!

**What to watch for:**
- ✅ Good: Always 0
- ❌ Bad: Any value > 0 (investigate immediately!)

### Garbage Collection Metrics

#### Head Block GC Activity (`prometheus_tsdb_head_gc_duration_seconds_count`)
- **Type**: Counter
- **Description**: Number of garbage collection operations performed on the head block
- **Normal Range**: Periodic GC is normal, frequency depends on data ingestion rate
- **Alert**: Excessive GC may indicate memory pressure

**What it means in simple terms:**
- GC = Garbage Collection (cleaning up unused memory)
- This counts how many times Prometheus cleaned up memory
- Think of it as: "How many times did Prometheus clean up its memory?"

**Why it matters:**
- Some GC is normal (like cleaning your room periodically)
- Too much GC = memory pressure (running out of memory)
- GC takes time, so excessive GC slows down Prometheus

**Real-world analogy:**
Like counting how many times you had to clean your desk. Occasional cleaning is normal, but constant cleaning means you're running out of space.

**What to watch for:**
- ✅ Good: Periodic GC (normal)
- ⚠️ Warning: Frequent GC (memory pressure)
- ❌ Bad: Constant GC (severe memory issues)

### Compaction Metrics

#### Compaction Activity (`prometheus_tsdb_compactions_total`)
- **Type**: Counter
- **Labels**: `type` (level, vertical)
- **Description**: Number of compaction operations performed
- **Normal Range**: Periodic compactions are normal for time-series databases
- **Alert**: Failed compactions indicate storage issues

**What it means in simple terms:**
- Compaction = combining small data files into larger ones (optimization)
- This counts how many times Prometheus optimized its storage
- Think of it as: "How many times did Prometheus reorganize its data files?"

**Why it matters:**
- Periodic compaction is normal and good (keeps storage efficient)
- Failed compactions = storage problems
- Compaction improves query performance

**Real-world analogy:**
Like defragmenting your hard drive. It reorganizes files to make them faster to access.

**What to watch for:**
- ✅ Good: Periodic successful compactions
- ⚠️ Warning: Failed compactions
- ❌ Bad: Many failed compactions (storage issues)

### Configuration Metrics

#### Reload Count (`prometheus_config_last_reload_successful`, `prometheus_config_last_reload_success_timestamp_seconds`)
- **Type**: Gauge
- **Description**: Status and timestamp of last configuration reload
- **Normal Range**: Should be 1 (successful) with recent timestamp
- **Alert**: Zero values or old timestamps indicate reload failures

**What it means in simple terms:**
- When you change Prometheus configuration, it "reloads" the config
- This shows if the last reload was successful (1 = success, 0 = failed)
- Think of it as: "Did the last configuration change work?"

**Why it matters:**
- If reload fails, your new configuration isn't active
- Old timestamp = config hasn't been reloaded recently
- Failed reloads = configuration errors

**Real-world analogy:**
Like checking if your new settings were saved successfully. If not, you're still using old settings.

**What to watch for:**
- ✅ Good: Value = 1 with recent timestamp
- ⚠️ Warning: Value = 0 (reload failed)
- ❌ Bad: Old timestamp (config might be outdated)

### Query Performance Metrics

#### Query Durations (`prometheus_engine_query_duration_seconds`)
- **Type**: Histogram
- **Labels**: `slice` (inner_eval, prepare_time, queue_time, result_sort)
- **Description**: Query execution time breakdown
- **Percentiles**: p50, p90, p99
- **Normal Range**: 
  - `inner_eval_p99`: Typically < 10ms for simple queries
  - Other slices: Usually near 0 for simple queries
- **Alert**: High p99 values indicate slow queries or resource constraints

**What it means in simple terms:**
- When you query Prometheus (ask for data), this measures how long it takes
- Breaks down time into: preparation, execution, sorting results
- Think of it as: "How long does it take Prometheus to answer questions?"

**Why it matters:**
- Slow queries = slow dashboards and alerts
- High p99 (99th percentile) = some queries are very slow
- Helps identify performance bottlenecks

**Real-world analogy:**
Like timing how long it takes a librarian to find books. Slow queries = slow service.

**What to watch for:**
- ✅ Good: p99 < 10ms for simple queries
- ⚠️ Warning: p99 > 100ms
- ❌ Bad: p99 > 1s (very slow queries)

### Alerting Metrics

#### Rule Group Eval Duration (`prometheus_rule_group_evaluation_duration_seconds`)
- **Type**: Histogram
- **Description**: Time taken to evaluate alerting/recording rules
- **Normal Range**: Typically 0 if no rules are configured
- **Alert**: High values indicate slow rule evaluation

**What it means in simple terms:**
- Prometheus can run "rules" (like alerts or data transformations)
- This measures how long it takes to evaluate (run) these rules
- Think of it as: "How long does it take to check alert conditions?"

**Why it matters:**
- Slow rule evaluation = delayed alerts
- Should be fast (< 1s typically)
- Zero activity with configured rules = rules aren't running

**Real-world analogy:**
Like timing how long it takes to check all your security alarms. Slow checks = delayed warnings.

**What to watch for:**
- ✅ Good: Fast evaluation (< 1s), or zero if no rules configured
- ⚠️ Warning: Slow evaluation (> 5s)
- ❌ Bad: Zero activity but rules are configured (rules not running)

#### Rule Group Eval Activity (`prometheus_rule_group_evaluations_total`)
- **Type**: Counter
- **Description**: Total number of rule group evaluations
- **Normal Range**: Depends on configured rules and evaluation interval
- **Alert**: Zero values with configured rules indicate rule evaluation failures

## Jussi Application Metrics

These metrics are exposed by the Jussi application and provide insights into request processing, caching, and upstream communication.

### Request Metrics

#### Total Requests (`jussi_requests_total`)
- **Type**: Counter
- **Labels**: `namespace`, `method`, `status`
- **Description**: Total number of JSON-RPC requests processed
- **Example**: `jussi_requests_total{namespace="steemd",method="get_block",status="200"}`
- **Use Cases**: 
  - Track request volume by namespace and method
  - Monitor success/failure rates
  - Identify popular API methods

**What it means in simple terms:**
- Counts every API request your Jussi server has handled
- Includes labels: which namespace, which method, what status code
- Think of it as: "How many requests have we processed total?"

**Why it matters:**
- Shows your application's workload
- Can see which APIs are most popular
- Can track success vs. failure rates

**Real-world analogy:**
Like a restaurant's total customer count, broken down by meal type and whether they were satisfied.

**Example:**
```
jussi_requests_total{namespace="steemd", method="get_block", status="200"} = 50,000
```
Means: "We've successfully handled 50,000 get_block requests from the steemd namespace"

**What to watch for:**
- ✅ Good: Steady increase (normal traffic)
- ⚠️ Warning: Sudden drop (might indicate downtime)
- ❌ Bad: Zero requests when you expect traffic (server might be down)

#### Request Duration (`jussi_request_duration_seconds`)
- **Type**: Histogram
- **Labels**: `namespace`, `method`
- **Description**: Request processing latency in seconds
- **Buckets**: Default Prometheus buckets (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
- **Use Cases**:
  - Monitor API response times
  - Identify slow methods
  - Calculate p50, p95, p99 latencies

**What it means in simple terms:**
- Measures how long each request takes to process (latency)
- Stored as a histogram (shows distribution: fast, medium, slow requests)
- Think of it as: "How long do users wait for responses?"

**Why it matters:**
- Slow requests = bad user experience
- Helps identify performance problems
- Can calculate percentiles (p50, p95, p99)

**Real-world analogy:**
Like measuring how long customers wait in line. Most wait 30 seconds (p50), but 1% wait 5 minutes (p99).

**Percentiles explained:**
- **p50 (median)**: Half of requests are faster, half are slower
- **p95**: 95% of requests are faster than this
- **p99**: 99% of requests are faster than this (catches the slowest 1%)

**What to watch for:**
- ✅ Good: p99 < 1 second
- ⚠️ Warning: p99 > 5 seconds
- ❌ Bad: p99 > 10 seconds (very slow)

#### Request Errors (`jussi_request_errors_total`)
- **Type**: Counter
- **Labels**: `namespace`, `method`, `error_type`
- **Description**: Total number of request errors by type
- **Use Cases**:
  - Track error rates
  - Identify problematic methods
  - Monitor error trends

**What it means in simple terms:**
- Counts how many requests failed (returned errors)
- Includes error type (timeout, connection error, etc.)
- Think of it as: "How many requests failed?"

**Why it matters:**
- High error rate = unhappy users
- Different error types = different problems
- Helps identify which APIs are problematic

**Real-world analogy:**
Like counting how many orders you messed up, and categorizing the mistakes.

**What to watch for:**
- ✅ Good: Error rate < 1% of total requests
- ⚠️ Warning: Error rate 1-5%
- ❌ Bad: Error rate > 5% (many failures)

#### Batch Size (`jussi_batch_size`)
- **Type**: Histogram
- **Description**: Distribution of batch request sizes
- **Buckets**: [1, 5, 10, 25, 50, 100]
- **Use Cases**:
  - Monitor batch request patterns
  - Optimize batch size limits
  - Identify unusual batch sizes

**What it means in simple terms:**
- JSON-RPC allows sending multiple requests in one batch
- This measures how many requests are in each batch
- Think of it as: "How many requests come in each batch?"

**Why it matters:**
- Large batches = more efficient but use more memory
- Helps optimize batch size limits
- Identifies unusual usage patterns

**Real-world analogy:**
Like counting how many items customers order at once. Some order 1 item, some order 50.

**What to watch for:**
- ✅ Good: Most batches are reasonable size (1-50)
- ⚠️ Warning: Many very large batches (> 100)
- ❌ Bad: Batches exceeding limits (rejected requests)

### Cache Metrics

#### Cache Operations (`jussi_cache_operations_total`)
- **Type**: Counter
- **Labels**: `operation` (get, set, delete), `result` (hit, miss, error)
- **Description**: Total number of cache operations by type and result
- **Use Cases**:
  - Monitor cache usage
  - Track cache hit/miss ratios
  - Identify cache errors

**What it means in simple terms:**
- Counts cache operations: get (read), set (write), delete
- Shows results: hit (found in cache), miss (not in cache), error
- Think of it as: "How many times did we use the cache?"

**Why it matters:**
- Cache hits = fast responses (good!)
- Cache misses = slower responses (need to fetch from upstream)
- Errors = cache problems

**Real-world analogy:**
Like tracking how often you can serve food from the pre-made stock (cache hit) vs. cooking fresh (cache miss).

**What to watch for:**
- ✅ Good: High hit rate (> 70%)
- ⚠️ Warning: Low hit rate (< 50%)
- ❌ Bad: Many cache errors

#### Cache Hit Ratio (`jussi_cache_hit_ratio`)
- **Type**: Gauge
- **Description**: Current cache hit ratio (0.0 to 1.0)
- **Use Cases**:
  - Monitor cache effectiveness
  - Alert on low hit ratios
  - Optimize cache TTL settings

**What it means in simple terms:**
- Percentage of cache lookups that found data (0.0 to 1.0)
- 0.85 = 85% of cache lookups found data
- Think of it as: "What percentage of the time do we find data in cache?"

**Why it matters:**
- Higher ratio = better performance (fewer slow upstream calls)
- Low ratio = cache isn't effective (might need to adjust TTL)
- Directly impacts user experience

**Real-world analogy:**
Like measuring what percentage of customers get pre-made food vs. waiting for fresh cooking.

**What to watch for:**
- ✅ Good: > 0.7 (70%+)
- ⚠️ Warning: 0.5 - 0.7 (50-70%)
- ❌ Bad: < 0.5 (< 50%, cache not effective)

#### Cache Operation Duration (`jussi_cache_operation_duration_seconds`)
- **Type**: Histogram
- **Labels**: `operation` (get, set, delete)
- **Description**: Cache operation latency in seconds
- **Buckets**: [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
- **Use Cases**:
  - Monitor cache performance
  - Identify slow cache operations
  - Optimize cache backend settings

**What it means in simple terms:**
- How long cache operations take (get, set, delete)
- Think of it as: "How fast is our cache?"

**Why it matters:**
- Cache should be very fast (< 1ms typically)
- Slow cache = defeats the purpose of caching
- Helps identify cache performance issues

**Real-world analogy:**
Like timing how long it takes to grab something from the pre-made stock. Should be instant!

**What to watch for:**
- ✅ Good: < 1ms for gets
- ⚠️ Warning: 1-10ms
- ❌ Bad: > 10ms (cache is slow)

### Upstream Metrics

#### Upstream Requests (`jussi_upstream_requests_total`)
- **Type**: Counter
- **Labels**: `upstream`, `protocol` (http, ws)
- **Description**: Total number of requests sent to upstream services
- **Use Cases**:
  - Track upstream usage
  - Monitor load distribution
  - Identify upstream dependencies

**What it means in simple terms:**
- Counts requests sent to upstream services (the actual blockchain APIs)
- Think of it as: "How many times did we call the real APIs?"

**Why it matters:**
- Shows load on upstream services
- Can see which upstreams are used most
- Helps with capacity planning

**Real-world analogy:**
Like counting how many times you had to call suppliers to get fresh ingredients.

**What to watch for:**
- ✅ Good: Reasonable distribution across upstreams
- ⚠️ Warning: All traffic to one upstream (no redundancy)
- ❌ Bad: Zero requests when you expect traffic (upstream might be down)

#### Upstream Request Duration (`jussi_upstream_request_duration_seconds`)
- **Type**: Histogram
- **Labels**: `upstream`, `protocol`
- **Description**: Upstream request latency in seconds
- **Buckets**: Default Prometheus buckets
- **Use Cases**:
  - Monitor upstream performance
  - Identify slow upstreams
  - Calculate upstream SLA compliance

**What it means in simple terms:**
- How long upstream services take to respond
- Think of it as: "How fast are the real APIs?"

**Why it matters:**
- Slow upstreams = slow user experience
- Helps identify which upstreams are slow
- Can help choose faster upstreams

**Real-world analogy:**
Like timing how long suppliers take to deliver ingredients.

**What to watch for:**
- ✅ Good: < 1 second
- ⚠️ Warning: 1-5 seconds
- ❌ Bad: > 5 seconds (very slow upstreams)

#### Upstream Errors (`jussi_upstream_errors_total`)
- **Type**: Counter
- **Labels**: `upstream`, `protocol`, `error_type`
- **Description**: Total number of upstream errors by type
- **Use Cases**:
  - Track upstream reliability
  - Identify failing upstreams
  - Monitor error trends

**What it means in simple terms:**
- Counts errors from upstream services
- Think of it as: "How many times did upstream services fail?"

**Why it matters:**
- High error rate = upstream problems
- Helps identify unreliable upstreams
- Can trigger failover to backup upstreams

**Real-world analogy:**
Like counting how many times suppliers failed to deliver.

**What to watch for:**
- ✅ Good: Error rate < 1%
- ⚠️ Warning: Error rate 1-5%
- ❌ Bad: Error rate > 5% (upstream is unreliable)

### WebSocket Pool Metrics

**What it means in simple terms:**
- WebSocket = persistent connections (like a phone call vs. text messages)
- Pool = a collection of reusable connections
- These metrics track the connection pool

**Why it matters:**
- Connection pools improve performance (reuse connections)
- Too few connections = slow
- Too many connections = waste resources

**Real-world analogy:**
Like having a pool of phone lines. You want enough for demand, but not too many unused lines.

#### WebSocket Pool Size (`jussi_websocket_pool_size`)
- **Type**: Gauge
- **Labels**: `upstream`
- **Description**: Current size of the WebSocket connection pool
- **Use Cases**:
  - Monitor pool utilization
  - Optimize pool sizing
  - Identify pool exhaustion

**What to watch for:**
- ✅ Good: Some idle connections available (ready for traffic)
- ⚠️ Warning: All connections active (might need more)
- ❌ Bad: Zero idle connections when traffic is low (connection leak)

#### WebSocket Pool Active (`jussi_websocket_pool_active`)
- **Type**: Gauge
- **Labels**: `upstream`
- **Description**: Number of active WebSocket connections
- **Use Cases**:
  - Monitor active connections
  - Track connection usage
  - Identify connection leaks

#### WebSocket Pool Idle (`jussi_websocket_pool_idle`)
- **Type**: Gauge
- **Labels**: `upstream`
- **Description**: Number of idle WebSocket connections in the pool
- **Use Cases**:
  - Monitor pool efficiency
  - Optimize pool sizing
  - Identify connection waste

## Example Queries

### Request Rate by Namespace
```promql
rate(jussi_requests_total[5m])
```

### Cache Hit Ratio
```promql
jussi_cache_hit_ratio
```

### P99 Request Latency
```promql
histogram_quantile(0.99, rate(jussi_request_duration_seconds_bucket[5m]))
```

### Error Rate
```promql
rate(jussi_request_errors_total[5m])
```

### Upstream Request Duration by Upstream
```promql
histogram_quantile(0.95, rate(jussi_upstream_request_duration_seconds_bucket[5m])) by (upstream)
```

### Prometheus Memory Usage
```promql
prometheus_process_resident_memory_bytes / 1024 / 1024
```

### Scrape Duration vs Target Interval
```promql
prometheus_target_interval_length_seconds / prometheus_target_interval_length_seconds{quantile="0.5"}
```

## Alerting Recommendations

### Critical Alerts

1. **High Error Rate**
   ```promql
   rate(jussi_request_errors_total[5m]) > 0.1
   ```

2. **Low Cache Hit Ratio**
   ```promql
   jussi_cache_hit_ratio < 0.5
   ```

3. **High Request Latency**
   ```promql
   histogram_quantile(0.99, rate(jussi_request_duration_seconds_bucket[5m])) > 5
   ```

4. **Upstream Failures**
   ```promql
   rate(jussi_upstream_errors_total[5m]) > 0.05
   ```

5. **Prometheus WAL Corruptions**
   ```promql
   prometheus_tsdb_wal_corruptions_total > 0
   ```

6. **High Prometheus Memory Usage**
   ```promql
   prometheus_process_resident_memory_bytes > 2 * 1024 * 1024 * 1024  # 2GB
   ```

### Warning Alerts

1. **Increasing Request Latency**
   ```promql
   rate(histogram_quantile(0.95, rate(jussi_request_duration_seconds_bucket[5m]))[1h]) > 0.1
   ```

2. **Low Cache Hit Ratio Trend**
   ```promql
   jussi_cache_hit_ratio < 0.7
   ```

3. **High Scrape Duration**
   ```promql
   prometheus_target_interval_length_seconds > 20
   ```

## Grafana Dashboard

The metrics can be visualized in Grafana. Recommended panels:

1. **Request Rate**: Line graph showing requests per second by namespace
2. **Request Latency**: Heatmap or line graph with p50, p95, p99
3. **Error Rate**: Line graph showing error rate over time
4. **Cache Performance**: Gauge showing hit ratio, line graph showing operations
5. **Upstream Performance**: Line graphs showing request duration and error rate by upstream
6. **Prometheus Health**: Panels for memory usage, scrape duration, and WAL status

## Best Practices

1. **Regular Monitoring**: Review metrics regularly to identify trends and anomalies
2. **Baseline Establishment**: Establish baseline values for normal operation
3. **Alert Tuning**: Adjust alert thresholds based on actual system behavior
4. **Retention**: Configure appropriate retention periods for Prometheus data
5. **Cardinality**: Monitor metric cardinality to avoid high memory usage
6. **Label Usage**: Use labels judiciously to balance detail and performance

## Troubleshooting

### High Memory Usage
- Check for high cardinality metrics (too many unique label combinations)
- Review Prometheus retention settings
- Consider reducing scrape frequency for less critical targets

### Missing Metrics
- Verify Prometheus is enabled in configuration
- Check metrics endpoint accessibility
- Review Prometheus scrape configuration

### Slow Queries
- Check query complexity
- Review Prometheus query performance metrics
- Consider using recording rules for complex queries

## Common Questions

### Q: What's the difference between Counter and Gauge?
**A**: Counter only goes up (like total requests), Gauge can go up or down (like current memory usage).

### Q: Why do we need both request duration and request errors?
**A**: Duration tells you about speed, errors tell you about reliability. A request can be fast but still fail, or slow but succeed.

### Q: What's a good cache hit ratio?
**A**: Generally > 70% is good. < 50% means your cache isn't helping much.

### Q: Why monitor Prometheus itself?
**A**: If Prometheus is broken, you lose all monitoring! It's like making sure your security cameras are working.

### Q: What's cardinality and why does it matter?
**A**: Cardinality = number of unique metric combinations. High cardinality = too many unique metrics = high memory usage. Example: If you label by user_id and have 1 million users, you have 1 million unique metrics!

### Q: What's the difference between p50, p95, and p99?
**A**: 
- **p50**: Half of requests are faster, half are slower (median)
- **p95**: 95% of requests are faster than this
- **p99**: 99% of requests are faster than this (catches the worst 1%)

### Q: Should I worry if one metric shows a warning?
**A**: Not necessarily. Look at trends and multiple metrics together. One metric might be temporarily high, but if multiple metrics show problems, that's more concerning.

### Q: How often should I check metrics?
**A**: 
- **Real-time**: Critical production systems (set up alerts)
- **Daily**: Review dashboards for trends
- **Weekly**: Deep dive into performance metrics

### Q: What if I see high error rates?
**A**: 
1. Check which specific methods/namespaces are failing
2. Look at error types (timeout, connection error, etc.)
3. Check upstream health
4. Review recent code changes or deployments

### Q: What's a "normal" value for these metrics?
**A**: It depends on your system! Establish baselines by monitoring during normal operation. What's normal for one system might be abnormal for another.

## Next Steps

1. **Start simple**: Focus on request rate, error rate, and latency first
2. **Set up alerts**: Use the alerting recommendations in this document
3. **Create dashboards**: Visualize metrics in Grafana
4. **Establish baselines**: Learn what "normal" looks like for your system
5. **Iterate**: Adjust alerts and dashboards based on what you learn

Remember: Metrics are tools to help you understand your system. Don't try to monitor everything at once - start with the basics and expand as needed!

## References

- [Prometheus Metrics](https://prometheus.io/docs/concepts/metric_types/)
- [Prometheus Querying](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Dashboards](https://grafana.com/docs/grafana/latest/dashboards/)

