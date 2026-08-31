# Correct VISTA command semantic integrity after #23

Reopens and closes #20 after the command-model feature PR was merged before its final review findings were addressed.

## What this fixes

- **Correct #77 automatic unbypass semantics.** `unbypass_zones` no longer fabricates an inline `#77/31 + ZZZ...` sequence. VISTA #77 actions 30/31 operate on a configured **Zone List # (01-15)**, so the semantic operation normalizes to `unbypass_zone_list` and compiles the complete action/specifier/confirmation/quit flow. Explicit-zone input is rejected rather than silently reinterpreted.
- **Keep prompt-driven `#nn` commands out of generic `system_command`.** Generic semantic execution is restricted to documented one-shot namespaces (`#41`, `#42`, `#65`, `#71`, `#72`, `#73`). Event-log display/print/clear (`#60`/`#61`/`#62`), clock editing, relay/access, #77, and scheduling/menu families must use a typed or explicit interactive transaction so keypad ownership is not released inside a panel menu.
- **Finish `acknowledged_unverified` audit rows.** The status is now terminal in both the Python status set and SQLite upsert path, so successful-but-not-fully-verifiable subtype commands get `completed_at` instead of remaining open indefinitely.
- **Reject unused semantic operands.** Commands such as `chime`, `quick_bypass`, `walk_test`, access relay, and capability display have explicit empty operand schemas; bogus fields cannot survive into audit while execution ignores them.
- **Conservative #77 parsing.** A recognized #77 action only receives high-confidence typed operands when its action specifier is valid for that action. Invalid partition/zone-list specifiers remain lower-confidence rather than being normalized as valid commands.

## Manual alignment

The Honeywell/Resideo VISTA-128BPT/250BPT user and installation guides document:

- #77 Auto Bypass / Auto Unbypass with a **Zone List #** action specifier, followed by confirmation and quit-menu prompts;
- Event Log Display/Print as interactive modes after `Code + #60/#61`;
- Event Log Clear as a confirmation flow after `Code + #62`;
- #41/#42, #65, #71/#72, and #73 as complete one-shot command sequences.

Reference: https://studylib.net/doc/27779423/vista-128-250bpt-owners-manual

## Regression coverage

Added/updated tests cover:

- explicit-zone unbypass rejection;
- zone-list 01-15 normalization and `#77/31` compilation;
- invalid #77 action specifiers not receiving high confidence;
- one-shot generic `system_command` compilation;
- rejection of event-log/menu/access/scheduling namespaces from the generic direct path;
- bogus operands rejected for simple semantic commands;
- `acknowledged_unverified` populating audit `completed_at`.

No #19/release-security behavior is changed. The existing transaction ownership, queue bounds, PIN handling, audit sensitivity policy, and frontend SEND boundary remain intact.
