"""Canonical, versioned records shared by roadmap services and API routes."""
from __future__ import annotations

import copy
import datetime as dt
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


PROJECT_SCHEMA = "spriteforge.project.v2"
ASSET_SCHEMA = "spriteforge.asset.v1"
REVISION_SCHEMA = "spriteforge.asset_revision.v1"
OPERATION_SCHEMA = "spriteforge.edit_operation.v1"
QA_REPORT_SCHEMA = "spriteforge.qa_report.v1"


class RecordValidationError(ValueError):
    """Raised when a persisted or API record is structurally invalid."""

    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}" if path else message)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _text(data: Dict[str, Any], key: str, *, required: bool = False) -> str:
    value = data.get(key, "")
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise RecordValidationError(key, "must be a string")
    value = value.strip()
    if required and not value:
        raise RecordValidationError(key, "is required")
    return value


def _string_list(data: Dict[str, Any], key: str) -> List[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RecordValidationError(key, "must be a list of strings")
    return list(value)


@dataclass(frozen=True)
class EditOperation:
    operation_id: str
    kind: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    schema: str = OPERATION_SCHEMA

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EditOperation":
        if not isinstance(data, dict):
            raise RecordValidationError("operations", "each operation must be an object")
        params = data.get("parameters", {})
        if not isinstance(params, dict):
            raise RecordValidationError("operations.parameters", "must be an object")
        enabled = data.get("enabled", True)
        if not isinstance(enabled, bool):
            raise RecordValidationError("operations.enabled", "must be a boolean")
        return cls(
            operation_id=_text(data, "operation_id", required=True),
            kind=_text(data, "kind", required=True),
            parameters=copy.deepcopy(params),
            enabled=enabled,
        )


@dataclass(frozen=True)
class AssetRevisionRecord:
    revision_id: str
    asset_id: str
    project_id: str
    parent_revision_id: Optional[str] = None
    source_asset_ids: List[str] = field(default_factory=list)
    generation: Dict[str, Any] = field(default_factory=dict)
    operations: List[EditOperation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    files: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    application_version: str = ""
    schema: str = REVISION_SCHEMA
    schema_version: int = 1

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssetRevisionRecord":
        if not isinstance(data, dict):
            raise RecordValidationError("", "asset revision must be an object")
        generation = data.get("generation", {})
        metadata = data.get("metadata", {})
        files = data.get("files", [])
        if not isinstance(generation, dict):
            raise RecordValidationError("generation", "must be an object")
        if not isinstance(metadata, dict):
            raise RecordValidationError("metadata", "must be an object")
        if not isinstance(files, list) or any(not isinstance(item, dict) for item in files):
            raise RecordValidationError("files", "must be a list of objects")
        operations = data.get("operations", [])
        if not isinstance(operations, list):
            raise RecordValidationError("operations", "must be a list")
        parent = data.get("parent_revision_id")
        if parent is not None and not isinstance(parent, str):
            raise RecordValidationError("parent_revision_id", "must be a string or null")
        return cls(
            revision_id=_text(data, "revision_id", required=True),
            asset_id=_text(data, "asset_id", required=True),
            project_id=_text(data, "project_id", required=True),
            parent_revision_id=parent or None,
            source_asset_ids=_string_list(data, "source_asset_ids"),
            generation=copy.deepcopy(generation),
            operations=[EditOperation.from_dict(item) for item in operations],
            metadata=copy.deepcopy(metadata),
            files=copy.deepcopy(files),
            created_at=_text(data, "created_at") or utc_now(),
            application_version=_text(data, "application_version"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AssetRecord:
    asset_id: str
    project_id: str
    name: str
    asset_type: str
    current_revision_id: Optional[str] = None
    role: str = ""
    action: str = ""
    direction: str = ""
    variant: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    schema: str = ASSET_SCHEMA
    schema_version: int = 1

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssetRecord":
        if not isinstance(data, dict):
            raise RecordValidationError("", "asset must be an object")
        current = data.get("current_revision_id")
        if current is not None and not isinstance(current, str):
            raise RecordValidationError("current_revision_id", "must be a string or null")
        return cls(
            asset_id=_text(data, "asset_id", required=True),
            project_id=_text(data, "project_id", required=True),
            name=_text(data, "name", required=True),
            asset_type=_text(data, "asset_type", required=True),
            current_revision_id=current or None,
            role=_text(data, "role"), action=_text(data, "action"),
            direction=_text(data, "direction"), variant=_text(data, "variant"),
            created_at=_text(data, "created_at") or utc_now(),
            updated_at=_text(data, "updated_at") or utc_now(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def migrate_project_manifest(data: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    """Upgrade legacy manifests in memory without removing legacy fields."""
    if not isinstance(data, dict):
        raise RecordValidationError("", "project manifest must be an object")
    migrated = copy.deepcopy(data)
    changed = migrated.get("schema") != PROJECT_SCHEMA or migrated.get("schema_version") != 2
    migrated["schema"] = PROJECT_SCHEMA
    migrated["schema_version"] = 2
    migrated.setdefault("project_id", str(migrated.get("name") or "").strip())
    migrated.setdefault("feature_flags", {})
    migrated.setdefault("style_profile_revision", None)
    if not migrated["project_id"]:
        raise RecordValidationError("project_id", "could not be inferred from name")
    return migrated, changed
