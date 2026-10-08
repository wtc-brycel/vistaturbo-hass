# Ingress and state-delivery recovery checkpoint

The previous local checkout was lost during an execution-workspace reset before
publication. This branch reconstructs its source changes on verified upstream
main `e20cc10` and ingress `67780df`; the prior local commit `2ac057f` was not
recovered and is not represented as the current commit.

Recovered source:
- Publish reconciled state before asserting freshness, including MQTT recovery
- Retry rejected synchronization delivery without querying the panel again
- Include zone-summary counts/lists in periodic retained-state delivery repair
- Preserve the latest received ZS/05/06 bypass evidence for ingress inspection
- Add a read-only Zones view with current-versus-historical masking, filters,
  responsive layout, browser navigation, and synchronization/watchdog health

The observed stale-bypass incident has no confirmed root cause. These are
verified source-level delivery gaps, not proof of the cause at the installation.
No bypass is cleared by age, disarm inference or historical events. Panel state
remains authoritative. No merge, release, deployment or live panel command is
part of this work. No ZIP/download bundles are checked into the repository.

## Fresh reconstruction validation

- 342 backend tests pass on the reconstructed source
- 11 security/release helper tests pass; repository-security guardrails pass
- JavaScript, shell syntax and whitespace checks pass
- Five Playwright scenarios and production-built fixtures are restored for zone
  filtering, explicit restore, browser loss, panel reconnect, mobile text safety,
  and Back/Forward/repeated navigation (69 browser tests total when listed)
- Browser execution and exact-commit remote CI remain outstanding. Previous
  reports for the lost checkout do not establish a browser pass for this branch

## Confirmed delivery gaps

Normal synchronization and recovery previously asserted `panel/state_fresh=ON`
before replaying reconciled zone data. The new ordering publishes data first.
Rejected state delivery keeps the MQTT projection unavailable and requests a
retry via the existing recovery mechanism. Rejected freshness publication is
retried too. The periodic in-memory projection now repairs zone-summary lists
as well as individual zones, so a rejected summary update need not wait for an
unrelated panel event. Retained deduplication keeps unchanged data quiet.

Publication acceptance is not proof of broker consumption. The RC28 QoS-1
acknowledgement watchdog retains responsibility for transport liveness. Normal
panel reconciliation still queries Arming Status only, without recurring ZS
polls or forced resets. These changes repair publication, not physical state.

## Panel-state evidence and inspection

The Zones view separates current fault/trouble/alarm/bypass conditions from
historical last-received bypass evidence. Source labels identify ZS snapshots
or live 05/06 events; timestamps are receipt times, not inferred transitions.
Full freshness still requires both 64-zone status and partition blocks. Zone
identity tests cover 64, 65 and 128. Unknown/offline/suspended state cannot become
clear merely because stale cached values exist. A historical LD entry cannot
change live bypass state or overwrite its receipt provenance. Disarm, elapsed
time and unrelated zone restores do not manufacture an unbypass.

## Open-work review at upstream baseline

- PR #61 (RC28 recovery) and PR #62 (Diagnostic Journal) are merged
- PR #60 is still an unreleased draft requiring installed ingress acceptance
- Issue #16 remains broad state-integrity work; this does not close it wholesale
- Issue #43 already has a dedicated Telnet filter and fragmented-stream tests
  on the baseline. Its acceptance/status needs reconciliation, not a rewrite
- Issue #25 includes native outputs, bypass commands and native HA migration.
  Older native-integration branches were not blindly merged into this change
- Issue #47 remains installer-recovery research. No speculative force-exit,
  reset, BREAK, or downloader commands were added

## Installed acceptance, only after explicit deployment approval

1. Verify app version, the affected zone number and HA entity IDs. Compare the
   physical keypad, individual zone entity, summary and ingress Zones view
2. Verify admin/owner access and member denial, including role revocation,
   nested ingress URLs and WebSocket reconnection
3. Observe an operator-authorized bypass and restore. Confirm the same numeric
   zone follows panel 05/06 or authoritative ZS reports; inspect receipt evidence
4. Test panel and browser interruption separately. Cached conditions must stay
   unknown until a complete new snapshot is acquired
5. Test MQTT interruption with a healthy panel link. Recovery must repair both
   individual zone values and summaries without restarting the panel session
6. If the symptom recurs, collect zone/entity IDs, app version, receipt times and
   sanitized incident diagnostics. Do not include PINs, raw keys or credentials

Source changes have not been deployed or established as a fix for the live
incident. No installation or hardware-timing qualification is claimed.
