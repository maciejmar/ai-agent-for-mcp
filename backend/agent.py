from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from mcp_tools import MCPTools


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ErrorKind(StrEnum):
    RUNTIME = "runtime"
    CONFIGURATION = "configuration"
    RESOURCE = "resource"
    NETWORK = "network"
    UNKNOWN = "unknown"


class DiagnosticFinding(TypedDict):
    severity: str
    kind: str
    title: str
    evidence: list[str]
    requires_restart: bool


class Recommendation(TypedDict):
    title: str
    action: str
    priority: str


class AgentState(TypedDict):
    requested_log_path: NotRequired[str | None]
    log_snapshot: NotRequired[dict[str, Any]]
    resource_snapshot: NotRequired[dict[str, Any]]
    findings: NotRequired[list[DiagnosticFinding]]
    recommendations: NotRequired[list[Recommendation]]
    graph_status: NotRequired[str]
    current_step: NotRequired[str]
    steps: NotRequired[list[dict[str, str]]]


CONFIG_PATTERNS = [
    re.compile(r"missing|required|undefined|null value", re.IGNORECASE),
    re.compile(r"\b(config|configuration|\.env|environment variable|env var)\b", re.IGNORECASE),
    re.compile(r"invalid.*(setting|config|url|dsn|host|port)", re.IGNORECASE),
]

CRITICAL_PATTERNS = [
    re.compile(r"\b(CRITICAL|FATAL|panic|segmentation fault)\b", re.IGNORECASE),
    re.compile(r"out of memory|oom|killed process", re.IGNORECASE),
    re.compile(r"database.*(unavailable|corrupt)|cannot start|startup failed", re.IGNORECASE),
]

NETWORK_PATTERNS = [
    re.compile(r"connection refused|connection reset|timeout|timed out", re.IGNORECASE),
    re.compile(r"dns|name resolution|no route to host|network unreachable", re.IGNORECASE),
]

RESOURCE_PATTERNS = [
    re.compile(r"no space left|disk full|high cpu|cpu usage|memory usage", re.IGNORECASE),
    re.compile(r"too many open files|file descriptor", re.IGNORECASE),
]


def build_diagnostic_graph(mcp_tools: MCPTools | None = None):
    tools = mcp_tools or MCPTools.from_env()
    graph = StateGraph(AgentState)

    def fetch_logs(state: AgentState) -> dict[str, Any]:
        log_snapshot = tools.read_filtered_logs(state.get("requested_log_path"))
        resource_snapshot = tools.check_resources()
        return {
            "log_snapshot": log_snapshot,
            "resource_snapshot": resource_snapshot,
            "current_step": "fetch_logs",
            "graph_status": "logs_and_metrics_collected",
            "steps": _append_step(state, "fetch_logs", "completed"),
        }

    def analyze(state: AgentState) -> dict[str, Any]:
        lines = state.get("log_snapshot", {}).get("lines", [])
        findings = _analyze_lines(lines)
        findings.extend(_analyze_resources(state.get("resource_snapshot", {})))

        if not findings:
            findings.append(
                {
                    "severity": Severity.INFO,
                    "kind": ErrorKind.UNKNOWN,
                    "title": "No high-signal errors found in filtered logs",
                    "evidence": ["MCP filtering found no critical, warning, or configuration lines."],
                    "requires_restart": False,
                }
            )

        return {
            "findings": findings,
            "current_step": "analyze",
            "graph_status": "analysis_completed",
            "steps": _append_step(state, "analyze", "completed"),
        }

    def suggest_fixes(state: AgentState) -> dict[str, Any]:
        recommendations = _recommend(state.get("findings", []))
        return {
            "recommendations": recommendations,
            "current_step": "suggest_fixes",
            "graph_status": "completed",
            "steps": _append_step(state, "suggest_fixes", "completed"),
        }

    graph.add_node("fetch_logs", fetch_logs)
    graph.add_node("analyze", analyze)
    graph.add_node("suggest_fixes", suggest_fixes)
    graph.add_edge(START, "fetch_logs")
    graph.add_edge("fetch_logs", "analyze")
    graph.add_edge("analyze", "suggest_fixes")
    graph.add_edge("suggest_fixes", END)
    return graph.compile()


diagnostic_graph = build_diagnostic_graph()


def run_diagnostics(requested_log_path: str | None = None) -> AgentState:
    initial_state: AgentState = {
        "requested_log_path": requested_log_path,
        "graph_status": "started",
        "current_step": "start",
        "steps": [{"name": "start", "status": "completed"}],
    }
    return diagnostic_graph.invoke(initial_state)


def stream_diagnostics(requested_log_path: str | None = None):
    initial_state: AgentState = {
        "requested_log_path": requested_log_path,
        "graph_status": "started",
        "current_step": "start",
        "steps": [{"name": "start", "status": "completed"}],
    }
    yield from diagnostic_graph.stream(initial_state, stream_mode="values")


def _append_step(state: AgentState, name: str, status: str) -> list[dict[str, str]]:
    steps = list(state.get("steps", []))
    steps.append({"name": name, "status": status})
    return steps


def _analyze_lines(lines: list[str]) -> list[DiagnosticFinding]:
    grouped: dict[tuple[Severity, ErrorKind, str], list[str]] = {}
    for line in lines:
        severity = _severity_for_line(line)
        kind = _kind_for_line(line)
        title = _title_for(severity, kind)
        grouped.setdefault((severity, kind, title), []).append(line)

    findings: list[DiagnosticFinding] = []
    for (severity, kind, title), evidence in grouped.items():
        findings.append(
            {
                "severity": severity,
                "kind": kind,
                "title": title,
                "evidence": evidence[:5],
                "requires_restart": _requires_restart(severity, kind, evidence),
            }
        )
    return findings


def _analyze_resources(resources: dict[str, Any]) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    disk_output = resources.get("disk", {}).get("output", "")
    if re.search(r"\b(9[0-9]|100)%", disk_output):
        findings.append(
            {
                "severity": Severity.CRITICAL,
                "kind": ErrorKind.RESOURCE,
                "title": "Disk usage is critically high",
                "evidence": disk_output.splitlines()[:5],
                "requires_restart": False,
            }
        )
    return findings


def _severity_for_line(line: str) -> Severity:
    if any(pattern.search(line) for pattern in CRITICAL_PATTERNS):
        return Severity.CRITICAL
    if re.search(r"\b(ERROR|WARN|WARNING)\b", line, re.IGNORECASE):
        return Severity.WARNING
    return Severity.INFO


def _kind_for_line(line: str) -> ErrorKind:
    if any(pattern.search(line) for pattern in CONFIG_PATTERNS):
        return ErrorKind.CONFIGURATION
    if any(pattern.search(line) for pattern in RESOURCE_PATTERNS):
        return ErrorKind.RESOURCE
    if any(pattern.search(line) for pattern in NETWORK_PATTERNS):
        return ErrorKind.NETWORK
    if any(pattern.search(line) for pattern in CRITICAL_PATTERNS):
        return ErrorKind.RUNTIME
    return ErrorKind.UNKNOWN


def _title_for(severity: Severity, kind: ErrorKind) -> str:
    if kind == ErrorKind.CONFIGURATION:
        return "Configuration error detected"
    if kind == ErrorKind.RESOURCE:
        return "Resource pressure detected"
    if kind == ErrorKind.NETWORK:
        return "Network or dependency connectivity issue"
    if severity == Severity.CRITICAL:
        return "Critical runtime failure detected"
    return "Application warning detected"


def _requires_restart(severity: Severity, kind: ErrorKind, evidence: list[str]) -> bool:
    joined = "\n".join(evidence)
    if kind == ErrorKind.CONFIGURATION:
        return False
    if kind == ErrorKind.RESOURCE and re.search(r"out of memory|oom|too many open files", joined, re.IGNORECASE):
        return True
    return severity == Severity.CRITICAL


def _recommend(findings: list[DiagnosticFinding]) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    for finding in findings:
        kind = finding["kind"]
        if kind == ErrorKind.CONFIGURATION:
            recommendations.append(
                {
                    "title": "Correct configuration before restarting",
                    "action": "Check .env/config values referenced in the evidence, validate required variables, then reload the application configuration.",
                    "priority": "high",
                }
            )
        elif kind == ErrorKind.RESOURCE:
            recommendations.append(
                {
                    "title": "Reduce resource pressure",
                    "action": "Free disk or memory, inspect the heaviest processes, and rotate logs before restarting services.",
                    "priority": "critical" if finding["severity"] == Severity.CRITICAL else "high",
                }
            )
        elif kind == ErrorKind.NETWORK:
            recommendations.append(
                {
                    "title": "Verify isolated-network dependencies",
                    "action": "Check firewall/Tufin rules, DNS resolution, target port availability, and service allowlists for the failing dependency.",
                    "priority": "high",
                }
            )
        elif finding["requires_restart"]:
            recommendations.append(
                {
                    "title": "Restart after preserving evidence",
                    "action": "Capture recent logs and metrics, restart the affected service, then rerun diagnostics to confirm recovery.",
                    "priority": "critical",
                }
            )
        else:
            recommendations.append(
                {
                    "title": "Monitor and gather more context",
                    "action": "Keep the filtered evidence, increase application logging for the affected module, and rerun diagnostics after the next event.",
                    "priority": "medium",
                }
            )
    return _deduplicate_recommendations(recommendations)


def _deduplicate_recommendations(items: list[Recommendation]) -> list[Recommendation]:
    seen: set[str] = set()
    result: list[Recommendation] = []
    for item in items:
        if item["title"] in seen:
            continue
        seen.add(item["title"])
        result.append(item)
    return result
