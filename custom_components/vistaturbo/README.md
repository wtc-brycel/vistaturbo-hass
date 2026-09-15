# Vista Turbo Home Assistant integration

This directory is the HA0 native-integration foundation described by the repository architecture decision.

The integration is deliberately thin:

- Supervisor App discovery supplies the Vista Turbo App's internal hostname, port, and installation-local machine token.
- Home Assistant takes one authoritative semantic snapshot, then consumes server-sent push snapshots from the App.
- VISTA framing, keypad grammar, synchronization, command planning, verification, and recovery remain exclusively in the App.
- The first native surface is read-only: assigned-zone condition sensors, bridge health, and keypad display state. Partition state is carried in the private snapshot but is not exposed as an alarm-control-panel entity until semantic native control is implemented.
- MQTT remains unchanged and required for compatibility during this migration phase.

The App's native API is internal-only and is not mapped to a host port. Its bearer token is generated in `/data`, is not an App option, and is transferred to Home Assistant only through Supervisor discovery.

Native control, Home Assistant user attribution, richer event entities, diagnostics/Repairs, and removal of MQTT as a required service are follow-up HA-platform phases after state parity is established.
