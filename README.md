# Agent AI do diagnostyki serwera

Projekt zawiera skonteneryzowany backend FastAPI + LangGraph oraz frontend Angular.

## Uruchomienie przez Docker Compose

```bash
docker-compose up --build
```

Adresy:

- Aplikacja: `http://localhost:8012/agent-to-mcp/`
- Backend API przez Nginx: `http://localhost:8012/agent-to-mcp/api`
- Swagger przez Nginx: `http://localhost:8012/agent-to-mcp/docs`

Na hosta wystawiany jest tylko port `8012`. Backend jest dostepny tylko w sieci Docker i jest proxy'owany przez Nginx frontendu.

## Wspolny Nginx

Do wspolnego Nginxa, np. `portal-ai-nginx`, nie wklejaj konfiguracji z `frontend/nginx.conf`, bo zawiera ona nazwy kontenerow widoczne tylko w sieci tej aplikacji (`backend`, `mcp-server`).

Wspolny Nginx powinien proxy'owac tylko do jednego wystawionego portu aplikacji:

```nginx
location = /agent-to-mcp {
    return 301 /agent-to-mcp/;
}

location /agent-to-mcp/ {
    proxy_pass          http://10.112.32.19:8012/agent-to-mcp/;
    proxy_http_version  1.1;
    proxy_set_header    Host                $host;
    proxy_set_header    X-Real-IP           $remote_addr;
    proxy_set_header    X-Forwarded-For     $proxy_add_x_forwarded_for;
    proxy_set_header    X-Forwarded-Proto   $scheme;
    proxy_read_timeout  300s;
    proxy_send_timeout  300s;
}
```

Po zmianie konfiguracji wspolnego Nginxa sprawdz i przeladuj:

```bash
docker exec portal-ai-nginx nginx -t
docker exec portal-ai-nginx nginx -s reload
```

Domyslnie agent czyta przykladowy log `backend/sample_app.log`. Aby podpiac realny log hosta, odkomentuj volume w `docker-compose.yml`:

```yaml
- /var/log/app.log:/host/var/log/app.log:ro
```

Allowlista MCP jest kontrolowana zmienna `MCP_ALLOWED_LOG_PATHS`.

## Rejestry bankowe / JFrog

Dockerfile uzywa obrazow bazowych z:

```text
repo.bank.com.pl/zrai-docker-remote-dev
```

Compose przekazuje sekrety zgodnie ze srodowiskiem bankowym:

```yaml
secrets:
  pip_conf:
    file: /etc/pip.conf
  ca_cert:
    file: /etc/pki/ca-trust/source/anchors/bank-jfrog-ca.crt
```

Frontend obsluguje zmienne:

```bash
NPM_REGISTRY=
NPM_AUTH_TOKEN=
```

## Ollama w kontenerze

Agent zaklada, ze Ollama dziala jako kontener, nie jako proces na hoscie.

Domyslna konfiguracja w `docker-compose.yml`:

```yaml
OLLAMA_ENABLED: true
OLLAMA_BASE_URL: http://ollama:11434
OLLAMA_MODEL: llama3.1
OLLAMA_TIMEOUT_SECONDS: 30
```
Backend jest podpiety do dwoch sieci Docker:

- `diagnostic-agent` - siec tej aplikacji
- `ollama-network` - zewnetrzna siec, w ktorej powinien byc kontener Ollamy

Jesli kontener Ollamy ma inna nazwe DNS niz `ollama`, ustaw:

```bash
OLLAMA_BASE_URL=http://nazwa-kontenera-ollamy:11434
```

Przed startem aplikacji siec Ollamy musi istniec:

```bash
docker network create ollama-network
```

Kontener Ollamy powinien byc dolaczony do tej sieci, np.:

```bash
docker network connect ollama-network ollama
```

## Zewnetrzny MCP server

Ten projekt nie buduje MCP servera. Korzysta z osobnej aplikacji z katalogu:

```text
../mcp-serv/mcp-server-sandbox
```

Tamten MCP server zgodnie ze swoim `docker-compose.yml` wystawia na hoscie port `8010` i endpointy:

```text
http://10.112.32.19:8010/mcp
http://10.112.32.19:8010/health
```

Backend agenta laczy sie z nim przez MCP Streamable HTTP. Domyslnie w Dockerze uzywa adresu hosta:

```yaml
MCP_SERVER_URL: http://host.docker.internal:8010/mcp
MCP_API_KEY: dev-mcp-key
```

Agent uzywa tego MCP servera do narzedzi infrastrukturalnych:

- `server_container_status`
- `server_gpu_status`
- `ollama_list_models`

Agent uzywa tez narzedzi logowych MCP:

- `log_list_allowed_paths`
- `log_read_filtered`
- `log_find_errors`

Odczyt logow przez MCP jest preferowana sciezka. Lokalny odczyt w backendzie zostaje tylko jako fallback awaryjny.

Logi po stronie MCP servera kontroluje:

```yaml
MCP_ALLOWED_LOG_PATHS: /logs/sample_app.log,/host/var/log/app.log
MCP_MAX_LOG_LINES: 500
MCP_MAX_LOG_LINES_HARD_LIMIT: 2000
```
