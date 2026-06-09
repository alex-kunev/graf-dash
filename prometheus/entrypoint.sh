#!/bin/sh
set -e

mkdir -p /etc/prometheus/secrets
printf '%s' "${GRAFANA_CLOUD_TOKEN}" > /etc/prometheus/secrets/grafana_cloud_token

exec /bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --storage.tsdb.retention.time=2h \
  --web.listen-address=0.0.0.0:9090 \
  --web.enable-lifecycle \
  --enable-feature=expand-external-labels
