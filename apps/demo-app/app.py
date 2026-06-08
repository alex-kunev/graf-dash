#!/usr/bin/env python3
"""
Microservices metrics simulator for the Grafana/Prometheus portfolio showcase.

Spins up background threads that generate realistic Golden Signals metrics for
five simulated services with a time-of-day traffic pattern, log-normal latency
distributions, and configurable error rates.
"""

import math
import os
import random
import time
from threading import Thread

from prometheus_client import Counter, Gauge, Histogram, Info, start_http_server

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests processed",
    ["service", "method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["service", "method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 10.0],
)

ACTIVE_CONNECTIONS = Gauge(
    "active_connections",
    "Active connections per service",
    ["service"],
)

DB_POOL_USAGE = Gauge(
    "db_connection_pool_usage",
    "DB connection pool utilisation ratio (0-1)",
    ["service"],
)

ORDERS_TOTAL = Counter("orders_total", "Total orders", ["status"])
REVENUE_TOTAL = Counter("revenue_dollars_total", "Total revenue (USD)", ["tier"])
ACTIVE_USERS = Gauge("active_users_total", "Currently active users")

APP_INFO = Info("demo_app", "Application metadata")
APP_INFO.info({"version": "2.1.0", "environment": "portfolio-demo", "team": "platform"})

# ---------------------------------------------------------------------------
# Service configuration
# ---------------------------------------------------------------------------

SERVICES = {
    "api-gateway": {
        "base_rps": 180,
        "base_latency_ms": 45,
        "latency_jitter": 0.55,
        "error_rate": 0.008,
        "endpoints": [
            "/api/health",
            "/api/v1/users",
            "/api/v1/orders",
            "/api/v1/products",
            "/api/v1/search",
        ],
    },
    "user-service": {
        "base_rps": 45,
        "base_latency_ms": 70,
        "latency_jitter": 0.50,
        "error_rate": 0.015,
        "endpoints": [
            "/users",
            "/users/{id}",
            "/auth/login",
            "/auth/register",
            "/users/{id}/profile",
        ],
    },
    "order-service": {
        "base_rps": 60,
        "base_latency_ms": 110,
        "latency_jitter": 0.70,
        "error_rate": 0.012,
        "endpoints": [
            "/orders",
            "/orders/{id}",
            "/orders/checkout",
            "/orders/{id}/status",
            "/orders/history",
        ],
    },
    "payment-service": {
        "base_rps": 30,
        "base_latency_ms": 180,
        "latency_jitter": 0.80,
        "error_rate": 0.025,
        "endpoints": [
            "/payments/process",
            "/payments/{id}",
            "/payments/refund",
            "/payments/verify",
        ],
    },
    "inventory-service": {
        "base_rps": 50,
        "base_latency_ms": 55,
        "latency_jitter": 0.40,
        "error_rate": 0.008,
        "endpoints": [
            "/inventory",
            "/inventory/{id}",
            "/inventory/reserve",
            "/inventory/release",
        ],
    },
}

METHODS = ["GET", "POST", "PUT", "DELETE"]
METHOD_WEIGHTS = [0.60, 0.25, 0.10, 0.05]


# ---------------------------------------------------------------------------
# Traffic shaping
# ---------------------------------------------------------------------------

def traffic_multiplier() -> float:
    """Return a multiplier that mimics a realistic daily traffic curve.

    Peak at 14:00, trough at 04:00. Includes ±10% random jitter and a
    rare (1%) traffic spike of 2.5×.
    """
    hour = (time.time() % 86400) / 3600
    daily = 0.25 + 0.75 * (1 + math.sin((hour - 14) * math.pi / 12)) / 2
    noise = random.uniform(0.90, 1.10)
    spike = 2.5 if random.random() < 0.01 else 1.0
    return daily * noise * spike


# ---------------------------------------------------------------------------
# Simulators
# ---------------------------------------------------------------------------

def simulate_service(name: str, cfg: dict) -> None:
    base_rps = cfg["base_rps"]
    base_latency = cfg["base_latency_ms"] / 1000.0
    jitter = cfg["latency_jitter"]
    error_rate = cfg["error_rate"]
    endpoints = cfg["endpoints"]
    pool_capacity = base_rps * 0.15

    while True:
        mult = traffic_multiplier()
        rps = max(1, int(base_rps * mult))

        connections = max(0, int(rps * 0.08 + random.gauss(0, 3)))
        ACTIVE_CONNECTIONS.labels(service=name).set(connections)

        pool = min(1.0, connections / pool_capacity) + random.uniform(-0.03, 0.03)
        DB_POOL_USAGE.labels(service=name).set(max(0.0, min(1.0, pool)))

        for _ in range(rps):
            method = random.choices(METHODS, weights=METHOD_WEIGHTS)[0]
            endpoint = random.choice(endpoints)

            roll = random.random()
            if roll < error_rate:
                status = random.choice([500, 502, 503, 504])
            elif roll < error_rate + 0.04:
                status = random.choice([400, 404, 422])
            elif method == "POST":
                status = 201
            else:
                status = 200

            REQUEST_COUNT.labels(
                service=name,
                method=method,
                endpoint=endpoint,
                status_code=str(status),
            ).inc()

            latency = random.lognormvariate(math.log(base_latency), jitter)
            if status >= 500:
                latency *= random.uniform(2.0, 5.0)
            REQUEST_LATENCY.labels(
                service=name, method=method, endpoint=endpoint
            ).observe(latency)

        time.sleep(1)


def simulate_business_metrics() -> None:
    while True:
        mult = traffic_multiplier()

        new_orders = max(0, int(random.gauss(3 * mult, 1)))
        for _ in range(new_orders):
            success = random.random() > 0.04
            ORDERS_TOTAL.labels(status="completed" if success else "failed").inc()
            if success:
                amount = random.lognormvariate(math.log(85), 0.8)
                tier = random.choices(
                    ["standard", "premium", "enterprise"],
                    weights=[0.70, 0.20, 0.10],
                )[0]
                REVENUE_TOTAL.labels(tier=tier).inc(amount)

        users = max(0, int(random.gauss(800 * mult, 800 * mult * 0.05)))
        ACTIVE_USERS.set(users)

        time.sleep(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # Render sets PORT automatically; fall back to METRICS_PORT for local docker-compose
    port = int(os.environ.get("PORT") or os.environ.get("METRICS_PORT", 8000))
    start_http_server(port)
    print(f"[demo-app] Prometheus metrics exposed on :{port}/metrics")

    threads: list[Thread] = []

    for svc_name, svc_cfg in SERVICES.items():
        t = Thread(target=simulate_service, args=(svc_name, svc_cfg), daemon=True)
        t.start()
        threads.append(t)
        print(f"[demo-app]   simulator started → {svc_name}")

    biz = Thread(target=simulate_business_metrics, daemon=True)
    biz.start()
    threads.append(biz)
    print("[demo-app]   simulator started → business-metrics")
    print("[demo-app] Ready.")

    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
