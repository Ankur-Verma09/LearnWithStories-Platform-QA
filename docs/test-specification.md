# Test specification

## Objective

Prove that the Learn With Stories QA Worker can be released through a repeatable workflow and returned to a known-good version when post-deployment checks fail. The test boundary starts at the Python release command, continues through Wrangler and the Cloudflare API, and ends at the public Worker response.

## Requirements

| ID | Requirement | Risk addressed |
|---|---|---|
| R-01 | The release controller must refuse the production Worker name. | A test changes the live application. |
| R-02 | A release fixture must contain both Worker source and Wrangler configuration. | An incomplete package reaches Cloudflare. |
| R-03 | The controller must record the active version before making a change. | There is no reliable rollback target. |
| R-04 | A candidate must be uploaded as an immutable version before activation. | Upload and activation cannot be inspected separately. |
| R-05 | Cloudflare must report the candidate as the active version after deployment. | A successful API response is mistaken for completed propagation. |
| R-06 | The public health response must return `200` and the expected release marker. | Cloudflare state and served content disagree. |
| R-07 | The health response must retain the agreed security headers. | A release weakens edge security. |
| R-08 | Invalid Cloudflare credentials must fail without being reported as a deployment defect. | Authentication errors are hidden or misclassified. |
| R-09 | A deployed version that fails health verification must restore the previous version. | A partial release remains active. |
| R-10 | A health request exceeding its deadline must restore the previous version. | A hanging version remains active. |
| R-11 | A failed release must return a nonzero CLI exit code and retain the original failure reason. | CI reports a false pass or loses diagnostic evidence. |
| R-12 | Pull-request and live tests must run in CI with machine-readable results. | The suite cannot act as a release gate. |

## Test cases

| ID | Priority | Scenario | Expected result | Automation |
|---|---|---|---|---|
| TC-01 | P0 | Configure the controller with the production Worker name. | Configuration is rejected before any API or Wrangler call. | `test_rejects_production_worker` |
| TC-02 | P1 | Load a complete QA configuration. | Values are normalized and accepted. | `test_reads_qa_configuration` |
| TC-03 | P1 | Omit required configuration. | All missing fields are reported together. | `test_reports_all_missing_configuration` |
| TC-04 | P0 | Activate a healthy candidate. | Candidate becomes active; no rollback occurs. | `test_accepts_healthy_candidate`, `test_successful_release_is_active_and_serving` |
| TC-05 | P0 | Candidate health check returns `500`. | Previous version is restored and the HTTP failure is reported. | `test_rolls_back_after_health_failure`, `test_unhealthy_release_restores_previous_version` |
| TC-06 | P0 | Candidate health check exceeds its deadline. | Previous version is restored and timeout is reported. | `test_rolls_back_after_health_timeout`, `test_slow_release_times_out_and_restores_previous_version` |
| TC-07 | P1 | Cloudflare returns an authentication error. | Status and public API error are surfaced without exposing the token. | `test_surfaces_cloudflare_error_without_token` |
| TC-08 | P1 | Deployment contains more than one traffic percentage. | The version with the highest percentage is treated as active. | `test_returns_version_with_highest_traffic_percentage` |
| TC-09 | P1 | Health response contains the expected marker and headers. | Response is accepted and headers remain available for assertions. | `test_accepts_expected_release_and_security_headers` |
| TC-10 | P1 | Health endpoint returns a different marker. | Verification fails even though HTTP status is `200`. | `test_rejects_wrong_release_marker` |
| TC-11 | P1 | First deployment fails and no baseline exists. | Failure is reported without claiming a rollback occurred. | `test_reports_failure_without_rollback_when_no_baseline_exists` |
| TC-12 | P1 | Create a single-version deployment. | Request assigns 100% of traffic to the candidate. | `test_creates_single_version_deployment` |

## Traceability summary

| Requirement | Covered by |
|---|---|
| R-01 | TC-01 |
| R-02 | `test_rejects_incomplete_fixture`, `test_surfaces_wrangler_failure` |
| R-03 | TC-04, TC-05, TC-06, TC-11 |
| R-04 | TC-04, TC-05, TC-06 |
| R-05 | TC-04, TC-08 |
| R-06 | TC-04, TC-09, TC-10 |
| R-07 | TC-09 and live security-header assertions |
| R-08 | TC-07 and `test_invalid_token_is_rejected_by_cloudflare` |
| R-09 | TC-05 |
| R-10 | TC-06 |
| R-11 | `test_failed_release_returns_nonzero_exit_code`, `test_healthy_release_returns_success` |
| R-12 | `.github/workflows/quality-gate.yml` |

## Failure injection

The unhealthy and slow Workers are intentionally valid deployment packages. Cloudflare can upload and activate them, which moves the workflow beyond input validation and creates the partial-failure condition under test.

The unhealthy fixture returns `500` from `/health`. The slow fixture waits five seconds while the release controller allows only half a second in the live timeout test. In both cases, the suite asserts the candidate was attempted, the previous version became active again, and the restored Worker passed health verification.

## Test data and independence

Each upload receives a unique tag. Live tests establish a healthy baseline before injecting a failure and record its version ID. Cleanup is a state transition back to that version rather than deletion of shared Worker history. Tests use only the configured QA Worker.

The deterministic tests replace Cloudflare, Wrangler, and health transport at process boundaries. They do not require network access and run for every pull request. Credentialed tests exercise the real Cloudflare API and Worker hostname through the same production code.

## Entry and exit criteria

Entry criteria:

- deterministic tests pass;
- the QA Worker name is not the production name;
- required secrets are available in the protected CI environment;
- the account token is limited to the intended Cloudflare account.

Exit criteria:

- all P0 tests pass;
- no test leaves an unhealthy or slow version active;
- JUnit results are attached to the workflow;
- any rollback failure blocks the release and requires manual recovery.

## Deliberate exclusions

- Production deployment is excluded because destructive failure tests are not appropriate on a user-facing Worker.
- Cloudflare Access login is excluded because the QA Worker uses a separate deployment boundary and no service token has been provisioned.
- VPC tunnel interruption is excluded because the existing tunnel serves the real application.
- Gradual traffic splits are specified as future work; a deterministic affinity strategy is needed first.
- Load, browser compatibility, and database behavior are outside this release-controller timebox.
- Cloudflare availability itself is not tested. API errors are handled, but the suite does not attempt to validate the provider's internal implementation.
