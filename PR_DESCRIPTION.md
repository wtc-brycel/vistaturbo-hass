# Coordinated security hardening for #16, #17, and #18

## Scope

This behavioral and security release hardens the bridge state model, panel transaction path, MQTT boundary, local persistence, printer assumptions, and frontend. Issue #19 is deliberately out of scope. No CI, release automation, or supply-chain workflow changes are included.

## Completed acceptance criteria

### Issue #16: alarm state and panel transactions

- Panel-wide alarm state now recognizes fire, burglary, auxiliary, silent, duress, supervisory, and all existing alarm-start event tokens, independently of the configured keypad partition list.
- Positive alarm evidence asserts ON immediately. OFF is emitted only after an authoritative arming, zone-status, zone-partition, and keypad alarm snapshot. Partial or stale knowledge is unavailable.
- TCP reconnect invalidates connection-derived arming, keypad, zone alarm, and alarm annunciator state while retaining configuration, descriptors, last-event data, and the durable event journal.
- Synchronization does not treat a partial multi-block snapshot as complete. Panel availability is retained as OFF until the required snapshot is complete.
- Keypad display replies are accepted only for the pending keypad transaction and the partition marker in that reply. Delayed or ambiguous replies cannot overwrite another partition.
- 08OK is scoped to a pending transaction and cannot complete unowned or wrong-response synchronization traffic. Unrelated acknowledgements no longer infer automation availability.
- Keypad sequences are bounded logical commands and are serialized with panel synchronization and other controls. The frontend keeps one interaction ID until the user explicitly presses SEND; input beyond the five-key KS frame is sent as `complete:false` segments followed by one final `complete:true` segment. Inactivity never completes or splits a command. The bridge keeps ownership until the final segment, cancellation, or session reset/reconnect, so a pause cannot permit interleaving. A competing interaction is rejected rather than interleaved. Reconnects discard pending control work.
- Control actor metadata includes interaction ID, HA user ID and name, partition, source, normalized action, exact logical command sequence, structured operands when known, timestamps, and outcome in the local audit table. PINs are intentionally present in that administrator-only local audit, but never in logs or MQTT control-result telemetry.

### Issue #17: MQTT, queues, persistence, telemetry, and transport assumptions

- MQTT TLS supports broker certificate verification, an optional CA, and optional client certificate/key. TLS setup or connection failure never falls back to plaintext.
- Trusted-LAN plaintext remains available for compatibility, with documentation requiring broker ACLs in either mode.
- Raw transmit is an explicitly opt-in administrative capability on `vista128/admin/raw_tx`, separate from normal control topics. The former confirmation phrase is not accepted as authentication. Input is strict ASCII or hex, bounded to 512 bytes, and sent through a bounded lower-priority queue.
- Normal transmit and control queues are finite. Overflow is deterministic, logged, and reported to the caller; raw work cannot overtake normal control or synchronization traffic.
- Important MQTT publishes check immediate Paho results, count failures, and expose a diagnostic counter. Repeated retained state is coalesced. Paho's own disconnected QoS queue and in-flight window are finite (`mqtt_outbound_queue_max: 256`, `mqtt_inflight_messages_max: 20`); the bridge adds no unbounded retry queue.
- Discovery and retained state cleanup publishes tombstones for obsolete alarm, keypad, partition, zone, summary, diagnostic, and legacy layouts.
- Raw frame MQTT publication and raw payload logging are both off by default. Opt-in raw frames are non-retained and valid-frame-only; default diagnostics retain metadata such as message type, validity, checksum, length, and timestamp.
- Event history and terminal printer spool history are bounded by configuration. Pruning is batched and does not delete pending printer work.
- Panel serial TCP is documented as unauthenticated plaintext; the VISTA checksum is documented as error detection, not authentication. Optional printer HTTP is documented as trusted-network-only unless the endpoint genuinely provides authenticated TLS, and an HTTP response is not described as proof of physical printing.
- The local `keypad_interactions` SQLite table keeps one row per logical interaction ID, including the exact completed sequence, including a four-digit PIN when present, actor metadata, partition, source, action, structured operands, timestamps, and status. A per-segment request identity makes queued-to-accepted lifecycle updates idempotent, so segments are concatenated once. It is bounded, local-only, and creates no HA entity or Recorder stream.

### Issue #18: frontend and release compatibility

- The card renders an explicit offline state and disables controls when the source HA entity is missing, unknown, or unavailable, regardless of retained attributes.
- CSS color validation accepts a narrow grammar for common named colors, hex, rgb/rgba, and hsl/hsla values and rejects `url()`, `calc()`, `var()`, and other expressions.
- Visual editor entity selection is domain-filtered, searchable, and bounded before friendly-name work, avoiding eager rendering of the entire HA registry.
- Frontend keypad input uses one logical non-retained QoS 1 JSON command with interaction and actor metadata. The card exposes an explicit SEND boundary, keeps the interaction ID across five-key KS segments, and emits `complete:false` for intermediates and `complete:true` only for the final segment. The bridge still accepts the former one-byte key payload and one-key JSON payload for compatibility.
- The card does not log, locally persist, or expose the entered sequence through its DOM event. The bridge stores the sequence only in the bounded local administrator audit described above.
- Bridge/add-on version is `0.2.6-rc.11`; the card version is `0.3.24`, including the cache-busting migration note.

## State and transaction model

The bridge now separates durable configuration and event history from connection-derived security state. Alarm state is evidence-based: positive event or keypad evidence is immediately visible, while a safe OFF value requires completeness. Synchronization uses pending transaction ownership, expected response types, and a shared serialization lock. Keypad responses must identify the pending partition. The VISTA protocol does not carry an on-wire transaction ID for 08OK, so the bridge uses the strongest safe association available from pending ownership, response ordering, session tainting, and reconnect boundaries. Keypad control additionally reserves the single panel keypad by logical interaction ID; the frontend uses an explicit SEND boundary and keeps that ID across all segmented frames until the final marker, and the bridge has no elapsed-time ownership expiry.

The keypad audit receives a complete logical command from the frontend or native control path rather than individual keypress events or an MQTT envelope. Multiple short segments carrying one interaction ID are concatenated into one bounded row, while a per-segment request identity prevents a queued-to-accepted update from being appended twice. Known native action metadata is stored separately from the exact four-digit code sequence. A full semantic VISTA command parser, including future zone operand interpretation, is intentionally left for issue #20; known zone operands are normalized to three zero-padded digits when supplied to the audit layer.

## Configuration and migration notes

- New defaults are `mqtt_tls_enabled: false`, `raw_mqtt_enabled: false`, `raw_logging: false`, `keypad_audit_enabled: true`, 90-day event/audit retention, 10,000 maximum event/audit rows, `tx_queue_max: 128`, `raw_tx_queue_max: 16`, `mqtt_outbound_queue_max: 256`, and `mqtt_inflight_messages_max: 20`.
- Existing plaintext MQTT deployments continue to work, but should be isolated and protected with broker ACLs. Enabling TLS requires the broker certificate chain to be trusted; it does not enable a plaintext fallback.
- If raw transmit is explicitly enabled, ACLs and tooling must move from the old debug topic to `vista128/admin/raw_tx`. The old confirmation phrase was never authentication and is no longer accepted.
- Existing one-byte keypad payloads remain accepted. New integrations should send the logical JSON form, for example `{"keys":"1234","complete":true}`, with QoS 1 and retain false. A segmented logical command must keep one interaction ID, use `complete:false` until its final segment, and send a unique request per segment.
- Existing event databases automatically receive the audit columns/table migration, including the per-segment request identity used to make queued-to-accepted updates idempotent. The audit stores sensitive panel security information; protect the App data directory and configure retention for the deployment.
- On MQTT reconnect, obsolete retained discovery and dynamic state topics are tombstoned before current discovery is republished. Replace the frontend resource with `vista-keypad-card.js?v=0.3.24`. Keypad users must press SEND to finish a command; inactivity no longer submits or splits it.

## Deliberately incomplete criteria and rationale

- Exact cryptographic attribution of one 08OK to one prior panel command is not implementable with the VISTA protocol exposed here because 08OK has no transaction identifier. The bridge now rejects unowned and wrong-response acknowledgements, prevents a timed-out transaction from being reused in the same session, and taints the session for reconnect, but a malicious or unusually delayed duplicate 08OK that arrives during a later valid control transaction cannot be distinguished on the wire. This limitation is not presented as solved.
- The panel serial-server transport remains unauthenticated plaintext by design. The bridge cannot add TLS to a Vista serial server that does not speak TLS. Isolation and firewall guidance are provided instead.
- Actor metadata is attribution, not authentication. HA identity and broker ACLs remain the trust boundary; this pass does not invent a second application authentication scheme.
- Full semantic parsing of arbitrary keypad commands and zone operands is deferred to issue #20. The exact completed logical sequence is persisted now so that parser can be applied later.
- Issue #19 CI, release, and supply-chain hardening is not included.

## Tests run

- `cd vista128_bridge && python -m unittest discover -s tests -v` -> 156 tests passed.
- `cd vista128_bridge && python -m py_compile app/vista_bridge/*.py tests/*.py` -> passed.
- `cd vista128_bridge && node --check ../frontend/vista-keypad-card.js` -> passed.
- `cd vista128_bridge && git diff --check` -> passed.
- `cd frontend && npm install --no-audit --no-fund` -> passed; lockfile unchanged.
- `cd frontend && npx playwright install --with-deps chromium` -> environment failure while apt attempted restricted privilege transitions; the subsequent browser download was completed with the repository's Playwright fallback installers.
- `cd frontend && npm run test:render` -> 49 tests passed.

## Remaining false-negative security behavior

Within the covered bridge state paths, no known path publishes a confident READY, DISARMED, or alarm OFF value from stale, incomplete, or disconnected panel knowledge; those states are unavailable until freshness and completeness are restored. Known positive alarm evidence still surfaces immediately.

The remaining false-negative risk is outside that guarantee: the unauthenticated panel TCP transport can be unavailable, malicious, or provide an unrecognized event, and the protocol has no 08OK transaction ID. Such conditions can cause missed or delayed evidence and are why the panel network isolation guidance and conservative unavailable state remain required.
