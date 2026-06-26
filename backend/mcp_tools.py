from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from remote_mcp_client import RemoteMCPClient


SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(password|passwd|pwd|secret|token|api[_-]?key)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(authorization:\s*bearer)\s+\S+"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
]


NOISY_LOG_PATTERNS = [
    re.compile(r"\bDEBUG\b", re.IGNORECASE),
    re.compile(r"\bTRACE\b", re.IGNORECASE),
    re.compile(r"health(check)?", re.IGNORECASE),
]


SIGNAL_LOG_PATTERNS = [
    re.compile(r"\b(ERROR|CRITICAL|FATAL|WARN|WARNING)\b", re.IGNORECASE),
    re.compile(r"\b(exception|traceback|failed|timeout|refused|denied|oom|out of memory)\b", re.IGNORECASE),
    re.compile(r"\b(config|configuration|env|missing|required|invalid)\b", re.IGNORECASE),
]


@dataclass(frozen=True)
class CommandSpec:
    name: str
    args: tuple[str, ...] = ()


@dataclass
class MCPTools:
    """Small MCP-like tool boundary for an isolated diagnostic agent.

    The class intentionally exposes only read-only, allowlisted operations.
    Data is filtered and redacted before it can reach the graph or an LLM.
    """

    allowed_log_paths: list[Path] = field(default_factory=list)
    allowed_commands: dict[str, CommandSpec] = field(default_factory=dict)
    docker_log_containers: list[str] = field(default_factory=list)
    max_log_lines: int = 500
    command_timeout_seconds: int = 8
    remote_client: RemoteMCPClient = field(default_factory=RemoteMCPClient)

    @classmethod
    def from_env(cls) -> "MCPTools":
        log_paths = os.getenv("MCP_ALLOWED_LOG_PATHS", "/var/log/app.log,./sample_app.log")
        allowed_log_paths = [Path(item.strip()).resolve() for item in log_paths.split(",") if item.strip()]

        containers_str = os.getenv("DOCKER_LOG_CONTAINERS", "diagnostic-agent-backend,bgk-mcp-server")
        docker_log_containers = [c.strip() for c in containers_str.split(",") if c.strip()]

        return cls(
            allowed_log_paths=allowed_log_paths,
            docker_log_containers=docker_log_containers,
            allowed_commands={
                "disk": CommandSpec("df", ("-h",)),
                "top": CommandSpec("top", ("-b", "-n", "1")),
                "memory": CommandSpec("free", ("-m",)),
            },
        )

    def read_filtered_logs(self, requested_path: str | None = None) -> dict:
        # When no path given, read logs from all configured Docker containers
        if not requested_path and self.docker_log_containers:
            return self._read_docker_containers()

        remote_snapshot = self.remote_client.call_tool(
            "log_read_filtered",
            {"path": requested_path, "max_lines": self.max_log_lines},
        )
        if remote_snapshot.get("ok") and isinstance(remote_snapshot.get("result"), dict):
            result = remote_snapshot["result"]
            if not result.get("error"):
                result["source"] = "remote_mcp"
                return result

        path = self._resolve_allowed_path(requested_path)
        if path is None:
            return {
                "path": requested_path,
                "available_paths": [str(p) for p in self.allowed_log_paths],
                "lines": [],
                "error": "No allowed log file was found.",
                "remote_mcp_error": remote_snapshot.get("error") or remote_snapshot.get("result", {}).get("error"),
            }

        raw_lines = self._tail_lines(path, self.max_log_lines)
        filtered = list(self._filter_and_redact(raw_lines))
        return {
            "path": str(path),
            "lines": filtered,
            "raw_line_count": len(raw_lines),
            "filtered_line_count": len(filtered),
            "source": "local_fallback",
        }

    def _read_docker_containers(self) -> dict:
        all_lines: list[str] = []
        errors: list[str] = []
        per_container = max(1, self.max_log_lines // len(self.docker_log_containers))
        for container in self.docker_log_containers:
            snapshot = self.remote_client.call_tool(
                "log_read_filtered",
                {"path": f"docker://{container}", "max_lines": per_container},
            )
            if snapshot.get("ok") and isinstance(snapshot.get("result"), dict):
                result = snapshot["result"]
                if not result.get("error"):
                    all_lines.extend(
                        f"[{container}] {line}" for line in result.get("lines", [])
                    )
                else:
                    errors.append(f"{container}: {result['error']}")
            else:
                errors.append(f"{container}: {snapshot.get('error', 'connection failed')}")
        return {
            "path": "docker://" + ",".join(self.docker_log_containers),
            "lines": all_lines,
            "filtered_line_count": len(all_lines),
            "raw_line_count": len(all_lines),
            "source": "remote_mcp_docker",
            **({"errors": errors} if errors else {}),
        }

    def get_llm_inference_status(self) -> dict:
        inference_port = urlparse(os.getenv("OLLAMA_BASE_URL", "")).port
        return self.remote_client.call_tool("llm_inference_status", {"port": inference_port})

    def check_resources(self) -> dict[str, dict]:
        container_status = self.remote_client.call_tool("server_container_status", {})
        results: dict[str, dict] = {
            "remote_mcp": {
                "container_status": container_status,
                "gpu_status": self.remote_client.call_tool("server_gpu_status", {}),
                "ollama_models": self.remote_client.call_tool("ollama_list_models", {}),
                "system_info": self.remote_client.call_tool("server_system_info", {}),
                "disk_usage": self.remote_client.call_tool("docker_system_df", {}),
                "container_configs": self._inspect_all_containers(container_status),
            }
        }
        for alias in ("disk", "memory", "top"):
            results[alias] = self.run_safe_command(alias)
        return results

    def _inspect_all_containers(self, container_status: dict) -> dict:
        if not container_status.get("ok"):
            return {}
        containers = container_status.get("result", {}).get("containers", [])
        configs: dict = {}
        for c in containers[:15]:
            name = c.get("name", "")
            if not name:
                continue
            result = self.remote_client.call_tool("container_inspect", {"container_name": name})
            if result.get("ok"):
                configs[name] = result.get("result", {})
        return configs

    def run_safe_command(self, alias: str) -> dict:
        spec = self.allowed_commands.get(alias)
        if spec is None:
            return {"ok": False, "error": f"Command alias '{alias}' is not allowed."}

        try:
            completed = subprocess.run(
                [spec.name, *spec.args],
                capture_output=True,
                check=False,
                text=True,
                timeout=self.command_timeout_seconds,
            )
        except FileNotFoundError:
            return {"ok": False, "command": spec.name, "error": "Command is unavailable on this host."}
        except subprocess.TimeoutExpired:
            return {"ok": False, "command": spec.name, "error": "Command timed out."}

        output = completed.stdout if completed.stdout else completed.stderr
        return {
            "ok": completed.returncode == 0,
            "command": " ".join([spec.name, *spec.args]),
            "exit_code": completed.returncode,
            "output": self._redact(output)[:6000],
        }

    def _resolve_allowed_path(self, requested_path: str | None) -> Path | None:
        candidates = self.allowed_log_paths
        if requested_path:
            requested = Path(requested_path).resolve()
            candidates = [path for path in self.allowed_log_paths if path == requested]

        for path in candidates:
            if path.exists() and path.is_file():
                return path
        return None

    def _tail_lines(self, path: Path, limit: int) -> list[str]:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
        return [line.rstrip("\n") for line in lines[-limit:]]

    def _filter_and_redact(self, lines: Iterable[str]) -> Iterable[str]:
        for line in lines:
            if any(pattern.search(line) for pattern in NOISY_LOG_PATTERNS):
                continue
            if not any(pattern.search(line) for pattern in SIGNAL_LOG_PATTERNS):
                continue
            yield self._redact(line)

    def _redact(self, text: str) -> str:
        redacted = text
        for pattern in SENSITIVE_PATTERNS:
            redacted = pattern.sub(lambda match: self._mask_match(match.group(0)), redacted)
        return redacted

    @staticmethod
    def _mask_match(value: str) -> str:
        if ":" in value:
            key = value.split(":", 1)[0]
            return f"{key}: [REDACTED]"
        if "=" in value:
            key = value.split("=", 1)[0]
            return f"{key}=[REDACTED]"
        return "[REDACTED]"
