# Ingress workflow validation

Review: September 22, 2026. Scope: draft PR 60.

The branding header is removed. The persistent system-condition strip and four
existing destinations remain. Repeated overlines and descriptions are removed;
unknown-state reasons, read-only notices, command outcomes, and time provenance
remain because they change operator decisions. The existing keypad bundle is
unchanged.

## Data and workflow contract

| Surface | Actual source | Display and interaction rule |
| --- | --- | --- |
| System condition | `VistaState.panel_alarm_states()`, synchronization flags, power/battery evidence, current keypads, trouble/zone state | Positive global, partition, zone, and keypad alarm evidence takes priority. Missing evidence never becomes normal. |
| Current conditions | Existing alarm classes, partition/global trouble tokens, current KD trouble, validated zone bits | Fire, security, supervisory, trouble, bypass, and ordinary zone faults remain distinct. Cached values are not current readings. |
| Partitions | Configured keypad scope, known zone-to-partition assignments, positive conditions | Do not manufacture eight installed/normal partitions. Unknown mode/readiness is shown explicitly. |
| Last received event | In-memory `last_event` plus receive time and zone descriptor | Not the last event in the whole retained database; no initiating-point inference from this row. |
| Event Journal | Retained SQLite `events`, never PIN-bearing `keypad_interactions` | Fifty-row cursor pages; applied filters remain fixed until Apply. System scope is distinct from all partitions. Database browsing remains available when the panel is offline. |
| Event emphasis | `event_codes.py` canonical code mappings | A restore is historical restoration, not proof of current system normal. Code 07 is Close (Arm). English description matching cannot determine alarm family. |
| Keypad | Current selected KD, core snapshot, original control gates, shared coordinator | Ordinary numeric/*/# keys only. No invented A-D, acknowledge, silence, reset, programming, or user-management workflow. |
| Diagnostics | Current bridge health plus the structured Diagnostic Journal from ADR 0002 | Read-only. Current health remains live; retained diagnostics use bounded cursor pages, severity/category filters, and explicit newest/oldest ordering. Correlated recovery sequences are grouped as incidents, and selecting an incident shows its complete sequence regardless of category/severity filters while retaining the selected time order. No credentials, key sequences, raw payloads, private-key content, or diagnostic database paths are returned. |

## Keypad delivery

A press is submitted once to the app, never through a browser MQTT connection.
The app supplies the verified ingress actor. The request is bound to the app
instance, panel session generation, configured partition, CSRF token, and a
single transaction identifier. Duplicate submissions cannot enqueue the same
press twice during the bounded five-minute deduplication window. Conflicting
reuse is rejected; capacity exhaustion rejects rather than evicting a recent
request. The browser never automatically retries a key.

The existing coordinator still owns panel serialization, admission gates,
programming interlock, stale-session discard, and acknowledgement handling.
`Queued` is not success. `Key acknowledged` means only that the key transaction
was acknowledged; it does not prove the intended arming/disarming operation.
Control results returned to a browser are limited to that verified actor and
contain no key or PIN.

Browser connection loss immediately invalidates the display and controls. A
10-second snapshot watchdog also detects a connection that remains open without
useful updates. Reconnect, partition change, and session change discard the
component's pending local key chain before enabling fresh input.

## Ingress authorization

`panel_admin: true` restricts menu visibility, not backend access. The service
therefore checks the peer against Supervisor's ingress proxy, requires the
Supervisor-assigned user ID, and verifies an active human administrator or owner
using Home Assistant's `config/auth/list` WebSocket command. This requires
`homeassistant_api: true`; the Supervisor token stays server-side. Only authorized
IDs are cached, for at most 30 seconds. Expired authorization and lookup failures
fail closed. Connected status streams are rechecked against the same cache.

POSTs and WebSocket upgrades require a matching origin. Mutation requests also
require a per-user CSRF token. No LAN port, separate login, or public API token is
added. Auth responses and control records are not browser-persisted.

## Bounds and compatibility

Event-journal and diagnostic-journal reads run off the panel event loop, with two
concurrent database reads at most. Event-journal statistics share a five-second
cache. Diagnostic writes remain isolated behind ADR 0002's bounded writer queue;
the ingress API only reads already-sanitized records. Status snapshots are sent
at approximately one-second intervals; this reads the existing domain state and
does not add panel polling. Each browser receives an authoritative snapshot,
not a simulated panel model. Eight concurrent status sockets are permitted.

The existing recent-event Home Assistant sensor, event retention behavior,
protocol/control implementation, and Lovelace keypad bundle remain compatible.
The only control-result extension is a correlation identifier without raw input.
Event-journal completeness is limited to records collected and retained by the
app; there is no claim of complete panel lifetime history or an on-demand dump
action. Diagnostic history is similarly bounded by its configured 30-day /
25,000-record retention. Diagnostic overload is represented by dropped-event,
pending-write, and write-error counters rather than hidden or backpressured into
panel/Home Assistant transport.

## Validation and remaining qualification

Automated Python coverage includes startup/incomplete/offline states, global and
untyped alarms, keypad-only alarms, partition trouble, fault/bypass distinction,
canonical event colors, actual coordinator admission/results, duplicate keys,
actor isolation, unauthorized ingress, CSRF/origin failures, revoked WebSockets,
query validation, system-only scope, event-journal paging, diagnostic redaction,
diagnostic cursor paging, incident correlation, diagnostic ordering, and filter validation.

Browser tests load the shipped HTML/CSS/JavaScript and unchanged keypad bundle
with deterministic fixtures produced by the real snapshot builder. They check
all four destinations, responsive labels/widths, light/dark rendering, keyboard
component input, acknowledgement feedback, stale-state invalidation, event paging,
diagnostic category/severity filters, newest/oldest ordering, complete incident views, and diagnostic paging.
Captures show fixture state, not a connected installation.

These checks do not qualify the installed Supervisor proxy, its actual API
permissions, real user-role changes, or hardware timing. The PR remains draft
until an installed test verifies administrator/member access, nested ingress
URLs, WebSockets, panel disconnect/reconnect, and physical keypad response.
