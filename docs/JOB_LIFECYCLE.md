# GEOLOGIA job lifecycle foundation

Status: durable state-machine foundation; no scientific worker is enabled.

## Job states

```text
planned -> queued -> running -> succeeded
    |         |        |  \
    |         |        |   -> failed -> queued (bounded retry)
    |         |        -> cancel_requested -> cancelled
    |         -> cancelled
    -> cancelled
```

Terminal states are `succeeded` and `cancelled`. A failed job may be queued again only while its recorded attempt count is below `max_attempts` (default: 3). Entering `running` increments the attempt count. Illegal transitions are rejected.

## Persistence and audit

- Existing SQLite job tables are migrated in place by rebuilding the constrained table while preserving existing job records.
- SQLite `PRAGMA user_version` is set to schema version `1` for both fresh and migrated databases.
- Each job stores attempt count, retry limit, queue/start/finish/update timestamps, and bounded error code/message fields.
- Every state transition is appended to `job_events` with actor, source state, destination state, structured detail, and timestamp.
- State changes and event insertion happen in one SQLite transaction using `BEGIN IMMEDIATE`.
- The events endpoint is read-only: `GET /api/v1/jobs/{job_id}/events`.

## Cancellation semantics

- Planned and queued jobs can become `cancelled`.
- A running job becomes `cancel_requested`; this endpoint does not claim to kill a worker or terminate a process.
- A future worker must poll or receive cancellation signals, stop cooperatively, clean up its workspace, and acknowledge with the final `cancelled` transition.
- `POST /api/v1/jobs/{job_id}/cancel` returns `execution_stopped: false` while cancellation is only requested.

## Explicit execution boundary

This phase does not add a queue consumer, worker process, container runtime, subprocess execution, engine integration, or permission to execute uploaded content. Existing job creation still creates a `planned` record only. The state machine is infrastructure for later isolated workers, not evidence that a scientific task ran.

Before enabling workers, the next design gate requires:
1. A durable queue/claim protocol with lease expiry and crash recovery.
2. Idempotency keys and duplicate-delivery handling.
3. Per-job workspace isolation and read-only source mounts.
4. CPU, memory, disk, process, network, and wall-clock limits.
5. Cancellation acknowledgement and cleanup guarantees.
6. Signed/verified engine images, pinned dependencies, and software provenance.
7. Structured logs, artifact manifests, immutable inputs, and reproducible result metadata.
8. Worker authentication and authorization; no public worker-control endpoint without the platform security boundary.
9. Failure-injection tests for crashes, retries, lease expiry, duplicate claims, and partial artifacts.

No state transition enables a scientific engine. The platform-level execution flag remains false.
