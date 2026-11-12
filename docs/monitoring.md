# Monitoring & Alerting

## Health probes
- GET `/api/health` — liveness
- GET `/api/ready` — readiness

## Metrics
- GET `/metrics` — Prometheus-style starter endpoint.

For production, replace the in-process counter with `prometheus-client` histograms/counters and scrape from Prometheus/Grafana.

## Suggested alerts
1. `5xx > 2% for 5m` -> high priority.
2. `/api/health` failing for 2 consecutive checks -> high priority.
3. Checkout errors > 5% for 10m -> high priority.
4. Razorpay payment failure ratio > baseline -> high priority.
5. Catalog import failure -> medium priority.
6. Disk/database capacity > 80% -> medium priority.

## Logging
JSON logs are emitted to stdout. A production runtime should ship stdout to its centralized log service and retain request IDs for correlation.
