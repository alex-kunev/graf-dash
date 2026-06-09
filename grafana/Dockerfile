FROM grafana/grafana:10.4.2

# Bake provisioning and dashboards into the image for Render deployment
COPY --chown=472:root provisioning /etc/grafana/provisioning
COPY --chown=472:root dashboards    /var/lib/grafana/dashboards
