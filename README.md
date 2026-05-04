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

Domyślnie agent czyta przykładowy log `backend/sample_app.log`. Aby podpiąć realny log hosta, odkomentuj volume w `docker-compose.yml`:

```yaml
- /var/log/app.log:/host/var/log/app.log:ro
```

Allowlista MCP jest kontrolowana zmienną `MCP_ALLOWED_LOG_PATHS`.

## Rejestry bankowe / JFrog

Dockerfile używa obrazów bazowych z:

```text
repo.bank.com.pl/zrai-docker-remote-dev
```

Compose przekazuje sekrety zgodnie ze środowiskiem bankowym:

```yaml
secrets:
  pip_conf:
    file: /etc/pip.conf
  ca_cert:
    file: /etc/pki/ca-trust/source/anchors/bank-jfrog-ca.crt
```

Frontend obsługuje zmienne:

```bash
NPM_REGISTRY=
NPM_AUTH_TOKEN=
```
