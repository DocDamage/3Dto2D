# Packaging, updates, and recovery

Build the Windows portable package and Inno Setup installer from PowerShell:

```powershell
./packaging/windows/build_release.ps1 -Version 1.2.0 -PythonRuntimeZip C:\build\python-embed-amd64.zip -PythonRuntimeSha256 <verified-sha256>
```

Pass `-CertificateThumbprint` to sign the installer with SHA-256 and a trusted timestamp. The build intentionally excludes user projects, models, output, logs, caches, and runtime state. Uninstall therefore does not target those separately managed locations.

The runtime archive must be the official Windows embeddable Python package and its SHA-256 must be supplied independently. The build verifies the archive, installs locked dependencies into `runtime/Lib/site-packages`, enables `site`, and runs the bundled interpreter smoke test before producing either artifact. The launcher always prefers this runtime and does not require system Python.

The build emits `release-manifest.json` containing SHA-256 hashes. `DistributionService.stage_update` refuses packages that do not match the selected release manifest and extracts only after archive path validation. Applying a staged update remains a user-controlled launcher action so a running application is never replaced in place.

Project snapshots are created outside the project tree under managed state storage, preventing recursive snapshot inclusion. Every snapshot has a SHA-256 sidecar and appears in the Production Studio recovery list only with its integrity status.

Support bundles preview their included files and exclude credentials, signed URLs, project assets, and source images by default.

Run `packaging/windows/test_clean_machine.ps1` inside a disposable clean Windows VM. Its evidence JSON is required by the release-readiness gate; the gate cannot be bypassed by merely claiming a manual test succeeded.

Run the production browser interaction suite with `tests/browser/run_production_studio.ps1`. Supply `-GoldenScreenshot` in visual-regression CI to compare the deterministic Production Studio region using the configured pixel tolerance. Browser artifacts and reports are written under `output/playwright/`.
