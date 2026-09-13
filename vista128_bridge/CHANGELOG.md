# Changelog

Detailed release-candidate notes are kept in [`../release/`](../release/). This file summarizes the user-visible and architectural changes for each published version.

## 0.2.6-rc.27

- Complete the real-hardware Lantronix transport fix by negotiating Telnet BINARY mode in both directions.
- Preserve RFC2217 `COM-PORT-OPTION` negotiation and 9600/8N1/no-flow serial configuration when supported.
- Add safe Telnet/RFC2217 negotiation diagnostics without logging VISTA payloads, keypad codes, alarm codes, or credentials.
- Confirm successful VISTA startup synchronization, keypad polling, and periodic reconciliation through the Lantronix path.
- Retain transparent raw-TCP compatibility and the installer-programming safety interlock.

## 0.2.6-rc.26

- Add Lantronix RFC2217 / TruPort negotiation on top of the Telnet compatibility layer.
- Request the known-good VISTA serial settings: 9600 baud, 8 data bits, no parity, 1 stop bit, and no flow control.
- Consume RFC2217 control and acknowledgement traffic before it reaches the VISTA frame parser.
- Preserve raw-TCP operation for serial servers that do not use Telnet control traffic.

## 0.2.6-rc.25

- Refine Lantronix Telnet option negotiation during hardware bring-up.
- Keep Telnet control traffic isolated from VISTA framing and preserve fragmented-IAC handling.
- This negotiation model was superseded by the bidirectional BINARY plus RFC2217 transport finalized in RC27.

## 0.2.6-rc.24

- Add a non-configurable installer-programming safety interlock.
- Block any four numeric keypad digits followed by `800` before the triggering frame reaches the panel.
- Cover individual keypresses, multi-key requests, semantic keypad fallback, and privileged raw `KS` transmission.
- Never log or persist the preceding four-digit code as part of the safety decision.
- Keep installer programming available from a physical keypad only.

## 0.2.6-rc.23

- Add automatic Telnet-mode serial-server detection while preserving raw TCP when no Telnet control traffic is present.
- Consume Telnet negotiation and subnegotiation before bytes reach the VISTA frame parser.
- Add stateful handling for fragmented IAC sequences and literal `0xFF` escaping.
- Begin real-hardware Lantronix compatibility work that was completed in RC27.

## 0.2.6-rc.22

- Treat `08XF` as generic Home/Facility Automation Communication Off rather than assuming installer programming.
- Quiesce automation traffic and mark panel state stale while communication is suspended.
- Use explicit `AD` / `BD` events as programming evidence when available.
- Require a full state resynchronization after `08XN` Communication On.

## 0.2.6-rc.21

- Stop reconnect loops when the panel deliberately disables the automation interface.
- Treat `08XF` as a terminal result for an in-flight control transaction rather than manufacturing an ACK timeout.
- Keep virtual keypad control unavailable while communication is suspended and resynchronize when it returns.

## 0.2.6-rc.20

- Accept legitimate markerless keypad-display replies when one serialized keypad transaction uniquely identifies the partition.
- Continue rejecting keypad replies that explicitly identify a different partition.
- Fix reconnect loops triggered by transient displays such as `CANCEL SENT TO CENTRAL / STATION`.

## 0.2.6-rc.19

- Queue rapid normal keypad presses in arrival order instead of rejecting presses while the previous key is awaiting the panel.
- Preserve exclusive keypad ownership for multi-step interactions.

## 0.2.6-rc.18

- Infer automation-interface availability from successful structured VISTA read transactions.
- Keep explicit Communication Off authoritative until communication is restored.
- Fix control remaining unavailable while normal AS/ZS/ZP/ZD/KD traffic is functioning.

## 0.2.6-rc.17

- Remove historical event-log import from normal startup so it cannot monopolize the serial session.
- Restrict keypad polling to configured partitions instead of probing all eight.
- Allow normal partition, zone, and keypad state to become available as soon as the live snapshot is valid.
- Base no-alarm completeness on partitions actually mapped by the panel.

## 0.2.6-rc.16

- Correct semantic command-model and audit integrity issues found during final review.
- Normalize automatic unbypass through the documented `#77` zone-list flow.
- Restrict generic system commands to documented one-shot namespaces and reject unused operands.
- Treat `acknowledged_unverified` as a terminal audit result.

## 0.2.6-rc.15

- Fix MQTT bootstrap queue exhaustion that could leave Home Assistant showing the bridge offline while panel communication was healthy.
- Increase the internal bounded Paho outbound queue while keeping the tuning surface private.
- Preserve RC14 keypad behavior and the streamlined App options surface.

## 0.2.6-rc.14

- Remove the synthetic keypad SEND workflow and restore immediate physical-keypad semantics for `0-9`, `*`, and `#`.
- Publish each press as an ordered one-key non-retained request with explicit completion.
- Keep control transaction IDs atomic while grouping rapid entry under a separate bounded audit interaction.
- Add browser regression coverage for rapid and slow entry, literal `*`/`#`, actor attribution, and redacted DOM events.
- Update the keypad card to `0.3.26`.

## 0.2.6-rc.13

- Correct alarm taxonomy so auxiliary, burglary families, and audible panic remain distinct.
- Preserve fail-safe alarm behavior across restore, disarm, reconnect, stale state, and incomplete snapshots.
- Accept ADR 0001 for the Home Assistant-native suite architecture.
- Keep the App as the sole VISTA protocol engine and define the future native integration and ingress management surfaces.

## 0.2.6-rc.12

- Add the canonical `VistaCommand` semantic command model, parser, compiler, and native-preferred execution planner.
- Add structured semantic control while preserving legacy partition and keypad topics.
- Preserve exact logical keypad sequences in bounded local administrator audit without exposing credentials in normal telemetry or logs.
- Serialize multi-step keypad interactions and require complete explicit prompt/menu flows.
- Verify keypad fallback arming across every requested partition.

## 0.2.6-rc.11

- Harden alarm state, synchronization, MQTT, persistence, and frontend behavior.
- Add fail-safe panel alarm aggregation and reconnect invalidation of connection-derived state.
- Add bounded normal/raw TX queues, strict privileged raw-TX validation, MQTT TLS verification, and retained-topic cleanup.
- Add explicit unavailable rendering and disabled controls to the keypad card.

## 0.2.6-rc.10

- Add first-class per-partition and panel-wide Fire, Burglary, Auxiliary, and Alarm Active binary sensors.
- Keep alarm OFF unavailable until the required authoritative state is complete after reconnect.
- Add active partitions and alarm classes to aggregate entity attributes.
- Continue asynchronous keypad-display refresh after control and live panel events.

## 0.2.6-rc.9

- Fix Home Assistant visual editors losing focus during repeated `hass` state refreshes.
- Avoid unnecessary editor Shadow DOM rebuilds after `config-changed` and echoed `setConfig()` updates.
- Apply the same lifecycle correction to the event-journal card editor.
- Update the keypad card to `0.3.22` without changing panel protocol behavior.

## 0.2.6-rc.8

- Infer Automation Interface Available after a successful structured VISTA transaction when the panel does not emit `08XN` during ordinary operation.
- Preserve `08XF` Communication Off as an explicit same-session control block.
- Add the Automation Availability Source diagnostic.
- Separate semantic Trouble from the raw keypad Trouble LED and improve validated trouble-family tracking.
- Keep Power unknown after reconnect until explicit AC evidence is observed.
- Remove keypad digits from frontend DOM event details and report actual control enablement.

## 0.2.6-rc.7

- Add the first opt-in VISTA panel write path while keeping control disabled by default.
- Add serialized keypad and native alarm control through the shared panel transaction coordinator.
- Add native Away, Home/Stay, Instant/Night, Maximum, Force Away, Force Home, and Disarm commands.
- Reject retained MQTT control messages and never replay queued control across reconnects.
- Redact control payloads and credentials from normal logs and telemetry.

## 0.2.6-rc.6

- Add the persistent SQLite event journal at `/data/vista128_events.sqlite3`.
- Journal live `nq` events and add optional documented historical-log import support.
- Publish only a bounded recent event window to Home Assistant.
- Add `custom:vista-event-log-card` and event-history filtering.
- Recognize `08XF` Communication Off and expose automation availability diagnostics.

## 0.2.6-rc.5

- Add the Home Assistant visual editor for keypad entity, model, layout, appearance, sound, haptics, and function-key labels.
- Preserve advanced YAML-only options and shorthand compatibility.
- Add Chromium regression coverage for editor behavior.

## 0.2.6-rc.4

- Add optional synthesized keypad audio and browser haptics.
- Add the First Alert-inspired keypad model.
- Add centralized `chime_zones` configuration and one-shot disarmed-zone chimes.
- Add burglary, auxiliary, and normalized sound-mode semantics.
- Add the interactive keypad simulator and expanded browser tests.

## 0.2.6-rc.3

- Add adaptive Lovelace layouts with `auto`, `physical`, and `compact` modes.
- Switch to a touchscreen-first compact layout at narrow card widths.
- Apply the renderer to 6160CR-2, 6160, and future model profiles.
- Add real Chromium layout and touch-target regression tests.

## 0.2.6-rc.2

- Harden the keypad cards for mobile and narrow dashboards.
- Add ResizeObserver-driven LCD redraws, pointer-cancel handling, and theme-aware case updates.
- Require both bridge and panel availability for panel entities.
- Invalidate event-derived annunciators after TCP gaps instead of publishing stale state.

## 0.2.6-rc.1

- Add production 6160CR-2 and 6160 Home Assistant keypad cards.
- Add Power, Fire Alarm, Silenced, Supervisory, and Trouble annunciator state.
- Add red, white, dark, and automatic light/dark enclosure handling.
- Keep keypad controls read-only in this release.

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
- Log explicit TCP timeout failures instead of hanging indefinitely in `connect()`.
- Include exception class names for non-timeout panel connection failures.

## 0.1.1

- Use asynchronous MQTT startup/reconnect so a temporary broker outage does not terminate the bridge.
- Reject raw diagnostic transmissions while the panel TCP connection is offline.
- Discard any queued raw transmission on panel disconnect so commands are never replayed after reconnect.
- Periodically republish panel connectivity state for recovery after MQTT broker restarts.
- Install Python dependencies from `requirements.txt` as the single dependency source.

## 0.1.0

- Initial TCP transport, raw frame capture, MQTT diagnostics, and guarded raw TX scaffold.
