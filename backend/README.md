# Agent diagnostyczny LangGraph + MCP

Backend działa jako offline-first agent diagnostyczny:

- `mcp_tools.py` jest granicą MCP-like: allowlista plików logów i bezpiecznych komend.
- `agent.py` definiuje graf LangGraph: `fetch_logs -> analyze -> suggest_fixes`.
- `main.py` udostępnia API dla dashboardu Angular.

## Uruchomienie

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Domyślna allowlista logów:

```text
/var/log/app.log
./sample_app.log
```

Możesz ją zmienić zmienną środowiskową:

```bash
set MCP_ALLOWED_LOG_PATHS=C:\logs\app.log,C:\logs\worker.log
```
