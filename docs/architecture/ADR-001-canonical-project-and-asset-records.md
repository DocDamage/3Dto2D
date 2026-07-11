# ADR-001: Canonical project and asset records

Status: Accepted

## Decision

Project manifests use `spriteforge.project.v2`. Existing manifests are upgraded on first canonical access, with the original saved as `spriteforge_project.pre-v2.json` before an atomic replacement.

Assets and immutable revisions are stored in each project's `.spriteforge/project.sqlite3`. Large payloads live in `.spriteforge/objects/<hash-prefix>/<sha256>` and are linked to revisions by SHA-256. An asset row contains the mutable pointer to its current revision; the pointer and completed revision metadata are committed in one SQLite transaction.

The web API and the `spriteforge assets` CLI both use `AssetRepositoryService` and `QAService`. Provider credentials are intentionally absent from every schema.

## Compatibility and rollback

- Legacy fields remain in migrated manifests so older readers can still recover project settings.
- Migration never edits source assets and saves one pre-v2 manifest backup.
- Restoring history moves only the current pointer; it does not delete later revisions.
- Unknown serialized edit operations remain stored. Rendering code must report an unavailable operation instead of discarding its parameters.
- Downgrades may ignore `.spriteforge`, while the backup manifest provides the pre-migration representation.

## Write and recovery rules

1. Validate typed records before persistence.
2. Atomically finalize content objects before starting the metadata transaction.
3. Insert the immutable revision and update the asset pointer within one transaction.
4. Use compare-and-swap when a caller edits from a previously loaded revision.
5. On startup or support checks, run the project integrity endpoint/CLI to detect missing or modified objects.
