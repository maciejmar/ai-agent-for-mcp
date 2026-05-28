from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


class OllamaClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", "").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "default").strip()
        self.timeout_seconds = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "30"))
        self.enabled = os.getenv("OLLAMA_ENABLED", "true").lower() in {"1", "true", "yes"} and bool(
            self.base_url
        )

    def suggest(self, payload: dict[str, Any]) -> dict[str, str]:
        if not self.enabled:
            return {"status": "disabled", "content": ""}

        prompt = self._build_prompt(payload)
        request_body = {
            "model": self.model,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Jestes agentem diagnostycznym dla serwera AI w izolowanej sieci bankowej. "
                        "Analizuj WYLACZNIE dane dostarczone w prompcie — nie wymyslaj konfiguracji ani komend. "
                        "Odpowiedz po polsku, szczegolowo, w nastepujacych sekcjach:\n"
                        "1) Konfiguracja i ustawienia — problemy z env, limity pamieci, restart policy, brakujace lub nieoptymalne ustawienia\n"
                        "2) Status serwisow — zdrowie kontenerow, liczba restartow, unhealthy serwisy\n"
                        "3) Zasoby i obrazy Docker — zuzycie dysku, duze obrazy do optymalizacji, woluminy\n"
                        "4) Ryzyko i kroki naprawcze — konkretne, priorytetyzowane dzialania"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }

        req = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return {"status": "error", "content": f"LLM unavailable: {exc}"}

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"status": "ok", "content": _strip_thinking(content).strip()}

    def _build_prompt(self, payload: dict[str, Any]) -> str:
        resource = payload.get("resource_snapshot", {})
        remote = resource.get("remote_mcp", {})
        container_configs = remote.get("container_configs", {})
        system_info = remote.get("system_info", {})
        disk_usage = remote.get("disk_usage", {})

        return (
            "Dane diagnostyczne zostaly przefiltrowane przez MCP i zredagowane z sekretow.\n\n"
            f"=== Findings ===\n{json.dumps(payload.get('findings', []), ensure_ascii=False, indent=2)}\n\n"
            f"=== Rule recommendations ===\n{json.dumps(payload.get('recommendations', []), ensure_ascii=False, indent=2)}\n\n"
            f"=== Log metadata ===\n{json.dumps(payload.get('log_snapshot', {}), ensure_ascii=False, indent=2)}\n\n"
            f"=== System info (host) ===\n{json.dumps(system_info, ensure_ascii=False, indent=2)}\n\n"
            f"=== Container configurations ===\n{json.dumps(container_configs, ensure_ascii=False, indent=2)[:4000]}\n\n"
            f"=== Docker disk usage ===\n{json.dumps(disk_usage, ensure_ascii=False, indent=2)[:2000]}\n\n"
            f"=== Full resource snapshot ===\n{json.dumps(resource, ensure_ascii=False, indent=2)[:3000]}"
        )


def _strip_thinking(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
