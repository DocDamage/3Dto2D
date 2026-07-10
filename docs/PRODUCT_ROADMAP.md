# SpriteForge Studio Product and Engineering Roadmap

## Purpose

This roadmap turns SpriteForge Studio from a broad collection of sprite-generation and editing tools into a cohesive, reproducible production environment that carries an asset from reference to game-ready export.

The intended product flow is:

```text
Reference -> Generate -> Curate -> Edit -> Animate -> Validate -> Export
```

The plan builds on capabilities already present in the repository. In particular, SpriteForge already has foundations for reproducibility manifests, quality checks, timeline editing, style profiles, persistent queues, remote ComfyUI execution, and engine exporters. The work below should consolidate and extend those foundations rather than introduce parallel implementations.

## Product principles

1. **Every result is reproducible.** Generated and edited assets retain enough provenance to recreate or branch them.
2. **Editing is non-destructive.** Source assets remain intact and transformations can be changed or removed.
3. **Quality is measurable.** Sprite-specific validation is available before export, not only after an asset fails in a game engine.
4. **Simple paths stay simple.** Presets and guided flows serve new users, while manifests and advanced workflow controls remain accessible.
5. **Local-first remains the default.** Projects work offline when local providers are available, and remote providers are adapters rather than hard dependencies.
6. **Exports are deterministic.** The same project revision and preset produce the same file layout and metadata.
7. **Long operations are resilient.** Generation, baking, validation, and export survive UI reloads and can be retried safely.

## Current foundation

| Area | Existing foundation | Roadmap target |
| --- | --- | --- |
| Reproducibility | File hashing and reproducibility manifests | Per-asset provenance graph with branchable revisions |
| Quality | QA and repair tooling | Unified validation rules, severity levels, autofixes, and export gates |
| Animation | Player, scrubbing, frame editing, and reordering | Full timeline, onion skinning, anchors, hitboxes, loop regions, and synchronized directions |
| Style | Palette cleanup and reusable style profiles | Versioned project style system with drift detection |
| Batch work | Production commands and persistent queue | Matrix generation, comparison, promotion, retry, and resumable UI jobs |
| Remote generation | ComfyUI submission and downloaded run manifests | Provider-neutral jobs and multiple local or remote workers |
| Export | Godot, Unity, Unreal, and validation helpers | Versioned presets, deterministic packaging, and additional formats |
| Pixel editing | Pixel Studio tools, inpainting, variants, and recipes | Non-destructive operation stack with persistent undo and snapshots |
| Project UI | Multiple specialized views | Production dashboard centered on asset readiness and workflow state |

## Delivery strategy

The roadmap is organized by dependency order rather than fixed calendar dates. Effort estimates assume a small team familiar with the codebase:

- **S:** a focused change taking roughly a few days
- **M:** a multi-part feature taking roughly one to three weeks
- **L:** a major milestone taking roughly one to two months
- **XL:** a cross-cutting product initiative best delivered incrementally

Each phase must be independently usable. Feature flags should protect incomplete user-facing work, and project schema migrations must remain backward compatible.

---

## Phase 0: Architecture and product baseline

**Effort:** M
**Goal:** Establish stable contracts and measurements before adding cross-cutting features.

### Deliverables

- Inventory current project manifests, asset sidecars, queue records, QA output, style profiles, and export metadata.
- Define a versioned canonical project schema and asset-record schema.
- Add JSON Schema or typed Python models for persisted records.
- Add a central project repository service so routes and command-line tools do not implement storage independently.
- Define API request and response contracts and publish an OpenAPI document for supported web endpoints.
- Record baseline measurements for startup time, Pixel Studio load time, generation throughput, export duration, test duration, and common failure rates.
- Add feature flags for incomplete roadmap capabilities.
- Document migration, backup, and rollback rules.

### Acceptance criteria

- Existing projects open without manual conversion.
- Invalid persisted records produce actionable errors instead of partial failures.
- Every schema includes a version and has round-trip tests.
- Web and CLI operations share the same project storage services.
- Baseline performance and reliability numbers are recorded in a repeatable report.

---

## Phase 1: Asset provenance and reproducible history

**Effort:** XL
**Goal:** Make every asset traceable, reproducible, and branchable.

### Core model

Introduce an asset record containing:

- Stable asset ID and project ID
- Asset type, role, action, direction, and variant labels
- Source asset IDs and parent revision ID
- Prompt, negative prompt, seed, provider, model, workflow, and sampler settings
- Reference-image hashes and generation input hashes
- Ordered edit-operation stack
- Palette, dimensions, frame layout, anchors, and timing metadata
- Generated files and their content hashes
- QA results and export history
- Creation time, application version, and schema version

Store immutable revisions and point the logical asset to its current revision. Use content-addressed storage for large duplicate files where practical, while retaining human-readable project exports.

### User experience

- Add an asset history panel showing sources, generated variants, edits, validation, and exports.
- Allow users to duplicate, branch, compare, rename, promote, and restore revisions.
- Add “Recreate this result” and “Create variant from here” actions.
- Show when exact recreation is impossible because a model, provider, or source is unavailable.
- Extend the existing reproducibility manifest tooling to cover asset revisions rather than only file snapshots.

### Acceptance criteria

- A generated asset can be recreated from its recorded inputs when its provider remains available.
- Restoring an older revision never destroys newer revisions.
- Identical binaries are detected and not stored repeatedly in managed project storage.
- Project export/import preserves history and validates hashes.
- Interrupted writes cannot leave the active asset revision pointing to incomplete data.

### Required tests

- Schema migration and downgrade-safety tests
- Revision branching and restoration tests
- Content-hash collision and deduplication tests
- Interrupted-write recovery tests
- Bundle round-trip and tamper-detection tests

---

## Phase 2: Non-destructive editing and persistent undo

**Effort:** L
**Depends on:** Phase 1
**Goal:** Turn Pixel Studio operations into editable instructions instead of destructive file changes.

### Deliverables

- Define an operation interface with input revision, parameters, deterministic output, preview, and serialization.
- Convert crop, resize, palette reduction, transparency cleanup, outline, shadow, alignment, reskin, and inpaint results into operations.
- Add an operation stack with enable, disable, reorder, duplicate, and edit controls.
- Persist undo and redo history across browser sessions.
- Add named snapshots for meaningful checkpoints.
- Cache rendered intermediate results by input hash plus operation parameters.
- Preserve an explicit “flatten” operation for export or performance-sensitive projects.

### Acceptance criteria

- Users can alter an earlier operation without losing later work.
- Undo and redo remain available after restarting the application.
- The original imported or generated image is never overwritten.
- Reopening an unchanged operation stack returns the same output hash.
- Missing or obsolete operations fail visibly and retain their serialized parameters.

---

## Phase 3: Unified sprite QA and repair

**Effort:** L
**Depends on:** Phase 1
**Goal:** Make validation a first-class production step and expand the current QA foundation.

### Rule categories

- **Structure:** dimensions, frame count, sheet layout, missing directions, missing actions, and naming
- **Transparency:** stray pixels, unintended opaque backgrounds, alpha fringes, and empty frames
- **Animation:** foot-anchor movement, centroid jitter, sudden silhouette changes, duplicates, and timing anomalies
- **Visual consistency:** palette drift, outline inconsistency, scale variance, lighting changes, and reference similarity
- **LPC:** required dimensions, layer compatibility, action mapping, direction order, and frame placement
- **Export:** required metadata, pivot validity, atlas bounds, file references, and engine-specific constraints

### Deliverables

- Create a rule registry with stable IDs, severity, explanation, evidence, and optional fix actions.
- Support project-, style-, and export-preset-specific rule configuration.
- Display findings on the affected frame, timeline position, or metadata field.
- Add safe one-click repairs and preview-before-apply for destructive-looking fixes.
- Create validation summaries for assets, animation sets, projects, and exports.
- Allow presets to block export on errors while permitting explicit warning overrides.
- Store QA results on asset revisions and invalidate them when relevant inputs change.

### Acceptance criteria

- Every finding identifies the affected asset and a concrete location or property.
- Autofixes produce a new asset revision and are undoable.
- Revalidating unchanged assets uses cached results.
- CLI, web UI, and export gates use the same rule engine.
- A machine-readable validation report can be consumed by CI.

### Success metrics

- Reduction in engine import failures
- Percentage of findings resolved before export
- False-positive rate for blocking rules
- Median validation duration per animation set

---

## Phase 4: Professional animation workspace

**Effort:** XL
**Depends on:** Phases 1 and 2
**Goal:** Evolve the existing player and frame editor into a complete sprite-animation workspace.

### Timeline

- Per-frame duration controls and FPS conversion
- Loop-region selection and named animation clips
- Multi-select, duplicate, reverse, hold, delete, and reorder operations
- Zoomable timeline with keyboard shortcuts
- Audio-free playback modes for deterministic visual review
- Onion skinning with previous/next frame count, opacity, and tint controls

### Spatial tools

- Persistent origin, foot anchor, pivot, attachment points, and collision or hitbox overlays
- Alignment guides and batch anchor movement
- Difference, silhouette, and onion-skin views
- Canvas-size and content-bounds visualization
- Optional suggested alignment based on feet, centroid, or selected landmarks

### Direction and action management

- Synchronize timing across directions.
- Compare the same frame index across directional animations.
- Detect and fill missing action-direction combinations.
- Copy anchors and timing between compatible animations.
- Preserve explicit mappings for LPC and engine export conventions.

### Acceptance criteria

- Editing timing or anchors updates previews and export metadata immediately.
- Direction synchronization never changes source frames without a new revision.
- Keyboard-only timeline editing is possible for common operations.
- A saved project restores timeline selection, zoom, playback, overlays, and clip definitions.
- Timeline operations have integration tests and visual browser tests.

---

## Phase 5: Batch generation, comparison, and curation

**Effort:** L
**Depends on:** Phases 1 and 7
**Goal:** Make large variant searches manageable rather than producing an unstructured output folder.

### Deliverables

- Add a matrix builder for prompts, seeds, models, providers, styles, characters, poses, directions, actions, outfits, and palettes.
- Estimate job count, storage, and provider cost before submission.
- Group results by experiment and matrix coordinates.
- Add contact-sheet and side-by-side comparison modes.
- Support star ratings, tags, rejection, shortlist, and promotion to a project asset.
- Calculate optional QA, style-similarity, and reference-similarity scores.
- Allow users to regenerate failed cells or expand promising matrix branches.
- Preserve exact generation parameters for every cell.

### Acceptance criteria

- The UI warns before unexpectedly large or costly batches.
- Cancelling a batch does not discard completed results.
- Promoting a result records its experiment and matrix provenance.
- Failed cells can be retried without repeating successful work.
- Filters remain responsive with at least several thousand result records.

---

## Phase 6: Project style system and drift detection

**Effort:** L
**Depends on:** Phases 1 and 3
**Goal:** Make visual consistency reusable, versioned, and measurable.

### Style profile contents

- Named palette with locked, optional, and forbidden colors
- Canvas, resolution, pixel scale, and nearest-neighbor rules
- Outline color, thickness, and continuity expectations
- Lighting direction and shadow rules
- Prompt fragments and negative prompt fragments
- Reference assets and their embeddings or descriptors
- Preferred model, workflow, provider, and post-processing settings
- QA thresholds and export assumptions

### Deliverables

- Version style profiles and record the exact profile revision used by each asset.
- Extend current profile extraction with editable detected values and confidence indicators.
- Add style comparison and drift warnings during generation, editing, and validation.
- Add “conform to style” previews for palette, outline, scale, and cleanup operations.
- Support project defaults plus per-asset exceptions.
- Export and import portable profile files without embedding provider secrets.

### Acceptance criteria

- Updating a style profile does not silently rewrite existing assets.
- Users can identify which assets use an outdated profile revision.
- Drift findings explain the contributing signals instead of presenting only a score.
- Applying style conformance creates a reversible asset revision.
- Profile exports contain no API keys, local credentials, or machine-specific paths.

---

## Phase 7: Resilient background jobs and provider adapters

**Effort:** XL
**Goal:** Replace separate execution paths with one resumable job system.

### Job model

Each job should record:

- Stable job ID, type, owner project, and related asset IDs
- Serializable inputs and content hashes
- State: queued, preparing, running, cancelling, cancelled, retrying, failed, or completed
- Progress, stage, logs, timestamps, worker, and resource requirements
- Retry policy, attempt history, failure classification, and outputs
- Provider-specific external job IDs without leaking them into general UI logic

### Deliverables

- Evolve the current persistent queue into a service shared by web and CLI operations.
- Store jobs transactionally, preferably in SQLite with migration support.
- Add retry, cancellation, priority, pause, resume, and stale-job recovery.
- Stream progress to the UI using server-sent events or WebSockets.
- Add concurrency and resource limits for CPU, GPU, VRAM, provider rate, and storage.
- Introduce provider interfaces for local processing, local ComfyUI, remote ComfyUI, and supported cloud services.
- Add worker health, capability discovery, and routing rules.
- Keep provider secrets outside project bundles and redact them from logs.

### Acceptance criteria

- Closing the browser does not stop server-side work.
- Restarting SpriteForge recovers queued jobs and marks unrecoverable running jobs clearly.
- Cancellation reaches providers that support it and is otherwise reported honestly.
- Provider outages use bounded retry with backoff and do not freeze unrelated jobs.
- The same generation request structure works across compatible providers.

### Operational safeguards

- Per-provider request and cost limits
- Disk-space checks before large jobs
- Output quarantine for invalid or unexpected payloads
- Structured, redacted logs
- Support-bundle export without credentials or user source images by default

---

## Phase 8: Export presets and deterministic packaging

**Effort:** L
**Depends on:** Phases 1, 3, and 4
**Goal:** Turn existing engine exporters into a versioned preset platform.

### Initial presets

- Godot
- Unity
- Unreal
- RPG Maker-compatible layouts where licensing and formats permit
- LPC
- Phaser or generic web atlas
- Generic JSON atlas
- CSS sprite sheet
- Raw frames plus metadata

### Preset capabilities

- Sheet packing strategy and maximum texture size
- Scale, interpolation, padding, extrusion, and trimming rules
- Naming templates and directory layout
- Pivot, anchor, collision, attachment, and timing mappings
- Atlas and animation metadata format
- Optional normal maps and derived files
- Pre-export QA rule set

### Deliverables

- Version preset schemas and embed the preset revision in export manifests.
- Add previewable file trees and estimated output sizes.
- Produce exports in a temporary staging directory, validate them, then publish atomically.
- Add incremental export when only a subset of assets changed.
- Generate import instructions and sample engine configuration where useful.
- Add golden-file tests for stable metadata and directory layouts.

### Acceptance criteria

- Repeating an export from the same revision and preset produces identical logical contents.
- Failed validation never replaces the last successful export.
- Export manifests map every output file back to an asset revision.
- Presets can be shared without machine-specific absolute paths.
- Supported engine versions are documented and tested.

---

## Phase 9: Visual workflow builder

**Effort:** XL
**Depends on:** Phases 1, 2, 3, and 7
**Goal:** Let users compose production recipes without exposing unnecessary provider complexity.

### Node categories

- Import or reference
- Generate or transform
- Background removal
- Frame extraction
- Crop, align, resize, and palette operations
- Style conformance
- QA and conditional repair
- Human approval checkpoint
- Export

### Deliverables

- Define a typed directed-acyclic-graph workflow schema.
- Add node input/output contracts and preflight validation.
- Compile high-level nodes into the provider-neutral job system.
- Permit reusable subflows and parameter presets.
- Support conditional branches based on QA results.
- Provide run history, per-node logs, cached nodes, and restart-from-node.
- Add an advanced escape hatch to link or embed compatible ComfyUI workflows without pretending all ComfyUI nodes are native SpriteForge nodes.
- Ship curated templates for common workflows.

### Acceptance criteria

- Invalid connections are rejected before execution with clear explanations.
- Unchanged deterministic nodes use cached outputs.
- Restarting from a failed node does not repeat valid upstream work.
- Workflow imports are schema-validated and subject to the same bundle safety rules as projects.
- A workflow run records exact node versions and parameters.

---

## Phase 10: Production dashboard and guided experience

**Effort:** L
**Depends on:** Phases 1, 3, 7, and 8
**Goal:** Organize the application around production readiness rather than disconnected tools.

### Dashboard sections

- Project completion by character, action, direction, and required variant
- Assets awaiting review or cleanup
- Missing or invalid animation combinations
- QA errors and warnings
- Active, failed, and recently completed jobs
- Style-profile drift
- Export readiness and last successful export
- Project disk usage and cache opportunities
- Recent activity and recoverable snapshots

### Guided flows

- New-project wizard with target engine, sprite standard, style profile, and required animations
- First successful local or remote generation
- Import-and-clean existing sprite workflow
- LPC character assembly workflow
- “Prepare for export” checklist
- Contextual empty states and direct links to the relevant corrective action

### Acceptance criteria

- Dashboard counts are derived from canonical asset, job, QA, and export records.
- Every problem card links to a filtered view where it can be resolved.
- New users can create, validate, and export a sample project without using the CLI.
- Dashboard loading remains responsive for large projects through pagination and incremental queries.

---

## Phase 11: Packaging, updates, and operational maturity

**Effort:** XL
**Goal:** Make installation and upgrades predictable for non-developer users.

### Deliverables

- Produce signed Windows installers and a documented portable distribution.
- Evaluate macOS and Linux packaging after the Windows pipeline is stable.
- Add application, schema, workflow-node, and provider-adapter version reporting.
- Implement update checking and a user-controlled updater with rollback.
- Separate application code, managed runtime dependencies, user projects, caches, models, and outputs.
- Add storage policies and safe cache cleanup previews.
- Add crash recovery, automatic project snapshots, and restore UI.
- Generate privacy-preserving diagnostic bundles with an explicit preview of included files.
- Document backup, migration, downgrade, and disaster-recovery procedures.

### Acceptance criteria

- Upgrade tests cover at least the previous two supported project schema versions.
- Uninstalling the application does not remove user projects or models by default.
- Failed updates roll back to a runnable version.
- Diagnostic bundles exclude secrets and user assets unless explicitly included.
- A clean machine can install, launch, run the CPU-safe demo, and uninstall through automated release testing.

---

## Cross-cutting engineering program

These improvements should be delivered continuously alongside the product phases.

### Frontend architecture

- Split large scripts by feature ownership and register each view through the lifecycle system.
- Introduce a small centralized project and session state store.
- Keep server-owned records authoritative and make optimistic UI updates reversible.
- Standardize accessible dialogs, notifications, progress indicators, and keyboard shortcuts.
- Add end-to-end browser tests for critical workflows at desktop and mobile widths.

### Backend architecture

- Keep Flask routes thin and move business logic into tested services.
- Use typed records at persistence and API boundaries.
- Centralize safe path, atomic-write, archive, hash, and migration utilities.
- Separate provider adapters from generation orchestration.
- Add structured error codes so the web UI does not depend on parsing error strings.

### Persistence

- Use SQLite for indexed metadata, jobs, history, and migrations.
- Keep images and large generated artifacts on disk or configurable object storage.
- Use transactions for metadata and atomic rename for finalized files.
- Provide integrity checking and repair for orphaned records or files.
- Never store credentials in project databases, manifests, exports, or logs.

### Testing and quality

- Maintain unit tests for transformations and storage rules.
- Add contract tests for every provider adapter.
- Add golden-image tests with explicit tolerances for deterministic image operations.
- Add browser tests for the primary product flow.
- Add migration fixtures representing real historical project versions.
- Add performance tests for large projects, long timelines, and large result sets.
- Keep third-party vendored code outside project lint and coverage measurements.

### Observability

- Use structured local logs with request, job, project, and asset correlation IDs.
- Display user-facing failure summaries separately from diagnostic detail.
- Track job duration, retries, cache hits, provider failures, and disk consumption locally.
- Make any external telemetry opt-in, documented, and free of prompts, images, or credentials.

### Security

- Continue enforcing authentication for state-changing endpoints.
- Apply strict project-root and archive safety checks to every new import/export path.
- Treat imported workflows, presets, profiles, and plugins as untrusted data.
- Redact credentials and signed URLs from logs and support bundles.
- Add dependency, secret, and static-analysis checks to CI.
- Define a plugin permission model before allowing third-party executable extensions.

## Suggested release slices

The phases can be packaged into user-facing releases as follows:

| Release | Included work | User-visible outcome |
| --- | --- | --- |
| Foundation | Phase 0 plus schema groundwork | Safer projects and stable contracts |
| History | Phases 1 and 2 | Reproducible assets, revisions, and non-destructive editing |
| Quality | Phase 3 | Actionable sprite QA and repair gates |
| Animator | Phase 4 | Complete animation authoring and metadata workflow |
| Art Direction | Phases 5 and 6 | Scalable variants and consistent project style |
| Production | Phases 7 and 8 | Resilient jobs and deterministic engine exports |
| Automation | Phases 9 and 10 | Visual pipelines and readiness dashboard |
| Distribution | Phase 11 | Reliable installers, updates, recovery, and support tooling |

## Priority order if resources are limited

If only three major investments are possible, prioritize:

1. **Asset provenance and reproducible history** because every later capability needs a stable asset identity and revision model.
2. **Unified sprite QA and repair** because it creates immediate value for generated, imported, and hand-authored assets.
3. **Professional animation workspace plus deterministic exports** because it completes the path from source frames to usable game content.

Do not start the visual workflow builder before provenance and jobs are stable. Otherwise, it will encode temporary execution paths and make future migrations significantly harder.

## Project-wide definition of done

A roadmap feature is complete only when:

- Its persisted data is versioned and migration-tested.
- Its core behavior is shared by web and CLI surfaces where both apply.
- Failure, cancellation, retry, and recovery behavior are defined.
- Accessibility and keyboard interaction are tested for its primary UI.
- Security boundaries and credential handling are reviewed.
- User documentation and in-product guidance are updated.
- Automated tests cover the normal path and important failure paths.
- Performance is measured against a representative large project.
- Existing projects continue to work or receive an automatic, reversible migration.

## Outcome metrics

Track these measures to determine whether the roadmap improves the product:

- Time from new project to first validated export
- Percentage of generated outputs promoted into project assets
- Percentage of project assets with complete provenance
- QA findings detected and resolved before export
- Export failure and engine-import failure rates
- Job completion, cancellation, retry, and recovery rates
- Cache hit rate and duplicate-storage reduction
- Median UI response time for large projects
- Crash-free sessions and successful project recoveries
- Number of manual steps required for a common character animation set

## Immediate next actions

1. Approve this roadmap's product principles and priority order.
2. Complete the Phase 0 metadata and persistence inventory.
3. Write the canonical project and asset schemas as an architecture decision record.
4. Select three representative real projects as migration and performance fixtures.
5. Prototype the asset history model behind a feature flag.
6. Define the initial QA rule registry and severity policy in parallel.
7. Convert the roadmap into tracked milestones only after the schema prototype validates the proposed boundaries.
