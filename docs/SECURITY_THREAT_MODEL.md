# GEOLOGIA security threat model — data and scientific workers

Status: design baseline for review. This document does not mean controls are implemented or that the service is safe for public deployment.

## Assets to protect
- User identity, credentials, project membership, and private datasets.
- Uploaded source bytes, upload-time digests, validation reports, and immutable input snapshots.
- Job requests, parameters, state transitions, worker leases, and cancellation signals.
- Engine images, dependencies, licenses, and signing identities.
- Scientific outputs, logs, provenance manifests, and uncertainty metadata.
- Host kernel, worker supervisor, container runtime, database, object storage, and backups.

## Trust boundaries
1. Browser to API: untrusted client input; authenticate, authorize, validate, rate-limit.
2. API to metadata store: trusted service boundary; least-privilege DB identity and audited transactions.
3. API to object storage: private service credentials; no direct client filesystem paths.
4. Control plane to worker supervisor: authenticated internal protocol with scoped, short-lived identity.
5. Worker supervisor to per-attempt container: explicit resource, filesystem, process, and network boundary.
6. Container to artifact staging: untrusted output until manifest, digest, size, and format checks pass.
7. Engine supply chain: signed, digest-pinned images and reviewed dependencies/licensing.

## Threat register

| ID | Threat / abuse case | Required controls | Verification evidence |
|---|---|---|---|
| T-01 | Unauthorized user reads another project's datasets or results | Authentication, project-level authorization on every route, tenant-scoped storage keys | Cross-project negative API tests and authorization audit |
| T-02 | Malformed upload exploits parser or consumes resources | Streaming size limits, strict parsers, bounded row/feature counts, parser timeouts, sandboxed parsing for high-risk formats | Fuzz tests, malformed corpus, CPU/memory limit tests |
| T-03 | Uploaded script or model executes on host | Never execute user files; only server-side allowlisted adapter entrypoints | Static policy tests, container integration tests, review of all process-launch paths |
| T-04 | Path traversal or symlink escapes job workspace | Generated object IDs, canonical path containment, no-follow/openat-style access, per-attempt mounts | Traversal and symlink regression tests |
| T-05 | Worker steals credentials or accesses host secrets | Dedicated identity, no secret mounts, short-lived scoped credentials, no runtime socket in API, rootless containers | Container mount inspection and secret-scanning tests |
| T-06 | Worker reaches internal services or exfiltrates data | Network namespace with default-deny egress; narrowly allowlisted control-plane channel only | Egress-deny tests from inside a worker container |
| T-07 | Worker escapes container or exploits kernel | Rootless runtime, non-root UID, user namespaces, seccomp, AppArmor/SELinux, patched host kernel | Runtime security profile tests and host hardening audit |
| T-08 | Duplicate delivery creates duplicate outputs or billing | At-least-once semantics, attempt IDs, idempotency keys, lease ownership, conditional artifact publication | Duplicate-claim and duplicate-completion failure tests |
| T-09 | Worker crash leaves job permanently running | Leases, heartbeats, expiry recovery, attempt budget, stale-attempt quarantine | Kill-worker and lease-expiry tests |
| T-10 | Cancellation reports success while computation continues | Running state transitions to cancel_requested; worker confirms only after process-tree stop and cleanup | Cancellation race, delayed-worker, and kill-timeout tests |
| T-11 | Tampered inputs or outputs produce misleading science | Re-hash immutable inputs before execution; digest outputs; bind reports to exact manifest and engine image | Tamper fixtures and provenance consistency tests |
| T-12 | Compromised engine image or dependency poisons results | Pinned digests, signature verification, SBOM, provenance attestations, license review, vulnerability policy | Supply-chain verification in CI and deployment admission |
| T-13 | Scientific results appear more certain than evidence supports | Benchmark gates, uncertainty schema, assumptions/limitations, independent domain review | Known-answer benchmark suite and scientific sign-off |
| T-14 | Resource exhaustion through expensive models or decompression bombs | Per-job CPU/RAM/disk/PID/time/output quotas, concurrency quotas, queue backpressure | Stress tests and resource-limit kill tests |
| T-15 | Audit trail is altered or contains secrets | Append-only event API, restricted DB roles, tamper-evident external audit export, log redaction | Permission tests, audit integrity checks, secret canary tests |
| T-16 | Public API bypasses the development CLI loopback restriction | Authentication, authorization, TLS termination, private ingress, deployment policy; do not rely on CLI guard | Deployment configuration tests and external exposure scan |

## Abuse cases requiring explicit negative tests
- User changes a dataset file after validation but before queue claim.
- User changes a project role or removes dataset access after a job is queued.
- Worker replays a previous lease token after expiry.
- Worker A attempts to heartbeat, cancel, or publish artifacts for worker B's lease.
- Worker submits a result after cancellation was requested.
- A worker crashes after publishing an object but before committing the terminal job state.
- Two workers claim the same queued job concurrently.
- An artifact filename contains traversal, Unicode confusables, or symlink targets.
- A compressed or nested dataset expands beyond the configured storage quota.
- An engine tries to access cloud metadata endpoints or loopback/private network addresses.
- A result manifest references a different input digest or engine image than the queued manifest.

## Risk acceptance
No high-impact risk in this register is accepted by default. Any exception requires a named owner, written rationale, scope, expiry date, and compensating controls. A passing CI suite is not a substitute for a deployment security review or scientific validation.

## Current implemented controls versus gaps

Implemented in the current repository: bounded upload size, generated storage names, SHA-256 at upload, re-hash before validation, strict GeoJSON JSON parsing, deterministic validation profiles, loopback restriction in the development CLI, and a durable local job state/event model.

Not implemented: authentication, project authorization, tenant isolation, rate limiting, malware scanning, PostgreSQL worker queue, leases, worker identity, OCI isolation, network policy, artifact publication protocol, supply-chain verification, and production audit infrastructure.

## Review gate
Before Phase 9 worker implementation, review this threat model with a security engineer and define the deployment target. No scientific engine may be enabled until the controls in WORKER_ARCHITECTURE.md and this register have executable tests.