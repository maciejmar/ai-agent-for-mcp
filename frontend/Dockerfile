# syntax=docker/dockerfile:1.4
FROM repo.bank.com.pl/zrai-docker-remote-dev/node:20-alpine AS build

WORKDIR /app

COPY package*.json ./

RUN --mount=type=secret,id=ca_cert,dst=/etc/pki/ca-trust/source/anchors/bank-jfrog-ca.crt \
    npm install

COPY . .
RUN npx ng build --configuration production

FROM repo.bank.com.pl/zrai-docker-remote-dev/nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/diagnostic-agent/browser /usr/share/nginx/html

EXPOSE 80
