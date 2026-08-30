# Changelog

## 0.2.6-rc.12

- Add a canonical `VistaCommand` model, deterministic keypad parser, bounded compiler, and native-preferred execution planner for semantic Home Assistant/MQTT control.
- Add `control/execute` structured MQTT commands while preserving legacy partition and logical keypad topics.
- Keep exact logical keypad sequences and four-digit PINs in the bounded local administrator audit, with normalized command type, operands, mechanism, confidence, and verification fields; never expose them in normal telemetry or logs.
- Preserve keypad ownership across every explicit `complete:false` segment and serialize fallback segments through the existing panel transaction coordinator.
- Reject raw sequence overrides on ordinary semantic actions, require complete `#70`/`#77` menu flows, and use native execution only when it preserves all command operands.
- Model `#77` action-specific operands through confirmation and quit-menu, compile semantic `system_command` namespaces, reject unused action operands, and support `GOTO 0`.
- Verify keypad fallback arming across every requested partition; subtype-bearing results are acknowledged as unverified when panel telemetry cannot prove the subtype.
- Bump the bridge to RC12 and the card to `0.3.25`.

## 0.2.6-rc.11

- Coordinate the #16, #17, and #18 security hardening pass across alarm state, synchronization, MQTT, persistence, and the keypad card; #19 is intentionally separate.
- Add fail-safe panel alarm aggregation for fire, burglary, auxiliary, silent, duress, supervisory, and untyped alarm evidence. Alarm OFF remains unavailable until the complete session snapshot is fresh.
- Invalidate connection-derived security state on reconnect while preserving configuration and event history. Do not republish stale READY, DISARMED, keypad, or alarm state as current.
- Correlate protocol acknowledgements and keypad responses with their pending transactions and serialize logical keypad sequences.
- Add bounded normal/raw TX queues, strict privileged raw-TX validation on `admin/raw_tx`, MQTT publish diagnostics, and opt-in raw frame diagnostics.
- Add MQTT TLS verification with no plaintext fallback, bounded event-history retention, retained-topic/discovery cleanup, and trusted-network transport documentation.
- Update the card to version `0.3.24` with explicit unavailable rendering, disabled controls, narrow CSS color validation, bounded searchable entity selection, and explicit logical keypad completion for serialized QoS 1 commands.

## 0.2.6-rc.8

- Infer Automation Interface Available after a successful structured VISTA transaction when the panel does not emit `08XN` during ordinary operation.
- Preserve `08XF` Communication Off as an explicit same-session control block that ordinary `08OK` replies cannot override.
- Add the **Automation Availability Source** diagnostic with `unknown`, `inferred`, `explicit`, `communication_off`, and `offline` states.
- Stop treating a quiet KD page or a false raw TROUBLE lamp bit as evidence that AC power is present. POWER remains unknown after reconnect until explicit AC evidence is observed.
- Split semantic keypad `trouble` from `trouble_led_raw`; semantic TROUBLE remains active across the VISTA's rotating display pages while known trouble conditions remain active.
- Track validated trouble families, system battery, RF low battery, and sensor tamper with reconnect-invalidated trouble state.
- Treat both `D` and `N` arming snapshots as authoritative disarmed states when clearing stale alarm tokens.
- Publish individual virtual-keypad presses at MQTT QoS 0 with retain disabled to avoid at-least-once duplicate digits.
- Remove entered keypad digits from the frontend `vista-keypad-key` DOM event detail.
- Report the partition `control_enabled` attribute from actual bridge configuration instead of a hard-coded false value.
- Close every SQLite event-journal connection deterministically and add regression coverage for connection closure.
- Add card `0.3.21`; keypad function keys A-D remain intentionally unmapped pending explicit action and hold semantics.

## 0.2.6-rc.7

- Add the first opt-in VISTA panel write path while keeping all control disabled by default.
- Add a serialized `VistaControlCoordinator` sharing the existing protocol transaction lock with synchronization and keypad polling.
- Add typed VISTA `KS` keypad commands for `0-9`, `*`, and `#`, with exact frame/checksum regression tests.
- Add typed native VISTA arm/disarm commands for Away, Home/Stay, Instant/Night, Maximum, Force Away, Force Home, and Disarm.
- Enable standard Home Assistant Away, Home, Night, and Disarm through MQTT remote-code validation when native alarm control is explicitly enabled.
- Require `08XN` Automation Interface Available before any control request can be queued and stop/discard requests on `08XF`.
- Treat `08OK` only as protocol flow-control acknowledgement and verify native alarm results with a fresh arming-status query.
- Never replay queued commands across a panel TCP reconnect; queued requests are tied to one connection generation and expire quickly.
- Reject retained MQTT control messages so broker reconnects cannot replay old keypad or alarm commands.
- Redact all control TX payloads from bridge logs and never echo alarm PINs or keypad digits in control result telemetry.
- Keep keypad code entry responsive by waiting for `08OK` per stroke and requesting a coalesced keypad refresh instead of blocking every digit on a KD transaction.
- Keep the A-D visual function keys and panic encodings unavailable through the normal RC7 keypad control path pending explicit action and hold-to-activate semantics.
- Add card `0.3.20` with an opt-in visual-editor keypad-input toggle and direct non-retained Home Assistant MQTT publishing.
- Preserve the RC6 SQLite event journal, historical event-log import, event-journal card, audio, chime, and First Alert keypad features.

## 0.2.6-rc.6

- Add a persistent SQLite VISTA event journal at `/data/vista128_events.sqlite3`.
- Journal live `nq` system events with event code, panel time, partition, zone, user, descriptor, and source metadata.
- Add optional startup import of the documented VISTA historical event log using `08LD00A8`, `ld` entries, and the `08lc0069` completion packet.
- Leave historical startup import disabled by default pending physical VISTA-128BPT validation; live SQLite journaling is enabled by default.
- Keep imported historical events isolated from live state changes, chimes, sounds, keypad refreshes, and printer receipts.
- Deduplicate repeated historical imports while preserving multiple identical events that genuinely occur within the same panel minute.
- Backfill programmed zone descriptors into existing journal rows when descriptors become available.
- Add the Home Assistant **Event Journal** sensor with a configurable 1-100 row recent window instead of copying the full database into HA state.
- Keep the Event Journal available while the panel TCP link is down as long as the bridge remains online.
- Add card `0.3.19` with `custom:vista-event-log-card`, responsive recent-event rows, partition filtering, live/history/both source labels, and a visual editor.
- Recognize `08XF` Communication Off and expose an **Automation Interface Available** diagnostic.
- Recognize `10DC` Display Changed passively without assuming refresh behavior until observed on the test panel.
- Add C7 Fail To Arm and C8 Fail To Disarm event descriptions.
- Keep all alarm and keypad control read-only.

## 0.2.6-rc.5

- Add card `0.3.18` with a Home Assistant visual editor exposed through the custom-card `getConfigElement()` contract.
- Configure keypad entity, model, layout, title, card background, case color, and day/night case overrides without hand-editing YAML.
- Configure sound enablement, key chirp, panel-state sounds, chime/trouble/supervisory toggles, key/alarm volume, and optional burglary/AUX entity overrides in the editor.
- Configure best-effort haptic enablement and keypress duration in the editor.
- Configure A/B/C/D function-key labels while preserving model defaults when fields are blank.
- Preserve advanced indicator/flashing maps and per-function-key colors as YAML-only options.
- Keep the visual editor read-only with no panel-control toggle.
- Preserve compatibility with `sound: true` and `haptic: true` shorthand configurations.
- Add Chromium regression coverage for editor discovery, rendered values, nested `config-changed` events, and shorthand compatibility.
- Keep the bridge protocol/state behavior unchanged from RC4.

## 0.2.6-rc.4

- Add card `0.3.17` with optional low-latency synthesized Web Audio keypad feedback and best-effort browser haptics.
- Add immediate keypress chirps plus chime, trouble, supervisory, fire, burglary, and auxiliary sound profiles.
- Add page-level audio unlocking and a small `AUDIO` flag while browser playback remains blocked.
- Add the First Alert-inspired keypad model with horizontal wide and portrait compact compositions.
- Add centralized App-level `chime_zones` configuration with zone/range syntax.
- Generate chimes only for new configured-zone fault transitions while the resolved partition is known to be disarmed; suppress duplicate and armed-state chimes.
- Add native `burglary_alarm`, `auxiliary_alarm`, and normalized `sound_mode` keypad attributes from validated event families.
- Keep silent alarm and duress events out of the audible burglary classifier.
- Invalidate native audible state across panel TCP gaps and stop continuous frontend audio while the keypad entity is unavailable.
- Make chime counters restart-safe so a bridge sequence reset does not replay a stale chime.
- Add checked-in browser audio tests and expand Chromium coverage to all three keypad styles.
- Add an interactive keypad simulator and attach it to release-candidate releases.
- Ignore generated Node and Playwright test artifacts while retaining a deterministic frontend package lock.
- Keep all alarm and keypad control read-only.

## 0.2.6-rc.3

- Add card `0.3.15` with a model-agnostic adaptive Lovelace layout system.
- Make `layout: auto` the default, preserving the physical keypad facsimile above 520 px card-container width and switching to a touchscreen-first compact layout at 520 px and below.
- Add `layout: physical` and `layout: compact` overrides.
- Give compact layouts a large LCD, condensed annunciator strip, and 4 x 4 keypad grid with approximately 50 px minimum key height.
- Hide secondary numeric legends below 320 px before allowing primary key labels or touch targets to become too small.
- Apply the same adaptive renderer to both 6160CR-2 and 6160 models.
- Add `MODEL_PROFILES` so future keypad models can declare compact annunciators and function-key labels without implementing a separate mobile UI.
- Reduce the Home Assistant grid minimum from six columns to four columns because compact mode remains usable at that width.
- Add real Chromium browser regression tests for wide/compact switching, 390 px and 320 px touch-target dimensions, both model profiles, forced layout modes, AUTO case colors, and Lovelace grid sizing.
- Keep all alarm and keypad control read-only.

## 0.2.6-rc.2

- Harden the 6160/6160CR-2 card for Home Assistant mobile and narrow dashboard layouts.
- Add ResizeObserver-driven LCD redraws so orientation and Lovelace column changes do not stretch the canvas bitmap.
- Handle pointer cancellation so touch scrolling cannot leave a keypad key visually pressed.
- Avoid rebuilding the keypad Shadow DOM for unrelated Home Assistant state changes.
- Observe browser light/dark theme changes when Home Assistant does not expose an explicit dark-mode value.
- Add Home Assistant grid sizing hints with a six-column minimum.
- Require both the bridge MQTT availability topic and the panel TCP connection topic for panel entity availability.
- Invalidate event-derived Power, Fire Alarm, Silenced, and Supervisory state after a TCP communication gap so stale CR-2 state cannot survive a missed restore event.
- Stop treating generic panel power-up events as authoritative evidence that AC power is present.
- Allow a restored fire latch to clear on a later non-fire keypad display even if an unrelated burglary zone keeps READY off.
- Add focused regression coverage for availability, reconnect state invalidation, AC semantics, and fire-latch clearing.
- Keep all alarm and keypad control read-only.

## 0.2.6-rc.1

- Add production 6160CR-2 and 6160 Home Assistant keypad cards.
- Add CR-2 Power, Fire Alarm, Silenced, Supervisory, and Trouble annunciator state to the keypad entity.
- Keep Fire Alarm latched across detector restore until keypad reset/normalization clears the condition.
- Reconstruct Power from AC loss/restore events and Supervisory from supervisory start/restore events.
- Republish initialized keypad entities immediately after relevant real-time panel events.
- Add red, white, and dark enclosure colors to both keypad models.
- Make `case_color: auto` the default for both keypad models and follow Home Assistant light/dark mode.
- Add optional `day_case_color` and `night_case_color` overrides for AUTO mode.
- Use model defaults of red/dark for 6160CR-2 and white/dark for 6160.
- Remove forced keypad minimum heights so Lovelace cards preserve physical aspect ratio in narrow columns.
- Add narrow-container control scaling for key padding, legends, and function-key positioning.
- Keep all keypad controls read-only.

## 0.2.5

- Add native VISTA Turbo keypad display polling over the existing RS-232 automation connection.
- Add the physically validated Partition 1 `09KD10077` request and `29kd` response parser.
- Decode both 16-character keypad lines, Ready/Trouble/Armed LED flags, and keypad backlight state.
- Publish one Home Assistant keypad sensor per configured partition with exact display text and raw protocol attributes.
- Poll configured keypad partitions every 7 seconds by default and request a debounced refresh after valid partition events.
- Serialize keypad queries with startup, periodic, and resynchronization traffic so only one panel transaction is active at a time.
- Require both valid keypad display data and a valid Ready-for-Next response before a keypad transaction succeeds.
- Keep keypad polling read-only. Home Assistant arm/disarm control remains disabled.

## 0.2.4

- Replace the combined per-zone binary sensor with four explicit binary sensors: Fault, Alarm, Check, and Bypass.
- Use the authoritative `49ZS` bitmask for all four per-zone condition entities.
- Rename aggregate sensors to Fault Zones, Alarm Zones, Check Zones, and Bypass Zones.
- Remove the old combined zone discovery entries and old aggregate discovery names during MQTT reconnect.
- Keep RF low-battery and sensor-tamper data separate because those conditions are not present in the `49ZS` snapshot.

## 0.2.3

- Add aggregate Home Assistant sensors for faulted zones, zones in CHECK, zones in alarm, and bypassed zones.
- Use the authoritative `49ZS` zone-status bitmask for all four aggregate sensors.
- Publish the number of matching assigned zones as sensor state and include zone number, partition, and descriptor in attributes.
- Refresh aggregate sensors after zone snapshots, partition mapping, descriptor synchronization, and relevant unsolicited zone events.
- Do not infer aggregate low-battery or tamper state from event-only data.

## 0.2.2

- Rename the public repository to `vistaturbo-hass` and the App to Vista Turbo RS232.
- Scope compatibility language to the VISTA Turbo RS-232 automation interface.
- State VISTA-128BPT as the only currently tested panel.
- Retain the `vista128_bridge` slug and existing MQTT identifiers to avoid breaking Home Assistant entities.
- Preserve the ChatGPT Codex development disclosure in README and documentation.

## 0.2.1

- Brand the public project as VistaHASS while retaining existing internal entity identifiers.
- Add Home Assistant repository metadata for public installation.
- Add explicit ChatGPT Codex and AI-assisted development disclosure to README and documentation.

## 0.2.0

- Refactor connection, synchronization, protocol handling, MQTT discovery, and printer persistence into focused modules.
- Group runtime configuration by panel, MQTT, synchronization, and printer concerns.
- Centralize the Python runtime version and verify package version consistency in tests.
- Accept Ready-for-Next only after packet validation succeeds.
- Remove unused protocol constants and generated-style explanatory comments.
- Remove em dashes from shipped source and documentation.
- Rewrite README and operator documentation for concise technical language.
- Preserve read-only alarm behavior and existing MQTT entity/topic contracts.

## 0.1.9

- Log the exact application version at container startup so the running build is immediately identifiable in Home Assistant logs.
- Add regression coverage for the real VISTA `05` Bypass event captured from zone 034/user 002/partition 1.
- Add regression coverage for the real lowercase `0Dzd000""007A` descriptor-stream terminator emitted by this VISTA-128BPT.
- Remove generated Python bytecode/cache files from the distributable package.
- Correct the 0.1.8 changelog to match the implemented 45-second descriptor fallback timeout.
- No new write/control capability; alarm control remains disabled.

## 0.1.8

- Treat the lowercase `zd000""` record as the end of descriptor synchronization.
- Stop waiting for a trailing `08OK` after a completed descriptor stream.
- Raise the descriptor fallback timeout to 45 seconds.

## 0.1.7

- Give the descriptor bootstrap query its own long-running timeout.
- Make descriptor timeout non-fatal to the TCP session.
- Recognize lowercase `zd` descriptor records from the VISTA-128BPT.
- Keep the 5-second timeout for normal state queries.

## 0.1.6

- Normalize Home Assistant App, runtime MQTT, and Python package version metadata to `0.1.6`.
- Stop reusing the installed manifest version during local development; every packaged build now has a unique version.
- No protocol, synchronization, printing, or state-machine behavior changes from the preceding `0.1.5-dev` code.

## 0.1.5-dev

- Add five-minute read-only partition/zone reconciliation to correct state drift while keeping unsolicited VISTA events authoritative.
- Serialize startup, periodic, and event-triggered re-sync traffic; abort a sync on missing Ready-for-Next rather than risking transaction overlap.
- Force a clean StarTech TCP reconnect after repeated failed periodic synchronizations.
- Request a full metadata/state re-sync after panel power-up/Communication-On conditions and program-mode exit.
- Track last successful sync, consecutive sync failures, and VISTA panel clock offset in MQTT diagnostics.
- Add optional continuous TransPort event receipts via HTTP `POST /print` on port 9101.
- Persist pending event receipts in `/data` using SQLite so pending jobs survive TransPort outages and App restarts.
- Retry only failures that occurred before a TransPort TCP connection was established; submissions with ambiguous physical outcome are marked uncertain and never blindly replayed.
- Format receipts as plain configurable-width text with event code, partition/zone/user, VISTA descriptor, receive timestamp, and panel timestamp.
- Keep normal arm/disarm control disabled.
- Preserve the local App manifest version at `0.1.1` so Supervisor Rebuild works during local development.

## 0.1.4-dev

- Add packet-length and checksum validation; invalid packets are logged/published but cannot mutate Home Assistant state.
- Decode VISTA arming status into read-only MQTT `alarm_control_panel` entities for partitions 1-8.
- Decode `49ZS` zone status blocks and `49ZP` zone-to-partition mapping into assigned-zone `binary_sensor` entities.
- Request and decode VISTA zone descriptors so entities can use the panel's programmed alpha labels.
- Decode enhanced `1Bnq` real-time events, including the captured `B7` Arm STAY event, into a Last Event sensor and non-retained MQTT event stream.
- Apply common fault/restore, trouble/restore, bypass/restore, alarm/restore, RF low-battery, and tamper transitions to HA state.
- Keep normal arm/disarm commands disabled; the build remains read-only.
- Preserve the local App manifest version at `0.1.1` so Supervisor Rebuild works during local development.

## 0.1.3

- Add read-only startup synchronization requests for arming status, zone status, and zone-to-partition mapping.
- Wait for the VISTA Ready-for-Next response between startup requests, with a bounded timeout.
- Add coarse protocol message classification to raw-frame logs and MQTT payloads.
- Add transmitted frame/byte diagnostic counters.
- Reset the stream framer on each TCP connection so partial data cannot leak across reconnects.
- Clean up connection tasks during shutdown/disconnect to avoid unhandled read-task exceptions during App restart.
- Correct MQTT Discovery software version metadata.

## 0.1.2

- Add a configurable TCP connection timeout (default 5 seconds).
- Log explicit TCP timeout failures instead of hanging indefinitely in connect().
- Include exception class names for non-timeout panel connection failures.

## 0.1.1

- Use asynchronous MQTT startup/reconnect so a temporary broker outage does not terminate the bridge.
- Reject raw diagnostic transmissions while the panel TCP connection is offline.
- Discard any queued raw transmission on panel disconnect so commands are never replayed after reconnect.
- Periodically republish panel connectivity state for recovery after MQTT broker restarts.
- Install Python dependencies from `requirements.txt` as the single dependency source.

## 0.1.0

- Initial TCP transport, raw frame capture, MQTT diagnostics, and guarded raw TX scaffold.
