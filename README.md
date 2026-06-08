# graf-dash

A production-grade Grafana + Prometheus observability stack built as a DevOps portfolio showcase.  
Demonstrates dashboards-as-code, SLO/error-budget tracking, multi-window burn-rate alerting, and realistic metric simulation.

## What's inside

| Component | Purpose |
|---|---|
| **Prometheus** | Metrics collection, alert evaluation, recording rules |
| **Grafana** | 4 provisioned dashboards (no manual setup required) |
| **Alertmanager** | Alert routing with severity-based receivers and inhibition |
| **demo-app** | Python service simulating 5 microservices with realistic Golden Signals |
| **node-exporter** | Host-level metrics (optional, `--profile full`) |

### Dashboards

| Dashboard | Description |
|---|---|
| **Golden Signals** | Latency (p50/p95/p99), traffic (req/s), error rate (%), saturation (connections, DB pool) |
| **Service Overview** | Per-service health table, business metrics (orders, revenue, active users) |
| **Infrastructure Overview** | CPU, memory, disk, network from node-exporter |
| **SLO / Error Budget** | 99.9% availability SLO, multi-window burn rate, budget remaining over time |

### Alert rules

| File | Alerts |
|---|---|
| `prometheus/alerts/application.yml` | HighErrorRate, CriticalErrorRate, HighP99Latency, TrafficDrop, ServiceDown |
| `prometheus/alerts/infrastructure.yml` | NodeHighCPU, NodeHighMemory, NodeDiskSpaceLow, PrometheusTargetDown |
| `prometheus/alerts/slo.yml` | SLOErrorBudgetBurnFast (1h), SLOErrorBudgetBurnElevated (6h), SLOErrorBudgetBurnSlow (3d) |

---

## Quick start

```bash
# 1. Clone and enter the repo
git clone <your-fork-url>
cd graf-dash

# 2. (Optional) set a Grafana password
cp .env.example .env
# edit .env

# 3. Start the core stack (Prometheus + Grafana + Alertmanager + demo-app)
docker compose up -d

# 4. Open Grafana
# Windows
start http://localhost:3000
# macOS
open http://localhost:3000
# Linux
xdg-open http://localhost:3000
```

Grafana will automatically load all four dashboards from `grafana/dashboards/`.  
The demo-app begins emitting metrics immediately — dashboards populate within ~30 seconds.

### With host metrics (Linux / WSL2)

```bash
docker compose --profile full up -d
```

> **Windows note**: node-exporter mounts `/proc`, `/sys`, and `/` from the Linux kernel.  
> On **Docker Desktop with WSL2** (the default since Docker Desktop 4.x) this works — but the metrics reflect the WSL2 VM, not the Windows host.  
> On **Docker Desktop without WSL2** (Hyper-V backend) the mounts will fail; omit `--profile full` and skip the Infrastructure Overview dashboard.  
> The other three dashboards (Golden Signals, Service Overview, SLO) work on all Windows configurations.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Docker network: monitoring                               │
│                                                           │
│  ┌──────────┐  scrape   ┌─────────────┐                  │
│  │  demo-   │◄──────────│             │                  │
│  │  app     │  :8000    │ Prometheus  │──evaluate──► alert│
│  └──────────┘           │  :9090      │   rules           │
│                         └──────┬──────┘                   │
│  ┌──────────┐  scrape          │ scrape                   │
│  │  node-   │◄─────────────────┘                         │
│  │  exporter│  :9100                                      │
│  └──────────┘           ┌──────────────┐                  │
│                         │ Alertmanager │                   │
│  ┌──────────┐  query    │  :9093       │──► Slack/webhook │
│  │  Grafana │──────────►│              │                   │
│  │  :3000   │           └──────────────┘                   │
│  └──────────┘                                             │
└──────────────────────────────────────────────────────────┘
```

---

## Project structure

```
graf-dash/
├── docker-compose.yml
├── .env.example
├── prometheus/
│   ├── prometheus.yml              # Scrape config + alertmanager wiring
│   └── alerts/
│       ├── application.yml         # Service-level alerts
│       ├── infrastructure.yml      # Host-level alerts
│       └── slo.yml                 # Multi-window burn-rate SLO alerts
├── alertmanager/
│   └── alertmanager.yml            # Routing tree, receivers, inhibition
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/            # Auto-configures Prometheus datasource
│   │   └── dashboards/             # Dashboard provider config
│   └── dashboards/
│       ├── golden-signals.json
│       ├── service-overview.json
│       ├── infrastructure-overview.json
│       └── slo-error-budget.json
├── apps/
│   └── demo-app/
│       ├── app.py                  # Metrics simulator
│       ├── requirements.txt
│       └── Dockerfile
└── .github/
    └── workflows/
        └── validate.yml            # CI: promtool, amtool, JSON lint, image build
```

---

## Useful endpoints

| URL | What it is |
|---|---|
| http://localhost:3000 | Grafana (admin/admin) |
| http://localhost:9090 | Prometheus UI + query explorer |
| http://localhost:9090/alerts | Firing alert status |
| http://localhost:9093 | Alertmanager UI |
| http://localhost:8000/metrics | Raw demo-app metrics |
| http://localhost:9100/metrics | Raw node-exporter metrics (profile full) |

---

## Metrics reference

The `demo-app` exposes these metrics:

| Metric | Type | Labels |
|---|---|---|
| `http_requests_total` | Counter | `service`, `method`, `endpoint`, `status_code` |
| `http_request_duration_seconds` | Histogram | `service`, `method`, `endpoint` |
| `active_connections` | Gauge | `service` |
| `db_connection_pool_usage` | Gauge | `service` |
| `orders_total` | Counter | `status` |
| `revenue_dollars_total` | Counter | `tier` |
| `active_users_total` | Gauge | — |

### Key PromQL queries

```promql
# Request rate per service
sum(rate(http_requests_total[5m])) by (service)

# Error rate %
sum(rate(http_requests_total{status_code=~"5.."}[5m])) by (service)
/ sum(rate(http_requests_total[5m])) by (service)

# p99 latency
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service)
)

# Error budget burn rate (vs 99.9% SLO)
(sum(rate(http_requests_total{status_code=~"5.."}[1h]))
 / sum(rate(http_requests_total[1h]))) / (1 - 0.999)
```

---

## CI pipeline

GitHub Actions runs on every push:

1. **`promtool check config`** — validates `prometheus.yml`
2. **`promtool check rules`** — validates all alert rule files
3. **`amtool check-config`** — validates `alertmanager.yml`
4. **JSON lint** — verifies dashboard JSON structure
5. **Docker build + smoke test** — builds the demo-app image and hits `/metrics`

---

## Extending this stack

| What to add | How |
|---|---|
| Loki (log aggregation) | Add `grafana/loki:latest` to docker-compose and a Loki datasource |
| Tempo (traces) | Add `grafana/tempo:latest`, wire the demo-app with OpenTelemetry |
| cAdvisor (container metrics) | Add to docker-compose with the `full` profile |
| Real app | Replace or supplement `demo-app` with your own service; expose `/metrics` |
| Grafana Oncall | Replace the Alertmanager Slack webhook with Grafana Oncall for escalation |

---

## SLO methodology

The SLO dashboard implements the **multi-window, multi-burn-rate** pattern from the [Google SRE Workbook](https://sre.google/workbook/alerting-on-slos/):

| Alert | Window | Burn rate | Budget consumed in |
|---|---|---|---|
| Critical page | 1 hour | 14.4× | ~2 hours |
| Warning page | 6 hours | 6× | ~5 days |
| Ticket | 3 days | 3× | ~10 days |

This approach balances **fast detection** of sharp outages with **slow-burn** visibility, while avoiding alert fatigue from minor blips.
