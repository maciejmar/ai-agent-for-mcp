# syntax=docker/dockerfile:1.4
FROM repo.bank.com.pl/zrai-docker-remote-dev/node:20 AS build

WORKDIR /app

COPY package*.json ./

RUN --mount=type=secret,id=ca_cert,target=/tmp/ca.pem \
    --mount=type=secret,id=npmrc,target=/tmp/.npmrc \
    sh -c ' \
      if [ -s /tmp/.npmrc ]; then cp /tmp/.npmrc /root/.npmrc; fi && \
      if [ -s /tmp/ca.pem ]; then export NODE_EXTRA_CA_CERTS=/tmp/ca.pem; fi && \
      npm install --include=dev \
    '

COPY . .
RUN npm run build

FROM repo.bank.com.pl/zrai-docker-remote-dev/nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/diagnostic-agent/browser /usr/share/nginx/html

EXPOSE 80
