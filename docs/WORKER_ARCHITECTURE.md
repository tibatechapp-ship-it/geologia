# GEOLOGIA worker and execution architecture

Status: design proposal only. No worker, queue consumer, subprocess runner, or engine execution is enabled by this document.

## 1. Design objective

Move scientific computation out of the FastAPI control plane. The API may validate inputs, create plans, authorize work, and persist state; it must never import or execute arbitrary scientific engine code inside the web process.

The architecture must preserve the project's evidence rule: a successful run is not merely a process exit code. It must produce immutable input references, a reproducible execution manifest, validated artifacts, explicit uncertainty metadata, and a machine-readable record of the engine environment.

## 2. Control plane and worker plane

### Control plane
- FastAPI API and bilingual web client.
- Authentication, authorization, project ownership, quotas, and audit policy.
- Dataset registry and versioned validation reports.
- Job state repository and durable queue interface.
- Engine catalogue with verified license metadata and pinned image digests.
- Result/provenance registry.

### Worker plane
- Separate worker supervisor process; never embedded in Uvicorn.
- One isolated OCI container per attempt.
- Explicit engine adapter selected from a server-side allowlist.
- Read-only access to immutable input snapshots.
- Private per-attempt scratch directory and bounded output staging.
- No direct access to API secrets, SQLite files, host home directories, or other projects.

The API must not mount the container runtime socket or receive host-level container privileges. The worker supervisor is a separate trust boundary and must run under a dedicated unprivileged identity. Rootless Podman or another rootless OCI runtime is the preferred deployment target, subject to platform verification.

## 3. Queue and persistence decision

Production source of truth: PostgreSQL. Use a database-backed queue with atomic claims and leases. A worker claims a row in a short transaction using SELECT FOR UPDATE SKIP LOCKED, changes its state, increments its attempt, and records a lease. The database remains authoritative for job state and events.

- Do not make Redis the only job store.
- Redis may later provide notifications or cache acceleration, but loss of Redis must not lose work or state.
- The current SQLite backend remains a local development adapter only; it is not a multi-worker production queue.
- Introduce a repository interface before implementing a production worker so the API does not depend on SQLite-specific queue semantics.
- Use a transactional outbox if state changes must be published to external notification systems.

### Required queue fields

| Field | Purpose |
|---|---|
| job_id | Stable job identity |
| attempt_id | Unique identity for each execution attempt |
| state | State-machine state |
| attempt_count, max_attempts | Bounded retry policy |
| idempotency_key | Prevent duplicate submission |
| lease_owner | Authenticated worker identity |
| lease_token_hash | Verify lease ownership without storing a raw token |
| lease_expires_at | Recover jobs after worker loss |
| heartbeat_at | Detect stalled workers |
| cancel_requested_at | Cooperative cancellation signal |
| input_manifest_digest | Immutable input snapshot identity |
| engine_image_digest | Exact executable environment |
| created_at, queued_at, started_at, finished_at | Lifecycle timestamps |

The current Phase 8 state machine is the starting contract, not the complete queue protocol. The next implementation must add leases, heartbeat, idempotency, and crash recovery.

## 4. Claim, lease, and recovery protocol

1. API authorizes the caller, validates the selected data profile, snapshots the exact input dataset IDs, SHA-256 digests, CRS declarations, and validation-report versions.
2. API creates a planned job and immutable request manifest. A job is not executable merely because required role tags are present.
3. An explicit authorization gate changes the job to queued only after the engine, version, license, input contract, resource profile, and user approval are all resolved.
4. Worker authenticates using a workload identity and requests a claim for an allowed queue.
5. Database atomically claims one eligible job, creates an attempt ID, increments the attempt count, and issues a short-lived lease.
6. Worker verifies the lease, re-hashes every input, verifies the manifest and engine image digest, and creates an isolated workspace.
7. Worker sends heartbeats and checks for cancellation. Heartbeat renewal requires the current lease token and owner.
8. On success, worker stages outputs, validates the artifact manifest, atomically publishes artifacts, and reports a result digest plus provenance.
9. On failure, worker returns a classified error. Retry only transient failures and only within the attempt budget. Deterministic input/schema failures are not retried.
10. If the lease expires, a recovery controller reconciles the attempt. It must not publish incomplete outputs. A retry receives a new attempt ID and isolated workspace.
11. A running cancellation request is acknowledged only after the worker has stopped the process tree and cleaned or quarantined its workspace.

### Delivery semantics

Assume at-least-once delivery. Exactly-once process execution cannot be guaranteed across network partitions and worker crashes. Instead, make effects idempotent:
- Each attempt has a unique ID.
- Artifacts are written to attempt-scoped staging paths.
- Publication is conditional on the active lease and a single successful terminal transition.
- Duplicate completion messages are rejected or treated as idempotent reads.
- Partial artifacts are never exposed as successful results.

## 5. Per-attempt isolation contract

Each execution attempt runs in a fresh rootless OCI container with:
- Non-root UID/GID and user namespace.
- Read-only container root filesystem.
- Read-only input mounts containing only the authorized job snapshot.
- One private writable scratch/output mount with an explicit quota.
- No host home, Docker/Podman socket, database file, credentials directory, or unrelated project mount.
- Network disabled by default; no arbitrary outbound internet access.
- All Linux capabilities dropped; no privilege escalation; no-new-privileges.
- Seccomp profile and AppArmor/SELinux policy where supported.
- PID, CPU, memory, disk I/O, file-size, open-file, and wall-clock limits.
- Process-count and output-size limits.
- Container teardown and workspace cleanup after each attempt.
- Image pinned by immutable digest and verified signature/provenance before execution.

The API process must not be the container supervisor. The worker supervisor must not accept user-supplied shell commands or arbitrary image names.

## 6. Engine adapter contract

An adapter is a reviewed, versioned, server-side package. It declares:
- Stable engine ID and adapter version.
- Exact OCI image digest and signature identity.
- License identifier, source URL, obligations, and review status.
- Supported input formats, schemas, units, CRS semantics, and size limits.
- Allowed parameter schema with bounds and defaults.
- Deterministic command/entrypoint and output contract.
- Resource profile and timeout.
- Benchmark fixture IDs and expected result tolerances.
- Known limitations and uncertainty methodology.

Never execute uploaded scripts, macros, plugins, notebooks, binaries, or model files as code. User-provided parameters are validated data, not commands. Do not interpolate untrusted strings into a shell. The adapter invokes only its fixed entrypoint with structured arguments.

## 7. Provenance and result contract

A successful result must include:
- Job ID and attempt ID.
- Input manifest and each input SHA-256.
- Validation profile IDs/versions and validation report digests.
- Engine ID, adapter version, OCI image digest, and license review reference.
- Exact parameters, units, CRS and datum assumptions.
- Start/end times, resource usage, and worker identity.
- Random seed and deterministic-mode setting when applicable.
- Output artifact names, media types, sizes, SHA-256 digests, and validation reports.
- Benchmark suite/version and known-answer comparison results.
- Uncertainty representation, assumptions, excluded effects, and limitations.
- Structured logs and warnings, excluding secrets.

A process exit code of zero is necessary but not sufficient for a scientifically accepted result.

## 8. API and authorization boundary

Before remote workers exist:
- Add user authentication and project-level authorization.
- Separate user routes from internal worker routes.
- Require short-lived, scoped worker credentials or mTLS workload identity.
- Authorize every job claim, heartbeat, cancellation acknowledgement, and artifact publication against worker identity and lease.
- Keep worker endpoints off the public browser surface.
- Apply quotas, rate limits, upload concurrency limits, and audit logging.
- Do not expose direct filesystem paths or storage credentials to workers.

The current Phase 8 cancellation endpoint is a local development API. It is not a production worker-control security design.

## 9. Observability and operations

Required metrics: queue depth, queue age, claim latency, active leases, heartbeat age, attempt duration, retry count, cancellation latency, worker saturation, resource-limit kills, artifact validation failures, and engine-specific benchmark drift.

Required operational controls: structured logs with correlation IDs, alerting on expired leases, disk pressure, stuck jobs, repeated deterministic failures, and unexpected egress; backup/restore drills; retention and artifact lifecycle policies; and a kill switch that prevents new jobs from being queued.

## 10. Implementation gates

Do not enable a scientific engine until all gates pass:
1. Threat model reviewed and security owner assigned.
2. Authentication, project authorization, worker identity, and quotas implemented.
3. PostgreSQL repository and migration tests complete.
4. Atomic claim, leases, heartbeats, idempotency, recovery, and cancellation acknowledgement tested with failure injection.
5. Rootless container isolation verified on the target Linux deployment.
6. Resource limits and network-deny behavior verified from inside test containers.
7. Artifact staging, validation, publication, and cleanup tested under worker crashes.
8. Engine license and supply-chain review complete.
9. Published benchmark fixtures, known-answer tolerances, uncertainty reporting, and independent scientific review complete.
10. Operational runbooks, backups, monitoring, and incident response tested.

## 11. Current status

Implemented now: Phase 8 job state machine, bounded attempt count, event history, idempotent cancellation request, and legacy SQLite migration.

Not implemented: PostgreSQL, queue claiming, leases, worker authentication, worker process, container supervisor, OCI isolation, engine adapters, artifact provenance, or scientific execution. This document is an architecture gate, not a claim that those capabilities exist.