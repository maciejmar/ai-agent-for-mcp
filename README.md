# Agent AI do diagnostyki serwera

Projekt zawiera skonteneryzowany backend FastAPI + LangGraph oraz frontend Angular.

## Uruchomienie przez Docker Compose

```bash
docker-compose up --build
```

Adresy:

- Frontend: `http://localhost:4200`
- Backend API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

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

Compose buduje tez realny MCP server z katalogu obok projektu:

```text
../mcp-serv/mcp-server-sandbox
```

Backend laczy sie z nim przez MCP Streamable HTTP:

```yaml
MCP_SERVER_URL: http://mcp-server:8000/mcp
MCP_API_KEY: dev-mcp-key
```

Agent uzywa tego MCP servera do narzedzi infrastrukturalnych:

- `server_container_status`
- `server_gpu_status`
- `ollama_list_models`

Odczyt logow aplikacyjnych zostaje lokalnie w backendzie, bo obecny MCP server nie ma jeszcze narzedzia do bezpiecznego czytania logow z allowlisty.
