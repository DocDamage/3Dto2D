"""CLI surface for canonical asset history and QA services."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from services.asset_repository_service import AssetRepositoryService
from services.project_service import ProjectService
from services.qa_rule_service import QAService
from services.distribution_service import DistributionService
from services.production_dashboard_service import ProductionDashboardService


def _repository(project: str) -> tuple[AssetRepositoryService, dict]:
    manifest_path = ProjectService.resolve_project_path(project)
    if not manifest_path:
        raise ValueError("--project must reference a valid SpriteForge project")
    return AssetRepositoryService(manifest_path.parent), ProjectService.load_manifest(manifest_path)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Manage reproducible SpriteForge assets")
    parser.add_argument("--project", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--name", required=True)
    create.add_argument("--type", default="sprite", dest="asset_type")
    create.add_argument("--role", default="")
    create.add_argument("--action", default="")
    create.add_argument("--direction", default="")
    create.add_argument("--variant", default="")
    commands.add_parser("list")
    history = commands.add_parser("history")
    history.add_argument("asset_id")
    validate = commands.add_parser("validate")
    validate.add_argument("revision_id")
    commands.add_parser("integrity")
    commands.add_parser("dashboard")
    commands.add_parser("snapshot")
    args = parser.parse_args(argv)
    repository, manifest = _repository(args.project)
    if args.command == "create":
        result = repository.new_asset(
            project_id=manifest["project_id"], name=args.name, asset_type=args.asset_type,
            role=args.role, action=args.action, direction=args.direction, variant=args.variant,
        )
    elif args.command == "list":
        result = repository.list_assets(manifest["project_id"])
    elif args.command == "history":
        result = repository.history(args.asset_id)
    elif args.command == "validate":
        result = QAService(repository).validate_revision(args.revision_id)
    elif args.command == "dashboard":
        result = ProductionDashboardService(repository, manifest).summary()
    elif args.command == "snapshot":
        result = DistributionService.snapshot(repository.project_dir)
    else:
        result = repository.verify_integrity()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not isinstance(result, dict) or result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
