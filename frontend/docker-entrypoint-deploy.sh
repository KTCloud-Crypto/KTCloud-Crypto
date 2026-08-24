#!/bin/sh
set -eu

if [ "${HTTPS_ENABLED:-false}" = "true" ]; then
    if [ -z "${DOMAIN:-}" ]; then
        echo "DOMAIN is required when HTTPS_ENABLED=true" >&2
        exit 1
    fi
    if [ -z "${API_DOMAIN:-}" ]; then
        echo "API_DOMAIN is required when HTTPS_ENABLED=true" >&2
        exit 1
    fi
    if [ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
        echo "Let's Encrypt certificate for ${DOMAIN} was not found" >&2
        exit 1
    fi
    if [ ! -f "/etc/letsencrypt/live/${API_DOMAIN}/fullchain.pem" ]; then
        echo "Let's Encrypt certificate for ${API_DOMAIN} was not found" >&2
        exit 1
    fi
    envsubst '${DOMAIN} ${API_DOMAIN} ${ENVIRONMENT}' \
        < /etc/nginx/nginx.https.conf.template \
        > /etc/nginx/conf.d/default.conf
else
    envsubst '${ENVIRONMENT}' \
        < /etc/nginx/nginx.http.conf.template \
        > /etc/nginx/conf.d/default.conf
fi

exec "$@"
