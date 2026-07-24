#!/bin/sh
set -eu

if [ "${HTTPS_ENABLED:-false}" = "true" ]; then
    if [ -z "${DOMAIN:-}" ]; then
        echo "DOMAIN is required when HTTPS_ENABLED=true" >&2
        exit 1
    fi
    if [ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
        echo "Let's Encrypt certificate for ${DOMAIN} was not found" >&2
        exit 1
    fi
    envsubst '${DOMAIN}' \
        < /etc/nginx/nginx.https.conf.template \
        > /etc/nginx/conf.d/default.conf
fi

exec "$@"
