FROM busybox:1.37.0-uclibc AS healthcheck

FROM grafana/loki:3.7.3
COPY --from=healthcheck /bin/busybox /bin/busybox
