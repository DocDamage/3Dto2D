from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Dict

from spriteforge_utils import audit_dir_exclusions, is_release_excluded, safe_name


MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 5_000
MAX_MEMBER_BYTES = 200 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
MAX_MANIFEST_BYTES = 1024 * 1024


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def resolve_project_directory(root: Path, projects_dir: Path, requested: str | Path) -> Path:
    raw = Path(requested)
    candidate = raw if raw.is_absolute() else root / raw
    resolved = candidate.resolve()
    if resolved.is_file():
        if resolved.name != "spriteforge_project.json":
            raise ValueError("Project path must reference a project directory or spriteforge_project.json.")
        resolved = resolved.parent
    projects_root = projects_dir.resolve()
    if resolved == projects_root or not _is_relative_to(resolved, projects_root):
        raise ValueError("Project path must stay inside the configured projects directory.")
    if not resolved.is_dir() or not (resolved / "spriteforge_project.json").is_file():
        raise FileNotFoundError("A valid SpriteForge project directory was not found.")
    return resolved


def export_project_bundle(project_dir: Path, releases_dir: Path) -> Dict[str, Any]:
    releases_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = releases_dir / f"{safe_name(project_dir.name)}.spriteforge"
    temp_path = bundle_path.with_name(f".{bundle_path.name}.{uuid.uuid4().hex}.tmp")
    violations = audit_dir_exclusions(project_dir)
    try:
        with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for file_path in sorted(project_dir.rglob("*")):
                if file_path.is_file() and not is_release_excluded(file_path, project_dir):
                    archive.write(file_path, file_path.relative_to(project_dir).as_posix())
        os.replace(temp_path, bundle_path)
    finally:
        temp_path.unlink(missing_ok=True)
    return {"bundle_path": bundle_path, "excluded": violations}


def _safe_member_path(name: str) -> PurePosixPath:
    normalized = str(name or "").replace("\\", "/")
    member = PurePosixPath(normalized)
    if not normalized or not member.parts or member.is_absolute() or ".." in member.parts:
        raise ValueError(f"Unsafe archive member path: {name!r}")
    if any(not part or ":" in part for part in member.parts):
        raise ValueError(f"Unsafe archive member path: {name!r}")
    return member


def _validate_archive(archive: zipfile.ZipFile) -> Dict[str, Any]:
    members = archive.infolist()
    if not members or len(members) > MAX_ARCHIVE_MEMBERS:
        raise ValueError("Project bundle has an invalid number of files.")
    total_size = 0
    names = set()
    for info in members:
        member = _safe_member_path(info.filename)
        canonical_name = member.as_posix().rstrip("/")
        if canonical_name in names:
            raise ValueError(f"Project bundle contains a duplicate member: {canonical_name}")
        names.add(canonical_name)
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            raise ValueError("Project bundles may not contain symbolic links.")
        if info.flag_bits & 0x1:
            raise ValueError("Encrypted project bundles are not supported.")
        if info.file_size > MAX_MEMBER_BYTES:
            raise ValueError(f"Project bundle member is too large: {info.filename}")
        total_size += info.file_size
        if total_size > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("Project bundle expands beyond the allowed size.")
        if info.file_size and info.compress_size == 0:
            raise ValueError("Project bundle contains an invalid compressed member.")
        if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            raise ValueError("Project bundle contains a suspicious compression ratio.")
    if "spriteforge_project.json" not in names:
        raise ValueError("Invalid bundle: missing spriteforge_project.json at the archive root.")
    manifest_info = archive.getinfo("spriteforge_project.json")
    if manifest_info.file_size > MAX_MANIFEST_BYTES:
        raise ValueError("Project manifest is too large.")
    manifest = json.loads(archive.read(manifest_info).decode("utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Project manifest must be a JSON object.")
    return manifest


def _unique_destination(projects_dir: Path, project_name: str) -> Path:
    base_name = safe_name(project_name)
    candidate = projects_dir / base_name
    suffix = 2
    while candidate.exists():
        candidate = projects_dir / f"{base_name}_{suffix}"
        suffix += 1
    return candidate


def import_project_bundle(file_stream: BinaryIO, filename: str, projects_dir: Path) -> Dict[str, Any]:
    projects_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = projects_dir / f".import_{uuid.uuid4().hex}"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="spriteforge_import_", suffix=".zip", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            shutil.copyfileobj(file_stream, temp_file, length=1024 * 1024)
        if temp_path.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ValueError("Project bundle exceeds the 100 MB upload limit.")
        with zipfile.ZipFile(temp_path, "r") as archive:
            manifest = _validate_archive(archive)
            project_name = safe_name(str(manifest.get("name") or Path(filename).stem))
            destination = _unique_destination(projects_dir, project_name)
            staging_dir.mkdir(parents=True, exist_ok=False)
            for info in archive.infolist():
                member = _safe_member_path(info.filename)
                target = staging_dir.joinpath(*member.parts)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
            if not (staging_dir / "spriteforge_project.json").is_file():
                raise ValueError("Extracted project manifest is missing.")
            os.replace(staging_dir, destination)
        return {"project_dir": destination, "manifest": manifest}
    except zipfile.BadZipFile as exc:
        raise ValueError("Project bundle is not a valid ZIP archive.") from exc
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
