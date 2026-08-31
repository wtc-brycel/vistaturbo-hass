# VISTA command semantic-integrity notes

The semantic control layer distinguishes complete one-shot keypad commands from prompt-driven menu flows.

- `unbypass_zones` no longer compiles an invented inline-zone `#77/31` sequence. VISTA #77 automatic unbypass is zone-list based; callers must supply `zone_list` 01-15 and the command is normalized as `unbypass_zone_list`.
- Generic `system_command` execution is limited to complete one-shot namespaces: `#41`, `#42`, `#65`, `#71`, `#72`, and `#73`.
- Event-log display/print/clear (`#60`, `#61`, `#62`), clock editing (`#63`), output/access menus, `#77`, and scheduling/timer families must use typed or explicit interactive transactions so keypad ownership remains held through every prompt and exit step.
- `acknowledged_unverified` is a terminal audit outcome. It records completion without claiming that panel telemetry proved a requested subtype.
- Executable semantic commands use action-specific operand schemas; unconsumed operands are rejected rather than retained in audit metadata.

These constraints preserve the invariant that the normalized audit record describes the operation actually transmitted to the panel.
