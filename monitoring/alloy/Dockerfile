FROM busybox:1.37.0-uclibc AS healthcheck

FROM grafana/alloy:v1.11.3
COPY --from=healthcheck /bin/busybox /bin/busybox
