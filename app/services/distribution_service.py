"""Portable packaging, project snapshots, recovery, and update staging."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sys
import subprocess
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict

from services.project_bundle_service import export_project_bundle
from services.roadmap_models import utc_now
from spriteforge_utils import ROOT, get_app_version, save_json


class DistributionService:
    @staticmethod
    def version_report() -> Dict[str, Any]:
        return {
            "schema": "spriteforge.version_report.v1", "application": get_app_version(),
            "project_schema": 2, "asset_schema": 1, "workflow_schema": 1, "provider_adapter_schema": 1,
            "python": platform.python_version(), "platform": platform.platform(),
        }

    @staticmethod
    def snapshot(project_dir: Path) -> Dict[str, Any]:
        project_dir = Path(project_dir).resolve()
        snapshots = ROOT / "state" / "project_snapshots" / project_dir.name
        timestamp = utc_now().replace(":", "-")
        result = export_project_bundle(project_dir, snapshots)
        source = Path(result["bundle_path"])
        target = snapshots / f"snapshot_{timestamp}_{uuid.uuid4().hex[:8]}.spriteforge"
        os.replace(source, target)
        digest = DistributionService._hash(target)
        metadata = {"schema": "spriteforge.project_snapshot.v1", "created_at": utc_now(), "path": str(target), "sha256": digest, "size_bytes": target.stat().st_size}
        save_json(target.with_suffix(".json"), metadata)
        return metadata

    @staticmethod
    def recovery_candidates(project_dir: Path) -> list[Dict[str, Any]]:
        snapshots = ROOT / "state" / "project_snapshots" / Path(project_dir).resolve().name
        candidates = []
        for path in sorted(snapshots.glob("snapshot_*.spriteforge"), reverse=True) if snapshots.exists() else []:
            meta_path = path.with_suffix(".json")
            try:
                metadata = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            except (OSError, json.JSONDecodeError):
                metadata = {}
            actual = DistributionService._hash(path)
            candidates.append({**metadata, "path": str(path), "sha256": actual, "valid": not metadata.get("sha256") or metadata["sha256"] == actual})
        return candidates

    @staticmethod
    def stage_update(package: Path, manifest: Dict[str, Any], staging_root: Path | None = None) -> Dict[str, Any]:
        package = Path(package).resolve()
        if not package.is_file() or package.suffix.lower() != ".zip":
            raise ValueError("Update package must be a ZIP file")
        expected = str(manifest.get("sha256") or "").lower()
        actual = DistributionService._hash(package)
        if len(expected) != 64 or actual != expected:
            raise ValueError("Update package hash does not match the signed release manifest")
        version = str(manifest.get("version") or "").strip()
        if not version:
            raise ValueError("Update manifest version is required")
        staging_root = Path(staging_root or ROOT / "state" / "updates").resolve()
        target = staging_root / f"staged_{version}_{uuid.uuid4().hex[:8]}"
        target.mkdir(parents=True, exist_ok=False)
        try:
            with zipfile.ZipFile(package) as archive:
                for info in archive.infolist():
                    parts = Path(info.filename.replace("\\", "/")).parts
                    if info.filename.startswith(("/", "\\")) or ".." in parts or info.file_size > 500_000_000:
                        raise ValueError("Update package contains an unsafe member")
                archive.extractall(target)
            record = {"schema": "spriteforge.staged_update.v1", "version": version, "sha256": actual, "path": str(target), "staged_at": utc_now(), "status": "ready"}
            save_json(target / "staged_update.json", record)
            return record
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            raise

    @staticmethod
    def support_bundle(output: Path) -> Dict[str, Any]:
        output = Path(output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        preview = ["version_report.json"]
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("version_report.json", json.dumps(DistributionService.version_report(), indent=2))
        return {"schema": "spriteforge.support_bundle.v1", "path": str(output), "included": preview, "excluded": ["credentials", "source_images", "project_assets", "signed_urls"]}

    @staticmethod
    def apply_staged_update(staged_dir: Path, install_root: Path, *, health_command: list[str] | None = None) -> Dict[str, Any]:
        """Apply a verified staged update with file-level rollback on failed health checks.

        This is intended for the launcher after the web process has stopped.
        """
        staged_dir, install_root = Path(staged_dir).resolve(), Path(install_root).resolve()
        record_path = staged_dir / "staged_update.json"
        if not record_path.is_file():
            raise ValueError("Staged update record is missing")
        staged_record = json.loads(record_path.read_text(encoding="utf-8"))
        if staged_record.get("status") != "ready":
            raise ValueError("Update is not ready to apply")
        update_id = f"update_{staged_record['version']}_{uuid.uuid4().hex[:8]}"
        backup_root = install_root / "state" / "updates" / "backups" / update_id
        files = []
        excluded_roots = {"projects", "models", "output", "logs", "state", ".git", ".venv"}
        for source in sorted(staged_dir.rglob("*")):
            if not source.is_file() or source == record_path:
                continue
            relative = source.relative_to(staged_dir)
            if not relative.parts or relative.parts[0].lower() in excluded_roots or ".." in relative.parts:
                continue
            target = install_root / relative
            backup = backup_root / relative
            existed = target.is_file()
            if existed:
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.update")
            try:
                shutil.copy2(source, temporary)
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            files.append({"path": relative.as_posix(), "existed": existed})
        applied = {
            "schema": "spriteforge.applied_update.v1", "update_id": update_id,
            "version": staged_record["version"], "applied_at": utc_now(), "install_root": str(install_root),
            "backup_root": str(backup_root), "files": files, "status": "health_check",
        }
        backup_root.mkdir(parents=True, exist_ok=True)
        applied_path = backup_root / "applied_update.json"
        save_json(applied_path, applied)
        command = health_command or [sys.executable, "spriteforge_web.py", "--smoke"]
        try:
            completed = subprocess.run(command, cwd=str(install_root / "app"), capture_output=True, text=True, timeout=120)
            if completed.returncode != 0:
                raise RuntimeError((completed.stdout + "\n" + completed.stderr).strip() or "Update health check failed")
            applied["status"] = "healthy"
            applied["health_output"] = completed.stdout[-4000:]
            save_json(applied_path, applied)
            staged_record["status"] = "applied"
            save_json(record_path, staged_record)
            return applied
        except Exception:
            DistributionService.rollback_update(applied_path)
            raise

    @staticmethod
    def rollback_update(applied_record: Path) -> Dict[str, Any]:
        applied_record = Path(applied_record).resolve()
        record = json.loads(applied_record.read_text(encoding="utf-8"))
        install_root = Path(record["install_root"]).resolve()
        backup_root = Path(record["backup_root"]).resolve()
        for item in reversed(record.get("files", [])):
            relative = Path(item["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Rollback record contains an unsafe path")
            target, backup = install_root / relative, backup_root / relative
            if item.get("existed"):
                if not backup.is_file():
                    raise FileNotFoundError(f"Rollback backup is missing: {relative}")
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(backup, target)
            else:
                target.unlink(missing_ok=True)
        record["status"] = "rolled_back"
        record["rolled_back_at"] = utc_now()
        save_json(applied_record, record)
        return record

    @staticmethod
    def release_readiness(*, certificate_thumbprint: str = "", clean_machine_evidence: Path | None = None) -> Dict[str, Any]:
        """Executable release gates; never reports external checks as passed without evidence."""
        import shutil as _shutil
        iscc = _shutil.which("ISCC.exe")
        signtool = _shutil.which("signtool.exe")
        clean_evidence = Path(clean_machine_evidence).resolve() if clean_machine_evidence else None
        clean_ok = False
        if clean_evidence and clean_evidence.is_file():
            try:
                evidence = json.loads(clean_evidence.read_text(encoding="utf-8"))
                clean_ok = evidence.get("schema") == "spriteforge.clean_machine_test.v1" and evidence.get("passed") is True
            except (OSError, json.JSONDecodeError):
                clean_ok = False
        checks = {
            "inno_setup": {"ok": bool(iscc), "path": iscc or ""},
            "signing_tool": {"ok": bool(signtool), "path": signtool or ""},
            "signing_certificate": {"ok": bool(certificate_thumbprint), "thumbprint_suffix": certificate_thumbprint[-8:] if certificate_thumbprint else ""},
            "clean_machine_test": {"ok": clean_ok, "evidence": str(clean_evidence or "")},
        }
        return {"schema": "spriteforge.release_readiness.v1", "ok": all(item["ok"] for item in checks.values()), "checks": checks}

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
