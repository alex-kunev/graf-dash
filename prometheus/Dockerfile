FROM prom/prometheus:v2.51.2

COPY prometheus.render.yml /etc/prometheus/prometheus.yml
COPY alerts/               /etc/prometheus/alerts/
COPY entrypoint.sh         /entrypoint.sh

USER root
RUN chmod +x /entrypoint.sh && mkdir -p /etc/prometheus/secrets /prometheus

ENTRYPOINT ["/entrypoint.sh"]
