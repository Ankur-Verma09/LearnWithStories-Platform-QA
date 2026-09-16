# Learn With Stories Platform QA

This repository tests the release path used by Learn With Stories at the Cloudflare edge. The production application serves its browser assets from a Cloudflare Worker and forwards `/api/*` to a private service through a Cloudflare VPC binding. The release checks in this repository use a separate Worker so failed deployments, timeouts, and rollbacks can be exercised without changing production.

The test target is a small release controller written in Python. It uploads an immutable Worker version with Wrangler, activates that version through the Cloudflare API, checks the public health endpoint, and restores the previous version when verification fails. Pytest drives the controller and compares three views of the result: the controller outcome, Cloudflare deployment state, and the response served by the Worker.

## Why this workflow

A successful upload is not enough to call a release healthy. A Worker may deploy correctly and still return errors, expose the wrong content, or take too long to respond. The highest-risk case is a partially completed release: the new version receives traffic but its verification fails. The controller treats that as a failed release and restores the version that was active before the attempt.

This scope was chosen because it covers the release behavior that matters without requiring changes to the Learn With Stories application or its private Dell service. The live tests target `learn-with-stories-qa`. They do not stop the tunnel, change the VPC service, or deploy to `learn-with-stories`.

## Workflow under test

```text
Read active Worker version
        |
Validate and upload a new version
        |
Activate the version at 100% traffic
        |
Call the public health endpoint
        |
   +----+----+
   |         |
 healthy   failure or timeout
   |         |
 accept    restore previous version
             |
        verify restored state
```

The fixtures provide three deterministic releases:

- `healthy` returns `200` from `/health` with the marker `healthy`.
- `unhealthy` deploys successfully but returns `500` from `/health`.
- `slow` deploys successfully but responds after the configured verification deadline.

## What is tested

The automated suite covers:

- successful version upload and activation;
- invalid local configuration;
- rejected Cloudflare authentication;
- deployment state returned by the Cloudflare API;
- live content and security-header validation;
- a post-deployment health failure;
- a health-check timeout;
- automatic restoration of the previous version;
- preservation of the failure that caused the rollback;
- protection against accidentally targeting the production Worker.

The detailed requirements, cases, priorities, and automation links are in [docs/test-specification.md](docs/test-specification.md).
The presentation sequence is documented in [docs/live-demo.md](docs/live-demo.md).

## Repository layout

```text
fixtures/                 Worker versions used by live tests
src/cloudflare_qa/        Cloudflare client and release controller
tests/unit/               Deterministic controller and client tests
tests/live/               Tests that change the isolated QA Worker
docs/                     Test specification and remaining work
.github/workflows/        Pull-request and live release gates
```

## Prerequisites

- Python 3.11 or newer, installed directly or through `uv`
- Node.js 20 or newer
- A Cloudflare account with Workers enabled
- A dedicated QA Worker name
- An API token scoped to Workers Scripts Edit for the required account

Wrangler is executed as `npx --yes wrangler@4.37.1` on Linux and `npx.cmd --yes wrangler@4.37.1` on Windows; a global installation is not required.

## Local setup

Create and activate a virtual environment, then install the project:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

If the Windows `py` launcher is unavailable, use the existing `uv.exe` installation:

```powershell
$uv = "$env:LOCALAPPDATA\hermes\bin\uv.exe"
& $uv python install 3.11
& $uv venv --python 3.11 .venv
& $uv pip install --python .\.venv\Scripts\python.exe -e ".[test]"
```

PowerShell may block `npx.ps1` under a restricted execution policy. Use `npx.cmd` instead; changing the machine-wide execution policy is not required.
If virtual-environment activation is also blocked, run `.\.venv\Scripts\python.exe` and `.\.venv\Scripts\cf-release.exe` directly as shown in the live demo runbook.

Run the deterministic suite:

```powershell
pytest -m "not live"
```

The first live run needs a QA Worker. The controller can create the script during the first Wrangler upload. Set the credentials only in the current shell:

```powershell
$env:CLOUDFLARE_ACCOUNT_ID = "your-account-id"
$env:CLOUDFLARE_API_TOKEN = "your-scoped-token"
$env:CLOUDFLARE_QA_WORKER_NAME = "learn-with-stories-qa"
$env:CLOUDFLARE_QA_URL = "https://learn-with-stories-qa.your-subdomain.workers.dev"
```

Do not place a token in `.env`, a Wrangler configuration file, test output, or source control.

Bootstrap the QA Worker with the healthy fixture:

```powershell
cf-release deploy --fixture fixtures/healthy --expected-marker healthy --timeout 15
```

Run the live suite:

```powershell
pytest --run-live -m live --junitxml=reports/live-results.xml
```

Generate a local HTML report when required:

```powershell
pytest -m "not live" --html=reports/unit-report.html --self-contained-html
```

## Command-line interface

Deploy and verify a fixture:

```powershell
cf-release deploy --fixture fixtures/healthy --expected-marker healthy --timeout 15
```

Inspect the current Cloudflare deployment:

```powershell
cf-release status
```

Restore a known version:

```powershell
cf-release rollback --version-id <version-id>
```

Every command prints one JSON document and returns a nonzero exit code on failure. Tokens are never included in command output.

## CI release gates

The `quality-gate` job runs on every push and pull request. It installs the package, runs the deterministic tests, and uploads the JUnit result even when a test fails.

The `cloudflare-live` job is intentionally manual. It uses a protected GitHub environment named `cloudflare-qa` and requires these repository secrets:

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_QA_WORKER_NAME`
- `CLOUDFLARE_QA_URL`

Keeping the live job behind an environment prevents code from an untrusted pull request from receiving deployment credentials. The job targets only the configured QA Worker and refuses the production name `learn-with-stories`.

Configure branch protection so `quality-gate` is required for pull requests. Run `cloudflare-live` before a release or after changes to the release controller.

## Cleanup and recovery

Each failure test records the version that was active before it starts. Its cleanup restores that version if the assertion fails halfway through. The suite does not delete the QA Worker because retaining the last healthy version makes investigation possible. Delete the QA Worker from Cloudflare only when the assessment environment is no longer needed.

If a live test is interrupted, list the recent versions and restore the known healthy version:

```powershell
npx.cmd --yes wrangler@4.37.1 versions list --name learn-with-stories-qa --json
npx.cmd --yes wrangler@4.37.1 rollback <version-id> --name learn-with-stories-qa --message "manual test recovery"
```

## Scope decisions

This suite validates a single Worker at 100% traffic. It does not change the production Worker, Cloudflare Access policy, VPC service, tunnel configuration, or the private application database. Gradual traffic splitting, Access identity flows, tunnel interruption, load testing, and browser coverage are documented as follow-up work rather than being approximated in the timebox.

## Submission notes

The repository should be submitted with its commit history and the exported AI conversation requested by the assessment. Add the complete exported conversation to `docs/ai-interaction-log.md` before submission; the decision record currently in that file is not a substitute for the verbatim export.
