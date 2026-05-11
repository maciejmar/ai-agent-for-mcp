from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", "").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "").strip()
        self.timeout_seconds = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "30"))
        self.enabled = os.getenv("OLLAMA_ENABLED", "true").lower() in {"1", "true", "yes"} and bool(
            self.base_url and self.model
        )

    def suggest(self, payload: dict[str, Any]) -> dict[str, str]:
        if not self.enabled:
            return {"status": "disabled", "content": ""}

        prompt = self._build_prompt(payload)
        request_body = {
            "model": self.model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Jestes agentem diagnostycznym dla aplikacji w izolowanej sieci. "
                        "Analizuj wylacznie dane dostarczone w prompcie. "
                        "Nie wymyslaj komend spoza danych. "
                        "Odpowiedz po polsku, zwiezle, w punktach: przyczyna, ryzyko, kroki naprawcze."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "options": {"temperature": 0.1},
        }

        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return {"status": "error", "content": f"Ollama unavailable: {exc}"}

        content = data.get("message", {}).get("content", "")
        return {"status": "ok", "content": content.strip()}

    def _build_prompt(self, payload: dict[str, Any]) -> str:
        return (
            "Dane diagnostyczne zostaly juz przefiltrowane przez MCP i zredagowane z sekretow.\n\n"
            f"Findings:\n{json.dumps(payload.get('findings', []), ensure_ascii=False, indent=2)}\n\n"
            f"Rule recommendations:\n{json.dumps(payload.get('recommendations', []), ensure_ascii=False, indent=2)}\n\n"
            f"Log metadata:\n{json.dumps(payload.get('log_snapshot', {}), ensure_ascii=False, indent=2)}\n\n"
            f"Resource metadata:\n{json.dumps(payload.get('resource_snapshot', {}), ensure_ascii=False, indent=2)[:6000]}"
        )
