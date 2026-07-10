# SpriteForge Foundation Baseline

Captured on 2026-07-10 for the Foundation roadmap slice.

## Repeatable checks

Run from the repository root in the same Python environment used to launch SpriteForge:

```powershell
Measure-Command { python -c "import spriteforge_web" }
Measure-Command { python -m pytest -q }
python -m pytest tests/test_asset_repository_service.py -q
spriteforge assets --project projects/<name>/spriteforge_project.json integrity
```

The full non-vendored suite contains 538 tests and completed in 41.56 seconds on the baseline machine. The canonical asset integration set contains five tests covering migration, branching, restoration, deduplication, conflict recovery, QA caching, and HTTP round trips.

## Production milestone measurement

The completed production suite contains 553 tests. The representative roadmap benchmark used 1,000 canonical assets, a 2,000-frame timeline, and a 5,000-cell matrix. On the development machine it measured 5.826 ms for the 1,000-asset query, 0.007 ms for the timeline operation, 74.405 ms to persist the matrix, and 5.669 ms for a paged status filter. All configured responsiveness thresholds passed. Asset fixture insertion took 12.895 seconds and is reported separately from interactive query latency.

Generation throughput and export duration are workload-dependent. Capture them with a fixed provider/model, seed, input fixture, and export preset; record unavailable providers as unavailable rather than zero. Pixel Studio load time should be captured from the browser performance timeline at desktop and mobile widths using the same project fixture.

For failure-rate comparisons, classify failures by stable error code and report `failed attempts / total attempts` separately for generation, validation, and export. Do not merge cancellations into failures.
