from prometheus_client import Counter, Gauge, Histogram


HTTP_REQUESTS = Counter(
    "signaltrade_http_requests_total", "HTTP requests", ["method", "route", "status"]
)
HTTP_DURATION = Histogram(
    "signaltrade_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
HTTP_IN_PROGRESS = Gauge(
    "signaltrade_http_requests_in_progress", "Currently running HTTP requests"
)
SECURITY_EVENTS = Counter(
    "signaltrade_security_events_total", "Security audit events", ["event_type", "outcome"]
)
WORKER_ERRORS = Counter(
    "signaltrade_worker_errors_total", "Worker loop failures", ["loop"]
)
WORKER_RECOVERIES = Counter(
    "signaltrade_worker_recoveries_total", "Recovered stale executions", ["outcome"]
)
WORKER_TASK_IN_PROGRESS = Gauge(
    "signaltrade_worker_task_in_progress", "Currently running worker tasks", ["task"]
)
WORKER_TASK_RUNS = Counter(
    "signaltrade_worker_task_runs_total", "Worker task runs", ["task", "result"]
)
WORKER_TASK_DURATION = Histogram(
    "signaltrade_worker_task_duration_seconds",
    "Worker task duration",
    ["task"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)
WORKER_TASK_LAST_SUCCESS = Gauge(
    "signaltrade_worker_task_last_success_timestamp_seconds",
    "Unix timestamp of the last successful worker task run",
    ["task"],
)
EXTERNAL_REQUESTS = Counter(
    "signaltrade_external_requests_total", "External API requests",
    ["provider", "operation", "outcome"],
)
EXTERNAL_DURATION = Histogram(
    "signaltrade_external_request_duration_seconds", "External API latency",
    ["provider", "operation"], buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
DATABASE_QUERY_DURATION = Histogram(
    "signaltrade_database_query_duration_seconds",
    "Database query latency",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
WEBSOCKET_CONNECTIONS = Gauge(
    "signaltrade_websocket_connected", "WebSocket connection state", ["provider"]
)
WEBSOCKET_RECONNECTS = Counter(
    "signaltrade_websocket_reconnections_total", "WebSocket reconnect attempts", ["provider"]
)
MARKET_LAST_TICK = Gauge(
    "signaltrade_market_stream_last_tick_timestamp_seconds", "Last market tick Unix timestamp", ["market"]
)
STRATEGY_SIGNALS = Counter(
    "signaltrade_strategy_signals_total", "Generated strategy signals",
    ["strategy", "market", "action", "source"],
)
STRATEGY_EXECUTIONS = Counter(
    "signaltrade_strategy_executions_total", "Strategy execution outcomes",
    ["mode", "market", "action", "outcome"],
)
ORDERS = Counter(
    "signaltrade_orders_total", "Order outcomes", ["mode", "market", "action", "outcome"]
)
ORDER_DURATION = Histogram(
    "signaltrade_order_duration_seconds", "Order processing latency",
    ["mode", "market", "action"], buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
POSITION_MISMATCHES = Counter(
    "signaltrade_position_mismatches_total", "Detected position mismatches", ["market"]
)
