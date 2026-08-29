# Security: harden release/CI supply chain and audit historical Actions (#19)

Closes #19. This PR starts from merged runtime/frontend hardening PR #21 and keeps issue #20 out of scope. It does not change VISTA runtime, control, or parser behavior.

## Historical audit conclusion

The five named commits and surrounding temporary validator runs were checked against local Git history, GitHub Actions run/job metadata and hosted logs, remote branch refs, tags, and the current RC11 release. The complete note is [docs/security/historical-actions-audit.md](docs/security/historical-actions-audit.md).

The historical workflows had a genuine vulnerable design: branch-controlled patch/test code ran with an ephemeral `GITHUB_TOKEN` that had `contents: write`, and checkout persisted credentials. The audit found two expected bot mutations: `f0367702fa9652a5e153ae1971a0598686ab9f42` on `fix/editor-focus` and `0b16430063f01ebfb73bac7e45ef71ab0123f0e5` on `feature/alarm-binary-sensors`. Failed runs stopped before their write step. No evidence of credential misuse, unexpected repository mutation, long-lived credential exposure, tag tampering, release tampering, suspicious artifacts, or unusual network activity was found. No rotation, history rewrite, tag deletion, or release cleanup was warranted.

## Completed #19 criteria

### Normal CI

- `.github/workflows/tests.yml` now declares `contents: read` at workflow and job level.
- Every checkout sets `persist-credentials: false`.
- Every active third-party action is pinned to a full upstream commit SHA with its human-readable release beside it:
  - `actions/checkout` `11bd71901bbe5b1630ceea73d27597364c9af683` (`v4.2.2`)
  - `actions/setup-python` `a26af69be951a213d495a4c3e4e4022e16d87065` (`v5.6.0`)
  - `actions/setup-node` `49933ea5288caeca8642d1e84afbd3f7d6820020` (`v4.4.0`)
  - `actions/upload-artifact` `ea165f8d65b6e75b540449e92b4886f43607fa02` (`v4.6.2`)
  - `actions/download-artifact` `634f93cb2916e3fdff6788551b99b062d0335ce0` (`v5.0.0`)
- Normal tests do not commit or push and now use `npm ci`.

### Release-candidate boundary

- `validate` is read-only (`contents: read`, `checks: read`, `actions: read`), checks out the exact `github.sha` without credential persistence, validates metadata, waits for the exact commit's newest successful GitHub Actions `test`, `frontend-render`, and `repository-security` checks, and uploads a one-day artifact named for that SHA.
- `publish` is the only job with `contents: write`; it has no checkout and executes only the fixed release publication shell path after downloading the SHA-bound artifact. It receives `actions: read` only in addition to the required contents write.
- `release/rc.json` must contain exactly `tag`, `name`, and `notes`. Tags must match `vMAJOR.MINOR.PATCH-rc.NUMBER`; names are bounded to 120 safe printable characters; notes must be an existing regular `.md` file below `release/`, with no absolute path, traversal component, backslash, or escaping symlink. Publication uses fixed bundle names `notes.md`, `vista-keypad-card.js`, and `vista-keypad-simulator.html`.
- Before any tag/release write, the workflow verifies the exact release SHA. Missing tags are created only at that SHA; existing lightweight or annotated tags are dereferenced and mismatches hard-fail. Existing releases must be the expected prerelease, non-draft release, and their downloaded expected assets must match the validated SHA-256 identities. Existing unrelated/mismatched releases hard-fail; a matching rerun exits idempotently.
- The workflow no longer runs merely because the publication workflow file changes; release metadata changes remain the deliberate publication trigger.

### Supply-chain inputs

- `vista128_bridge/Dockerfile` now uses Home Assistant base `3.24` with immutable multi-architecture manifest digest `sha256:93ef607824e3f27e868f11b10938283a98bf880ed57bcf8eaa81c6c2d521f6f5`, verified from GHCR. Its manifest supports Linux `amd64` and `arm64` for the add-on's `amd64` and `aarch64` targets.
- `paho-mqtt==2.1.0` remains pinned and now uses pip `--require-hashes` for the reviewed wheel and source distributions.
- `@playwright/test` is upgraded from `1.55.0` to `1.62.1`; the lockfile is refreshed consistently.
- Alpine packages remain selected by the immutable Home Assistant base's supported repositories rather than brittle exact APK versions. Exact APK freezing was deliberately left incomplete because it would make routine add-on builds unreliable against those repositories; this limitation is documented in the audit note.

### Regression guardrails

`scripts/check_repository_security.py` is a read-only repository check run by CI. It fails for mutable action refs, normal-workflow write permissions, persisted checkout credentials, production `:latest` base images, unsafe release metadata, and ordinary test-workflow commit/push behavior. Unit tests cover valid pins, each policy failure, metadata traversal/symlink rejection, newest-check success rules, and mismatched tag/release identity handling.

## Deliberately incomplete

- Exact Alpine package-version pinning is not used for the concrete compatibility reason above; the base image is pinned by digest and the limitation is documented.
- The panel runtime and the full semantic keypad parser from issue #20 are intentionally untouched.
- GitHub's repository-level default Actions permission setting cannot be changed from repository content; workflow-level and job-level permissions now explicitly enforce read-only normal CI, with write isolated to the trusted release job.

## Migration notes

- No application configuration migration is required.
- Release maintainers must keep release notes under `release/` as `.md` files and use the exact three-field `release/rc.json` schema. Moving a note outside that directory or using a non-RC tag now fails closed.
- A release workflow-only change does not publish a release. Update `release/rc.json` deliberately when preparing the next candidate.
- CI installs frontend dependencies from `package-lock.json` with `npm ci`; local contributors should use the same command.

## Tests and validation

- `python -m unittest discover -s scripts -p 'test_*.py' -v` — 10 passed.
- `python scripts/check_repository_security.py` — passed.
- Both active workflow YAML files parsed successfully with PyYAML.
- `python -m py_compile scripts/*.py` — passed.
- `python -m pip install --dry-run --require-hashes --no-deps -r vista128_bridge/requirements.txt` — passed.
- `cd vista128_bridge && python -m unittest discover -s tests -v` — 156 passed locally and in CI.
- `cd vista128_bridge && python -m py_compile app/vista_bridge/*.py tests/*.py` — passed locally.
- `cd vista128_bridge && node --check ../frontend/vista-keypad-card.js` — passed locally.
- `cd frontend && npm ci --no-audit --no-fund` — passed locally and in CI.
- `cd frontend && npx playwright install --with-deps chromium` — local apt dependency installation was blocked by the managed runner's restricted privilege transitions.
- `cd frontend && npx playwright install chromium --only-shell` — local browser download timed out; the browser-only fallback could not complete in this environment.
- `cd frontend && npm run test:render` — the local run could not start because the new browser executable was unavailable after the download failure; the GitHub Actions runner completed all 49 tests successfully.
- GitHub Actions push run `33259517815` and PR run `33259532639` — `test`, `frontend-render`, and `repository-security` all passed; `frontend-render` reports 49 passed.
- Docker build validation — Docker is not installed in this environment. The GHCR `3.24` manifest was inspected and confirmed to contain Linux `amd64` and `arm64` entries with the pinned digest.
- `git diff --check` — passed locally.

Known remaining security limitation: the panel serial-server transport remains unauthenticated plaintext by design, but that is outside #19's repository trust boundary and is documented in the runtime documentation. Within the repository/release boundary, no known path now grants normal test execution repository-write credentials or accepts a mismatched release identity.
