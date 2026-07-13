from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Callable
from urllib.parse import urlparse, urlunparse

# Order in which running engines are tried as a fallback when the configured
# LLM is unreachable — roughly strongest/production-grade serving engines first.
ENGINE_FALLBACK_PRIORITY = [
    re.compile(r"vllm", re.IGNORECASE),
    re.compile(r"sglang", re.IGNORECASE),
    re.compile(r"lmdeploy", re.IGNORECASE),
    re.compile(r"text-generation-inference|\btgi\b", re.IGNORECASE),
    re.compile(r"llama[.\-_]?cpp|llama-server", re.IGNORECASE),
    re.compile(r"koboldcpp|text-generation-webui|oobabooga|localai", re.IGNORECASE),
    re.compile(r"ollama", re.IGNORECASE),
]


class OllamaClient:
    def __init__(self, llm_status_provider: Callable[[], dict[str, Any]] | None = None) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", "").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "default").strip()
        self.timeout_seconds = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "30"))
        self.enabled = os.getenv("OLLAMA_ENABLED", "true").lower() in {"1", "true", "yes"} and bool(
            self.base_url
        )
        # Lets the client discover other running inference engines (vLLM, llama.cpp, ...)
        # on the same host when the configured one is down. Wired to
        # MCPTools.get_llm_inference_status by the caller.
        self.llm_status_provider = llm_status_provider

    def suggest(self, payload: dict[str, Any]) -> dict[str, str]:
        request_body = self._build_request_body(payload)

        if self.enabled:
            result = self._call(self.base_url, request_body)
            if result["status"] == "ok":
                return result

        return self._suggest_via_fallback(request_body)

    def _suggest_via_fallback(self, request_body: dict[str, Any]) -> dict[str, str]:
        if self.llm_status_provider is None or not self.base_url:
            return {"status": "disabled" if not self.enabled else "error", "content": ""}

        primary_port = urlparse(self.base_url).port
        for engine, port in self._ranked_fallback_engines(exclude_port=primary_port):
            candidate_url = self._with_port(self.base_url, port)
            result = self._call(candidate_url, request_body)
            if result["status"] == "ok":
                result["status"] = f"fallback:{engine.get('name', candidate_url)}"
                return result

        return {
            "status": "disabled" if not self.enabled else "error",
            "content": "Skonfigurowany model LLM jest niedostepny, a zadna inna wykryta aplikacja "
            "do inferencji (vLLM/Ollama/llama.cpp/...) nie odpowiedziala.",
        }

    def _ranked_fallback_engines(self, exclude_port: int | None) -> list[tuple[dict, int]]:
        status = self.llm_status_provider()
        engines = status.get("result", {}).get("engines", []) if status.get("ok") else []

        candidates: list[tuple[dict, int]] = []
        for engine in engines:
            if not engine.get("running"):
                continue
            port = self._public_port(engine, exclude_port)
            if port is not None:
                candidates.append((engine, port))

        def rank(item: tuple[dict, int]) -> int:
            engine, _ = item
            haystack = f"{engine.get('name', '')} {engine.get('image', '')}"
            for index, pattern in enumerate(ENGINE_FALLBACK_PRIORITY):
                if pattern.search(haystack):
                    return index
            return len(ENGINE_FALLBACK_PRIORITY)

        return sorted(candidates, key=rank)

    @staticmethod
    def _public_port(engine: dict, exclude_port: int | None) -> int | None:
        for entry in engine.get("ports", "").split(","):
            public_port = entry.strip().split(":", 1)[0]
            if public_port.isdigit() and int(public_port) != exclude_port:
                return int(public_port)
        return None

    @staticmethod
    def _with_port(base_url: str, port: int) -> str:
        parsed = urlparse(base_url)
        return urlunparse(parsed._replace(netloc=f"{parsed.hostname}:{port}"))

    def _call(self, base_url: str, request_body: dict[str, Any]) -> dict[str, str]:
        req = urllib.request.Request(
            f"{base_url}/v1/chat/completions",
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

    def _build_request_body(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = self._build_prompt(payload)
        return {
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
