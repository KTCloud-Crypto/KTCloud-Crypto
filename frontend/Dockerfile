FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx.https.conf /etc/nginx/nginx.https.conf.template
COPY docker-entrypoint-deploy.sh /usr/local/bin/docker-entrypoint-deploy.sh
COPY --from=build /app/dist /usr/share/nginx/html

RUN chmod +x /usr/local/bin/docker-entrypoint-deploy.sh

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost/healthz || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint-deploy.sh"]
CMD ["nginx", "-g", "daemon off;"]
