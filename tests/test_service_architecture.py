import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SERVICES = ROOT / "app" / "services"


def test_service_architecture_manifest_references_existing_files():
    manifest = json.loads((SERVICES / "service_architecture.json").read_text(encoding="utf-8"))

    assert manifest["schema"] == "spriteforge.service_architecture.v1"
    assert manifest["domains"]
    for domain in manifest["domains"]:
        assert domain["name"]
        assert domain["files"]
        for filename in domain["files"]:
            assert (SERVICES / filename).is_file(), filename


def test_service_architecture_has_unique_domain_membership_for_core_files():
    manifest = json.loads((SERVICES / "service_architecture.json").read_text(encoding="utf-8"))
    membership: dict[str, list[str]] = {}
    for domain in manifest["domains"]:
        for filename in domain["files"]:
            membership.setdefault(filename, []).append(domain["name"])

    duplicates = {
        filename: domains
        for filename, domains in membership.items()
        if len(domains) > 1
    }

    assert duplicates == {}
    for required in [
        "job_service.py",
        "sprite_processing_pipeline.py",
        "project_service.py",
        "lora_training_service.py",
        "web_helpers_cmd.py",
        "database_service.py",
    ]:
        assert required in membership
