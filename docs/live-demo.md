# Live demo runbook

## Preparation

Use the dedicated Worker `learn-with-stories-qa`. The production Worker is blocked by the release controller.

Create a Cloudflare API token from the **Edit Cloudflare Workers** template and limit it to the account that owns Learn With Stories. Keep the token in the current shell or a GitHub secret; do not save it in this repository.

Set the live-test values in PowerShell:

```powershell
$env:CLOUDFLARE_ACCOUNT_ID = "your-account-id"
$env:CLOUDFLARE_API_TOKEN = "your-scoped-token"
$env:CLOUDFLARE_QA_WORKER_NAME = "learn-with-stories-qa"
$env:CLOUDFLARE_QA_URL = "https://learn-with-stories-qa.aaankurankur.workers.dev"
```

Confirm Node.js and the existing `uv.exe` installation are available:

```powershell
node --version
npx.cmd --version
$uv = "$env:LOCALAPPDATA\hermes\bin\uv.exe"
& $uv --version
```

Install Python 3.11 and the test package through `uv`:

```powershell
& $uv python install 3.11
& $uv venv --python 3.11 .venv
& $uv pip install --python .\.venv\Scripts\python.exe -e ".[test]"
```

Use `npx.cmd` and the executables under `.venv\Scripts` throughout the demo. This avoids blocked PowerShell scripts without changing the Windows execution policy.

## One-time QA Worker bootstrap

Create a healthy baseline before demonstrating rollback:

```powershell
npx.cmd --yes wrangler@4.37.1 deploy `
  --config fixtures/healthy/wrangler.jsonc `
  --name learn-with-stories-qa
```

Open the health endpoint and confirm the marker is `healthy`:

```powershell
Invoke-RestMethod "$env:CLOUDFLARE_QA_URL/health"
```

## Presentation sequence

### 1. Show the test strategy

Open `docs/test-specification.md`. Point out the P0 cases for successful activation, partial failure, timeout, rollback, and production isolation.

### 2. Run the deterministic gate

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not live" -q
```

Expected result: all deterministic tests pass and live tests are deselected.

### 3. Demonstrate a successful release

```powershell
.\.venv\Scripts\cf-release.exe deploy `
  --fixture fixtures/healthy `
  --expected-marker healthy `
  --timeout 10
```

The JSON output should report `healthy`, a new version ID, and `rolled_back: false`.

```powershell
.\.venv\Scripts\cf-release.exe status
Invoke-RestMethod "$env:CLOUDFLARE_QA_URL/health"
```

The version reported by the CLI should be active, and the public endpoint should return the `healthy` marker.

### 4. Demonstrate partial failure and rollback

```powershell
.\.venv\Scripts\cf-release.exe deploy `
  --fixture fixtures/unhealthy `
  --expected-marker unhealthy `
  --timeout 10
```

The command intentionally returns a nonzero exit code. Its JSON output should show:

```text
status: failed
rolled_back: true
error: Health endpoint returned HTTP 500
```

Confirm that the previous release is serving traffic again:

```powershell
.\.venv\Scripts\cf-release.exe status
Invoke-RestMethod "$env:CLOUDFLARE_QA_URL/health"
```

### 5. Demonstrate timeout recovery

```powershell
.\.venv\Scripts\cf-release.exe deploy `
  --fixture fixtures/slow `
  --expected-marker slow `
  --timeout 0.5
```

The command should report a timeout and `rolled_back: true`. The public health endpoint should again return `healthy` after rollback.

### 6. Run the complete live suite

```powershell
.\.venv\Scripts\python.exe -m pytest --run-live -m live -q --junitxml=reports/live-results.xml
```

Show the JUnit file and the Cloudflare deployment history. The history should contain the attempted unhealthy and slow versions followed by deployments that restore the recorded healthy version.

## CI demonstration

Push `assessment/cloudflare-platform-qa` to GitHub. Add the four Cloudflare values as secrets in the protected `cloudflare-qa` environment. The normal quality gate runs on pushes and pull requests. Start the live job from **Actions → Platform QA → Run workflow**.

## Recovery

If the demo terminal closes during a failure test, find the healthy version and restore it:

```powershell
npx.cmd --yes wrangler@4.37.1 versions list `
  --name learn-with-stories-qa `
  --json

npx.cmd --yes wrangler@4.37.1 rollback <healthy-version-id> `
  --name learn-with-stories-qa `
  --message "demo recovery"
```
