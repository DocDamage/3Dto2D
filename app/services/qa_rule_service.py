"""Shared rule registry and cacheable, machine-readable QA reports."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional

from services.asset_repository_service import AssetRepositoryService
from services.roadmap_models import QA_REPORT_SCHEMA, utc_now


RuleEvaluator = Callable[[Dict[str, Any]], List[Dict[str, Any]]]


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    category: str
    default_severity: str
    title: str
    explanation: str
    evaluator: RuleEvaluator


class QARuleRegistry:
    def __init__(self):
        self._rules: Dict[str, RuleDefinition] = {}

    def register(self, rule: RuleDefinition) -> None:
        if rule.default_severity not in {"info", "warning", "error"}:
            raise ValueError("QA rule severity must be info, warning, or error")
        if rule.rule_id in self._rules:
            raise ValueError(f"Duplicate QA rule ID: {rule.rule_id}")
        self._rules[rule.rule_id] = rule

    def describe(self) -> List[Dict[str, str]]:
        return [{key: value for key, value in asdict(rule).items() if key != "evaluator"} for rule in self._rules.values()]

    def evaluate(self, revision: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        config = config or {}
        findings: List[Dict[str, Any]] = []
        disabled = set(config.get("disabled_rules", []))
        severities = config.get("severities", {}) if isinstance(config.get("severities", {}), dict) else {}
        for rule in self._rules.values():
            if rule.rule_id in disabled:
                continue
            for finding in rule.evaluator(revision):
                item = dict(finding)
                item.setdefault("finding_id", f"finding_{uuid.uuid4().hex}")
                item["rule_id"] = rule.rule_id
                item.setdefault("category", rule.category)
                item.setdefault("severity", severities.get(rule.rule_id, rule.default_severity))
                item.setdefault("explanation", rule.explanation)
                item.setdefault("location", {"property": "metadata"})
                findings.append(item)
        counts = {severity: sum(1 for item in findings if item["severity"] == severity) for severity in ("error", "warning", "info")}
        return {
            "schema": QA_REPORT_SCHEMA, "schema_version": 1, "revision_id": revision["revision_id"],
            "created_at": utc_now(), "findings": findings, "summary": counts, "passed": counts["error"] == 0,
        }


def _dimensions(revision: Dict[str, Any]) -> List[Dict[str, Any]]:
    dimensions = revision.get("metadata", {}).get("dimensions")
    if dimensions is None:
        return [{"message": "Sprite dimensions are not recorded.", "location": {"property": "metadata.dimensions"}}]
    if (not isinstance(dimensions, dict) or not isinstance(dimensions.get("width"), int)
            or not isinstance(dimensions.get("height"), int) or dimensions.get("width", 0) <= 0 or dimensions.get("height", 0) <= 0):
        return [{"message": "Sprite dimensions must contain positive integer width and height.", "location": {"property": "metadata.dimensions"}}]
    return []


def _files(revision: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [] if revision.get("files") else [{"message": "Revision has no generated files.", "location": {"property": "files"}}]


DEFAULT_QA_REGISTRY = QARuleRegistry()
DEFAULT_QA_REGISTRY.register(RuleDefinition(
    "structure.dimensions", "structure", "error", "Valid dimensions",
    "Dimensions are required for sheet layout and engine export.", _dimensions,
))
DEFAULT_QA_REGISTRY.register(RuleDefinition(
    "export.generated_files", "export", "error", "Generated files present",
    "At least one immutable file is required before export.", _files,
))


class QAService:
    def __init__(self, repository: AssetRepositoryService, registry: QARuleRegistry = DEFAULT_QA_REGISTRY):
        self.repository = repository
        self.registry = registry

    def validate_revision(self, revision_id: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        revision = self.repository.get_revision(revision_id)
        input_hash = hashlib.sha256(json.dumps(
            {"revision": revision, "config": config or {}, "rules": self.registry.describe()},
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        with self.repository._connect() as connection:
            cached = connection.execute(
                "SELECT payload_json FROM qa_reports WHERE revision_id=? AND input_hash=?", (revision_id, input_hash)
            ).fetchone()
        if cached:
            report = json.loads(cached["payload_json"])
            report["cached"] = True
            return report
        report = self.registry.evaluate(revision, config)
        report["input_hash"] = input_hash
        report["cached"] = False
        with self.repository._connect() as connection:
            connection.execute(
                "INSERT INTO qa_reports(report_id,revision_id,input_hash,payload_json,created_at) VALUES(?,?,?,?,?)",
                (f"qa_{uuid.uuid4().hex}", revision_id, input_hash, json.dumps(report, sort_keys=True), report["created_at"]),
            )
        return report
