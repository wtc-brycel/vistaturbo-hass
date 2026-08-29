# Historical Actions security audit

Audit date: 2026-08-29
Repository: `wtc-brycel/vistaturbo-hass`
Current audited `main`: `c4d4630318efa38ed27cf61d5ad8eaea6a2014e6`

## Method

The audit used the local Git object database and remote GitHub repository state. For each named commit, the workflow file at that exact commit was inspected, then GitHub Actions run metadata, job steps, and hosted logs were queried. Resulting commits, branch refs, tags, and the current RC11 release were cross-checked with the repository's Git refs and commit graph. Logs were searched for checkout credential persistence, token permissions, branch-controlled scripts, commits, pushes, tags, releases, assets, and unusual network commands.

The hosted logs expose the token permission summary, but GitHub masks the token value. No long-lived credential was present in the workflow definitions or visible logs; the credential source was the ephemeral Actions `GITHUB_TOKEN`.

## Findings by named commit

| Commit | Relevant run(s) | Effective boundary and result |
| --- | --- | --- |
| `273547c9fca39c8c781d9cd18613d583d3d9d9d1` | `32526666311`, push to `main` | The exact `tests.yml` had `contents: write` and checkout persisted credentials. The normal test and frontend jobs passed; the conditional editor-apply job was skipped. No repository mutation was observed. |
| `626359a98df5ea30553508af51578d98fabc59c9` | `32526737917`, push; `32526754276`, pull request; `32526754281`, pull-request tests; `32526738001`, apply push | `editor-focus-apply.yml` granted `contents: write` and used checkout credential persistence. The branch-controlled patch ran in all applicable apply jobs. The exact runs failed with one browser test failure and the commit/push step was skipped. No mutation resulted from those failed runs. |
| `ccd8962e1777d61e1159788395c8317fdb759b55` | `32528315344`, push to `feature/alarm-binary-sensors` | `apply-alarm-binary-sensors.yml` granted `contents: write`, persisted checkout credentials, ran a branch-controlled patch, then passed 37 browser tests and committed/pushed `0b16430063f01ebfb73bac7e45ef71ab0123f0e5`. This was an expected workflow mutation, not evidence of misuse. |
| `fc16489ea3bf8b9a5ca7482548c7e9b308602793` | `32528652233`, apply push; `32528652101`, normal tests | The apply workflow had the same write/persistent-checkout boundary. Its patch ran, but backend validation failed and commit/push was skipped. The separate normal test run passed. No mutation resulted. |
| `062c910a7e2f5dbd838db5f79e8000b5937e738d` | `32528746843`, normal tests; `32528755067`, temporary validator on follow-up `582a05bd25b9be2033f9f2e052295916de1f392a` | The temporary validator workflow declared `contents: write`, persisted checkout credentials, ran branch-controlled patch scripts, and could push to `feature/alarm-binary-sensors`. The associated normal tests had read-only effective contents permission but persisted checkout credentials. The temporary validator ran on the follow-up trigger, failed its tests, and skipped commit/push. No mutation resulted. |

## Surrounding runs and repository state

The nearby successful editor validator run `32526864759` ran the same write-capable workflow with `contents: write` and persisted checkout credentials. It committed/pushed the expected bot commit `f0367702fa9652a5e153ae1971a0598686ab9f42`, `Keep visual editor focus stable`, to `fix/editor-focus`. Its paired pull-request run `32526869747` passed validation and correctly skipped its push step. Later cleanup commits removed the temporary workflow; the current ref is `80e38a9a0973e40f2f8745caaf71d457c1ae70ce`.

The alarm/global-alarm retriggers following the named commits all failed before their commit steps. Their logs show the expected test/fixture failures, including missing `publish_alarm_states` test doubles and missing alarm topics; no unexpected network command, tag, release, or asset operation was observed.

The action-created alarm commit `0b16430` is present as a Git object with parent `ccd8962`; the current `feature/alarm-binary-sensors` ref is `7a9e11302e6189e4b6c4fb029eb761890e595daf`, so the bot commit is no longer the branch tip. The current `fix/editor-focus` ref is `80e38a9a0973e40f2f8745caaf71d457c1ae70ce`. No historical run created or modified a tag or release in the audited set.

The current RC mechanism was also cross-checked: tag `v0.2.6-rc.11` resolves to `c4d4630318efa38ed27cf61d5ad8eaea6a2014e6`; its prerelease has the same `target_commitish`, and its two uploaded assets are present with uploaded state and matching SHA-256 digests. No mismatch or unexplained asset was found.

## Conclusion

The historical workflows had a real vulnerable design: branch-controlled code ran with an ephemeral repository-write token available through persisted checkout credentials. One editor validation run and one alarm validation run performed the writes their scripts explicitly requested. Those mutations are visible, expected, and attributable to `github-actions[bot]`; no evidence of credential misuse, unexpected repository mutation, long-lived credential exposure, tag tampering, release tampering, or suspicious artifact/network activity was found. Failed runs did not reach their write steps. No credential rotation, history rewrite, tag deletion, or release cleanup is warranted by the evidence.

Active workflows now use immutable action pins, explicit read-only permissions for tests, and non-persistent checkout credentials. Release publication is separated into a read-only validation job and a narrowly scoped write job.

## Reproducibility notes

- `vista128_bridge/Dockerfile` uses Home Assistant base `3.24` pinned to its multi-architecture manifest digest. The manifest contains Linux `amd64` and `arm64` images, matching the add-on's `amd64` and `aarch64` configuration.
- `paho-mqtt==2.1.0` remains reviewed and is installed with hashes for both the wheel and source distribution. Alpine packages remain `apk`-selected from the immutable Home Assistant base repositories; exact APK versions are intentionally not frozen because that would make the add-on brittle against the base's supported repositories. The immutable base digest constrains the package universe and this limitation is explicit.
- Frontend tests use `@playwright/test` `1.62.1` with a refreshed npm lockfile.
