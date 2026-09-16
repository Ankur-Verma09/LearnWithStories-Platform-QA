# Future production test strategy

## Status and purpose

This document describes production controls for a future quiz delivery platform that may use Telegram, an AI model provider, web search, persistent memory, scheduled jobs, and external current-affairs sources. These capabilities are not part of the current Cloudflare Worker assessment and are not claimed as automated by the existing suite.

The strategy assumes every external dependency can be unavailable, slow, misconfigured, or return an unexpected response. Validation must occur before an operation changes state or sends a message. A failed validation must produce a diagnostic result, an administrator alert, and either a documented degraded mode or a safe stop.

## Operating principles

- Treat configuration as untrusted input.
- Verify identity as well as connectivity. A valid credential for the wrong bot or account is a failure.
- Do not send user-facing content when environment, authorization, or recipient validation fails.
- Separate transient provider failures from permanent configuration and permission errors.
- Retry only idempotent operations and use bounded exponential backoff with jitter.
- Keep student data isolated by Telegram user ID and application user ID.
- Mask credentials and personal data in logs, reports, traces, and alerts.
- Record enough state to resume interrupted work without duplicating messages or reports.
- Test degraded operation deliberately; do not discover it during an outage.

## Future requirements

| ID | Priority | Requirement | Failure behavior | Proposed evidence |
|---|---|---|---|---|
| FP-01 | P0 | Validate profile, environment, workspace, timezone, clock, storage, scheduler, network, and required providers during startup. | Do not accept scheduled work; publish a masked diagnostic and alert the administrator. | Startup contract tests and dependency fault injection. |
| FP-02 | P0 | Match the loaded profile to the expected bot name, username, environment, workspace, stores, database, cron directory, and home channel. | Stop before polling, webhook registration, or message delivery. | Configuration matrix and wrong-profile tests. |
| FP-03 | P0 | Verify Telegram token validity, bot ID, username, API access, update mode, permissions, and home chat. | Retry transient failures; stop and alert after the retry budget. | Telegram sandbox contract tests. |
| FP-04 | P0 | Verify model authentication, configured model, reachability, required context size, tool support, and fallback model. | Use the approved fallback; stop content generation if no approved model is available. | Provider contract tests and forced primary-provider outage. |
| FP-05 | P0 | Verify internet, search, reliable sources, and publication dates before generating current affairs. | Do not generate unverified current-affairs content. | Search outage, stale-source, and missing-date tests. |
| FP-06 | P0 | Verify memory availability, storage writability, user profile existence, and data integrity before progress updates. | Cache an encrypted pending update, avoid reporting it as persisted, retry later, and alert. | Store outage, read-only store, and corruption tests. |
| FP-07 | P0 | Validate recipient, chat ID, bot permission, message size, Markdown, and links before sending. | Reject invalid messages; retry only transient Telegram errors with an idempotency key. | Boundary, formatting, invalid-chat, and duplicate-send tests. |
| FP-08 | P0 | Validate profile, timezone, lock, previous result, and idempotency key before every scheduled job. | Skip duplicates and record why the job did not run. | Concurrent scheduler and replay tests. |
| FP-09 | P0 | Require exactly one correct answer, unambiguous wording, assigned topic and difficulty, exam relevance, uniqueness, verified solution, and checked calculations. | Reject the question and regenerate within a fixed attempt limit. | Rule-based validators, curated examples, and mutation tests. |
| FP-10 | P0 | Verify the source and date for every current-affairs question. | Reject questions without traceable evidence. | Source-contract and citation-age tests. |
| FP-11 | P0 | Never expose secrets, student data, internal paths, raw provider errors, memory files, or admin configuration. | Redact before persistence or notification; treat leakage as a release blocker. | Secret scanning, log inspection, and error-redaction tests. |
| FP-12 | P0 | Authorize every request using registered, active, non-blocked identity and role. | Deny by default and audit the decision. | Student, moderator, administrator, blocked-user, and unknown-user tests. |
| FP-13 | P0 | Require administrator identity, role, and permission for every admin command. | Reject unauthorized commands without revealing protected information. | Privilege-escalation and audit-log tests. |
| FP-14 | P0 | Isolate progress, reports, history, memory, statistics, and active sessions by user. | Stop processing on missing tenant scope; never fall back to a shared record. | Cross-user access and property-based isolation tests. |
| FP-15 | P0 | Protect quiz submission, report generation, memory updates, and leaderboard updates from races. | Serialize or use optimistic concurrency; reject stale writes. | Parallel request and conflict tests. |
| FP-16 | P0 | Resume unfinished quizzes, pending reports, and scheduled jobs after a restart. | Continue from the last durable checkpoint without duplicate delivery. | Process-kill, restart, and replay tests. |
| FP-17 | P1 | Record startup, shutdown, errors, warnings, generation, validation, registration, reports, cron runs, model switches, and searches. | Continue safely if optional telemetry is unavailable; never log secrets. | Structured-log schema and redaction tests. |
| FP-18 | P1 | Run Telegram, model, memory, storage, scheduler, internet, and current-affairs health checks every 30 minutes. | Store a health report and alert only on meaningful state changes or repeated failure. | Scheduled health-check and alert-deduplication tests. |
| FP-19 | P0 | Alert administrators about provider loss, bot disconnection, corruption, storage exhaustion, repeated generation failure, authentication failure, profile mismatch, and unexpected restart. | Route by severity, deduplicate, and include a safe recovery action. | Alert routing, throttling, and masked-payload tests. |
| FP-20 | P0 | Back up profiles, progress, reports, question bank, settings, and admin configuration. | Fail the backup job visibly without blocking normal reads; protect backup credentials separately. | Daily, weekly, and monthly backup job tests. |
| FP-21 | P0 | Verify that backups can be decrypted, read, and restored into an isolated environment. | Mark unverifiable backups unusable and alert immediately. | Scheduled restore drills and integrity checks. |
| FP-22 | P0 | Block delivery unless environment, model, question, memory, security, authorization, cron, and bot gates required for that operation pass. | Stop safely and identify the failed gate without exposing internals. | End-to-end gate orchestration tests. |

## Validation sequence

The platform should evaluate gates in this order:

1. Load and validate the intended profile and environment.
2. Validate secrets without printing their values.
3. Verify Telegram bot identity and permissions.
4. Check storage, memory, database, scheduler, timezone, and clock.
5. Check primary and fallback model providers.
6. Check internet, search, and current-affairs sources when the request needs them.
7. Authenticate and authorize the user.
8. Acquire the operation-specific lock or idempotency key.
9. Generate and validate content.
10. Validate the destination and message representation.
11. Persist the pending operation, send it, and record the final outcome.

A later gate must never compensate for an earlier failed identity, security, or authorization gate.

## Degraded modes

Safe degraded behavior must be explicit and tested:

- Model primary unavailable: use only the configured fallback model.
- Search or current-affairs provider unavailable: disable current-affairs generation; allow verified static subjects.
- Memory or database temporarily unavailable: permit read-only activity where safe, queue encrypted progress updates, and show that progress is pending.
- Telegram API unavailable: retain an idempotent outbound message record and retry within a bounded window.
- Scheduler unavailable: allow interactive requests if their own gates pass; do not imitate missed scheduled jobs without duplicate protection.
- Observability provider unavailable: continue essential work with a bounded local diagnostic buffer.

There is no degraded mode for profile mismatch, wrong bot identity, failed authorization, suspected data mixing, invalid questions, or secret exposure.

## Alerts and diagnostics

Alerts should use four severities:

- Critical: wrong environment or bot, authorization bypass, data isolation failure, secret exposure, corrupted primary data, or failed recovery.
- High: bot disconnected, no model available, storage unwritable, rollback or restore failure, or scheduler stopped.
- Medium: fallback model in use, current-affairs provider unavailable, repeated question rejection, or delayed memory persistence.
- Low: transient provider error recovered within the retry budget.

Every alert should contain the profile, environment, affected component, safe error category, first occurrence, retry count, correlation ID, and operator action. It must not contain tokens, student content, raw provider responses, internal paths, or database records. Repeated alerts should be grouped until the state changes.

## Recovery and data protection

State-changing operations need an idempotency key, durable status, and checkpoint. The minimum states are `pending`, `in_progress`, `delivered`, `failed`, and `recovery_required`. A restart must reconcile incomplete records before accepting duplicate work.

Backups should be encrypted, access-controlled, and separated from the primary store. Retention must cover daily, weekly, and monthly recovery points. A backup is not considered successful until checksum validation completes. Restore drills should run in an isolated environment and verify record counts, relationships, tenant isolation, and application readability.

Recovery-time and recovery-point objectives require business approval before implementation. The tests should use those approved values instead of inventing thresholds.

## Proposed automation layers

- Deterministic tests: validators, authorization, message limits, secret masking, state transitions, and question rules.
- Contract tests: Telegram, model, search, memory, database, storage, and current-affairs adapters against sandboxes or controlled fakes.
- Fault-injection tests: timeouts, invalid credentials, permission loss, malformed responses, rate limits, partial writes, process termination, and clock drift.
- End-to-end tests: registration, quiz delivery, submission, progress update, reporting, scheduled delivery, restart recovery, and administrator alerts.
- Security tests: role bypass, cross-user access, injection, unsafe Markdown and links, log leakage, dependency scanning, and secret scanning.
- Recovery tests: backup integrity, isolated restore, pending-operation replay, and duplicate suppression.

## Implementation phases

Phase 1 establishes configuration validation, secret masking, identity checks, authorization, tenant isolation, idempotency, and fail-closed quality gates.

Phase 2 adds provider contracts, fallback-model behavior, Telegram delivery validation, question validators, scheduled-job locks, and structured diagnostics.

Phase 3 adds restart recovery, encrypted pending operations, administrator alert routing, backup schedules, and automated restore verification.

Phase 4 adds controlled chaos testing, rate-limit behavior, regional health checks, capacity tests, and measured recovery objectives.

## Exit criteria for a future production release

- All P0 requirements have automated evidence.
- Wrong-profile and wrong-bot tests prove that no message is sent.
- Cross-user isolation and privilege tests pass.
- Provider outage tests demonstrate the documented degraded behavior.
- Restart tests recover work without duplicate messages or lost progress.
- Logs and alerts pass secret and personal-data inspection.
- A recent isolated restore drill succeeds.
- Known exclusions, owners, and expiry dates are recorded in the release decision.
