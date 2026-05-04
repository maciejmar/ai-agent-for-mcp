# syntax=docker/dockerfile:1.4
# Docker Hub is unavailable in the bank network.
FROM repo.bank.com.pl/zrai-docker-remote-dev/node:20 AS build

ARG NPM_REGISTRY=""
ARG NPM_AUTH_TOKEN=""

WORKDIR /app

RUN if [ -n "$NPM_REGISTRY" ]; then \
    echo "registry=${NPM_REGISTRY}" > .npmrc ; \
    if [ -n "$NPM_AUTH_TOKEN" ]; then \
      REGISTRY_HOST=$(echo "$NPM_REGISTRY" | sed 's|https\?://||'); \
      echo "//${REGISTRY_HOST}:_authToken=${NPM_AUTH_TOKEN}" >> .npmrc ; \
    fi ; \
  fi

COPY package*.json ./
RUN --mount=type=secret,id=ca_cert,target=/etc/ssl/certs/ca.pem \
    NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca.pem \
    npm install

COPY . .
RUN npx ng build --configuration production

FROM repo.bank.com.pl/zrai-docker-remote-dev/nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/diagnostic-agent/browser /usr/share/nginx/html

EXPOSE 80
