"""Local observability, plugin permissions, SBOM, and release provenance."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List

from services.roadmap_models import utc_now
from spriteforge_utils import ROOT, save_json


ALLOWED_PLUGIN_PERMISSIONS = {"project.read", "project.write", "network", "process", "models.read", "ui.panel"}
SENSITIVE_IMPORTS = {"subprocess": "process", "socket": "network", "urllib": "network", "requests": "network", "httpx": "network"}


class LocalTelemetry:
    """Bounded local traces/metrics/log correlations with opt-in export semantics."""
    def __init__(self, path: Path | None = None, max_events: int = 20_000):
        self.path = Path(path or ROOT / "state" / "telemetry.jsonl")
        self.max_events = max(100, int(max_events))

    def emit(self, signal: str, name: str, *, value: float | None = None,
             attributes: Dict[str, Any] | None = None, trace_id: str = "", span_id: str = "") -> Dict[str, Any]:
        if signal not in {"trace", "metric", "log"}:
            raise ValueError("Telemetry signal must be trace, metric, or log")
        clean = self._attributes(attributes or {})
        event = {"schema": "spriteforge.telemetry.v1", "time": utc_now(), "signal": signal, "name": str(name)[:160], "attributes": clean}
        if value is not None: event["value"] = float(value)
        if trace_id: event["trace_id"] = trace_id
        if span_id: event["span_id"] = span_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")
        self._bound()
        return event

    @contextmanager
    def span(self, name: str, attributes: Dict[str, Any] | None = None, trace_id: str = "") -> Iterator[Dict[str, str]]:
        trace_id, span_id = trace_id or uuid.uuid4().hex, uuid.uuid4().hex[:16]
        started = time.perf_counter()
        context = {"trace_id": trace_id, "span_id": span_id}
        self.emit("trace", name + ".start", attributes=attributes, **context)
        try:
            yield context
            self.emit("trace", name + ".end", value=(time.perf_counter() - started) * 1000, attributes={**(attributes or {}), "status": "ok"}, **context)
        except Exception as exc:
            self.emit("trace", name + ".end", value=(time.perf_counter() - started) * 1000, attributes={**(attributes or {}), "status": "error", "error_type": type(exc).__name__}, **context)
            raise

    @staticmethod
    def _attributes(value: Dict[str, Any]) -> Dict[str, Any]:
        blocked = {"prompt", "image", "token", "secret", "password", "authorization", "signed_url"}
        result = {}
        for key, item in list(value.items())[:64]:
            if any(word in str(key).lower() for word in blocked):
                result[str(key)] = "[redacted]"
            elif isinstance(item, (str, int, float, bool)) or item is None:
                result[str(key)[:80]] = str(item)[:500] if isinstance(item, str) else item
        return result

    def _bound(self) -> None:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
            if len(lines) > self.max_events:
                self.path.write_text("\n".join(lines[-self.max_events:]) + "\n", encoding="utf-8")
        except OSError:
            pass


class PluginSecurityService:
    @staticmethod
    def inspect(entrypoint: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
        permissions = set(manifest.get("permissions", []))
        unknown = sorted(permissions - ALLOWED_PLUGIN_PERMISSIONS)
        issues = []
        if unknown:
            issues.append({"severity": "error", "code": "unknown_permissions", "permissions": unknown})
        try:
            tree = ast.parse(Path(entrypoint).read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as exc:
            return {"ok": False, "issues": [{"severity": "error", "code": "parse_failed", "message": str(exc)}]}
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module: imports.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec", "compile", "__import__"}:
                issues.append({"severity": "error", "code": "dynamic_code", "name": node.func.id})
        for module, permission in SENSITIVE_IMPORTS.items():
            if module in imports and permission not in permissions:
                issues.append({"severity": "error", "code": "permission_required", "module": module, "permission": permission})
        return {"schema": "spriteforge.plugin_security_report.v1", "ok": not any(item["severity"] == "error" for item in issues), "permissions": sorted(permissions), "imports": sorted(imports), "issues": issues}

    @staticmethod
    def run(entrypoint: Path, manifest: Dict[str, Any], payload: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        report = PluginSecurityService.inspect(entrypoint, manifest)
        if not report["ok"]:
            raise PermissionError("Plugin failed permission inspection")
        runner = (
            "import importlib.util,json,sys; p=sys.argv[1]; s=importlib.util.spec_from_file_location('plugin',p); "
            "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); data=json.load(sys.stdin); "
            "fn=getattr(m,data.pop('_hook')); print(json.dumps(fn(**data),default=str))"
        )
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8", "SPRITEFORGE_PLUGIN_SANDBOX": "1"}
        completed = subprocess.run(
            [sys.executable, "-I", "-c", runner, str(Path(entrypoint).resolve())],
            input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=max(1, min(120, int(timeout))),
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "Plugin process failed")
        return {"ok": True, "result": json.loads(completed.stdout or "null"), "security": report}


class SupplyChainService:
    @staticmethod
    def generate_sbom(requirements: Path, output: Path) -> Dict[str, Any]:
        components = []
        for line in Path(requirements).read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text or text.startswith("#") or "==" not in text: continue
            name, version = text.split("==", 1)
            components.append({"type": "library", "name": name, "version": version, "purl": f"pkg:pypi/{name.lower()}@{version}"})
        sbom = {"bomFormat": "CycloneDX", "specVersion": "1.5", "serialNumber": f"urn:uuid:{uuid.uuid4()}", "version": 1, "metadata": {"component": {"type": "application", "name": "SpriteForge Studio"}}, "components": sorted(components, key=lambda item: item["name"].lower())}
        save_json(Path(output), sbom)
        return sbom

    @staticmethod
    def build_provenance(artifacts: List[Path], *, source_revision: str, builder_id: str,
                         invocation: Dict[str, Any], output: Path) -> Dict[str, Any]:
        subjects = []
        for artifact in artifacts:
            digest = hashlib.sha256(Path(artifact).read_bytes()).hexdigest()
            subjects.append({"name": Path(artifact).name, "digest": {"sha256": digest}})
        provenance = {
            "_type": "https://in-toto.io/Statement/v1", "subject": subjects,
            "predicateType": "https://slsa.dev/provenance/v1",
            "predicate": {"buildDefinition": {"buildType": "https://spriteforge.local/build/windows/v1", "externalParameters": invocation, "resolvedDependencies": [{"uri": "git+local", "digest": {"gitCommit": source_revision}}]}, "runDetails": {"builder": {"id": builder_id}, "metadata": {"invocationId": uuid.uuid4().hex, "startedOn": utc_now()}}},
        }
        save_json(Path(output), provenance)
        return provenance
