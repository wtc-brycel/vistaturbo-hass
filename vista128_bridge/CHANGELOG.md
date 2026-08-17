# Changelog

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
