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

At this checkpoint, recovered JavaScript passes syntax validation. Previously
reported test results belong to the lost checkout, not this reconstruction.
Restoring regression tests and running fresh verification remains in progress.
