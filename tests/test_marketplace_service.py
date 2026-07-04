import sys
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_marketplace_gallery_adds_safe_local_import_plan(tmp_path):
    from services.marketplace_service import marketplace_gallery

    bundle = tmp_path / "output" / "releases" / "hero.spriteforge"
    bundle.parent.mkdir(parents=True)
    bundle.write_bytes(b"bundle")

    gallery = marketplace_gallery(tmp_path)
    entry = gallery["entries"][0]
    plan = entry["import_plan"]

    assert gallery["schema"] == "spriteforge_marketplace.v1"
    assert plan["ok"] is True
    assert plan["importable"] is True
    assert plan["mode"] == "local"
    assert plan["source_path"].endswith("hero.spriteforge")
    assert "/projects/imports/" in plan["target_path"].replace("\\", "/")
    assert plan["sha256"] == hashlib.sha256(b"bundle").hexdigest()
    assert entry["sha256"] == plan["sha256"]


def test_marketplace_import_plan_rejects_workspace_escape(tmp_path):
    from services.marketplace_service import plan_marketplace_import

    outside = tmp_path.parent / "evil.spriteforge"
    outside.write_bytes(b"evil")

    plan = plan_marketplace_import(tmp_path, {
        "id": "evil",
        "bundle_url": "/file/../evil.spriteforge",
    })

    assert plan["ok"] is False
    assert plan["importable"] is False


def test_marketplace_import_plan_treats_remote_as_explicit_download(tmp_path):
    from services.marketplace_service import plan_marketplace_import

    plan = plan_marketplace_import(tmp_path, {
        "id": "remote",
        "bundle_url": "https://example.com/remote.spriteforge",
    })

    assert plan["ok"] is True
    assert plan["importable"] is False
    assert plan["mode"] == "remote"


def test_marketplace_share_manifest_is_non_destructive(tmp_path):
    from services.plugin_manager import PLUGIN_SDK_VERSION
    from services.marketplace_service import build_marketplace_share_manifest

    bundle = tmp_path / "output" / "releases" / "hero.spriteforge"
    bundle.parent.mkdir(parents=True)
    bundle.write_bytes(b"bundle")

    manifest = build_marketplace_share_manifest(
        tmp_path,
        bundle_paths=["output/releases/hero.spriteforge"],
        author="Doc",
        license_name="private-review",
    )

    assert manifest["schema"] == "spriteforge_marketplace_share.v1"
    assert manifest["compatibility"]["schema"] == "spriteforge.marketplace_share_compatibility.v1"
    assert manifest["compatibility"]["plugin_sdk_version"] == PLUGIN_SDK_VERSION
    assert manifest["non_destructive"] is True
    assert manifest["upload_performed"] is False
    assert manifest["entry_count"] == 1
    assert manifest["entries"][0]["author"] == "Doc"
    assert manifest["entries"][0]["license"] == "private-review"
    assert manifest["entries"][0]["bundle_url"] == "/file/output/releases/hero.spriteforge"
    assert manifest["entries"][0]["sha256"] == hashlib.sha256(b"bundle").hexdigest()
    assert manifest["entries"][0]["compatibility"]["plugin_sdk_version"] == PLUGIN_SDK_VERSION
    checks = manifest["entries"][0]["share_checks"]
    assert checks["workspace_safe"] is True
    assert checks["bundle_exists"] is True
    assert checks["license_declared"] is True
    assert checks["local_import_plan_ok"] is True
    assert checks["sha256_present"] is True
    assert checks["compatibility_declared"] is True
    assert manifest["entries"][0]["import_plan"]["importable"] is True


def test_marketplace_import_copies_verified_local_bundle(tmp_path):
    from services.marketplace_service import import_marketplace_bundle

    bundle = tmp_path / "output" / "releases" / "hero.spriteforge"
    bundle.parent.mkdir(parents=True)
    bundle.write_bytes(b"bundle")

    result = import_marketplace_bundle(tmp_path, {
        "id": "hero",
        "bundle_url": "/file/output/releases/hero.spriteforge",
    })

    assert result["ok"] is True
    assert result["imported"] is True
    assert Path(result["target_path"]).read_bytes() == b"bundle"
    assert "/projects/imports/hero.spriteforge" in result["target_path"].replace("\\", "/")
