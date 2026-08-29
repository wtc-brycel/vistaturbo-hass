# VISTA command model and transactional semantic control

Closes #20. This PR is based on merged `main` after #22 and preserves the security properties from #16, #17, and #18. It does not modify #19 or begin #20 follow-up work beyond the command-model scope described here.

## Summary

This adds one canonical `VistaCommand` representation shared by keypad parsing, structured MQTT requests, keypad compilation, execution planning, verification, and the existing bounded local audit journal.

The control path is now:

```text
logical keypad or semantic MQTT request
  -> VistaCommand
  -> deterministic parser/compiler and ExecutionPlan
  -> existing serialized control coordinator
  -> native VISTA command or owned <=5-stroke keypad fallback
  -> panel acknowledgement and, for arm/disarm, fresh arming verification
  -> one bounded audit row per interaction ID
```

## Completed acceptance criteria

- Added fixed VISTA invariants: PINs are exactly four digits and semantic keypad zone operands are exactly three zero-padded digits. Zone lists are bounded and duplicate-free.
- Added deterministic parser states for normal commands, bypass zones/groups, hash namespace, output control, instant activation, user management, global partition selection, programming, macro/function keys, and explicit unclassified/ambiguous cases.
- Recognized normal disarm, Away, Stay subtypes, Instant subtypes, Maximum, walk test, chime, GOTO, user-capability, access relay, quick arm, quick exit, programming entry/exit, documented `#nn` families, `#70`, and representative `#77` action codes.
- Added model/capability extension registration and conservative handling for function keys, panic ambiguity, bare-code entry, programming data, and prompt-dependent commands. The parser does not fabricate certainty when panel context is insufficient.
- Added bidirectional compilation and planning. Core arm/disarm semantics prefer the existing native automation interface. Other supported deterministic operations use the existing keypad transaction path. Programming and interactive commands require their exact logical sequence.
- Added `vista128/control/execute` as a compact structured MQTT API. It validates action-specific operands, preserves actor/source/interaction attribution, rejects malformed input, and does not create a large HA entity surface.
- Kept legacy `partition/<partition>/command`, JSON keypad, and one-byte keypad paths compatible.
- Preserved one keypad owner across all explicit `complete:false` segments and blocked unrelated panel writes while an interaction is open. Fallback compilation sends all segments through the existing synchronizer lock and per-frame transaction acknowledgement.
- Enriched the existing `keypad_interactions` SQLite table in place with command type, exact PIN when part of the command, execution mechanism, parser confidence, and verification. Existing databases migrate automatically; lifecycle updates remain idempotent per request/segment and one interaction remains one row.
- Preserved the deliberate issue #21 audit policy: the exact completed logical sequence, including PINs, is retained only in the bounded administrator-local audit. It is not emitted in logs, HA entities, retained MQTT state, control-result telemetry, browser events, or MQTT envelopes.
- Preserved bounded event/audit retention and added coverage for semantic fields and full-sequence replacement after segmented request lifecycle updates.
- Bumped the bridge/add-on to `0.2.6-rc.12` and the frontend card/simulator to `0.3.25`. Updated release metadata, changelog, installation cache-busting examples, semantic command documentation, fixed-width operand rules, audit behavior, and migration notes.
- Preserved the fail-safe alarm/freshness, reconnect invalidation, TLS/no-downgrade, raw-TX privilege, Paho queue bounds, retained-topic cleanup, frontend unavailable rendering, CSS validation, and repository-security behavior from the merged security work.

## API examples

Publish to `vista128/control/execute` with retain disabled:

```json
{
  "action": "arm",
  "mode": "away",
  "partition": 1,
  "code": "1234",
  "transaction_id": "ha-script-42",
  "source": "ha_frontend",
  "actor_id": "user-id",
  "actor_name": "Home Admin"
}
```

```json
{
  "action": "bypass_zones",
  "partition": 1,
  "code": "1234",
  "zones": [1, 27, 104]
}
```

The second request compiles to `12346001027104**` before five-stroke segmentation. The input is never placed in the normal control result.

## Deliberately incomplete

- The parser does not decode the complete Compass/VISTA programming schema, every prompt-driven access-control menu, or every `#77` access-code extension. Those operations remain explicit interactive, model-specific, or unclassified commands and retain the exact logical sequence for later semantic work.
- Full prompt acquisition from keypad display is represented by parser context, but this PR does not claim that every panel prompt can be inferred from a single captured display page. Held-key timing and A/B/C panic-vs-macro distinctions remain configuration-dependent.
- The frontend continues to expose only ordinary `0-9`, `*`, and `#` input. A-D function buttons are not made executable by this PR.
- The implementation exposes a structured MQTT API, not a new first-class Home Assistant service. A future service can call the same `VistaCommand` and coordinator API.
- The panel serial-server connection remains unauthenticated plaintext and its checksum remains error detection, not authentication. Optional printer HTTP has the existing trusted-network assumption. These are documented operational limitations, not claims of cryptographic protection.
- An acknowledged obscure keypad/menu operation may still be unverified when no authoritative state or event feedback exists. Native core arm/disarm continues to require fresh arming-state verification.

No known behavior introduced by this PR can make a stale or ambiguous panel state look safely current. Ambiguous parsing and insufficient verification produce an explicit low-confidence/unverified result or rejection; they may produce a false negative for command confirmation, but not a new false-safe alarm/arming state.

## Migration and compatibility

Existing SQLite databases are migrated automatically by adding empty semantic audit columns. Existing rows remain valid. The existing bridge control gates remain disabled by default. The new semantic topic is subscribed only when the existing global control gate and at least one execution gate are enabled. Existing keypad and partition topics remain available under their existing gates.

Normal MQTT control ACLs should grant only the required `keypad/+/command`, `partition/+/command`, and optionally `control/execute` topics. Keep `admin/raw_tx` separate and do not grant it to ordinary HA control publishers. Actor metadata is attribution, not authorization.

## Validation

Local commands and results:

- `cd vista128_bridge && python -m unittest discover -s tests -v`: **173 tests passed**.
- `cd vista128_bridge && python -m py_compile app/vista_bridge/*.py tests/*.py`: **passed**.
- `node --check ../frontend/vista-keypad-card.js`: **passed**.
- `python scripts/check_repository_security.py`: **passed**.
- `python -m unittest discover -s scripts -p 'test_*.py' -v`: **11 tests passed**.
- `cd frontend && npm ci --no-audit --no-fund`: **passed** without lockfile changes.
- `cd frontend && npx playwright install --with-deps chromium`: **blocked by the managed container's apt privilege restrictions** (`setgroups/setegid/seteuid` and apt archive permission errors).
- `cd frontend && npm run test:render`: **49 tests attempted; browser launch was unavailable because Chromium was not installed**, so no frontend assertions executed locally. CI must run the full Chromium suite before merge.
- `git diff --check`: **passed**.
- GitHub Actions run **463** on the published head passed all jobs: `test`, `repository-security`, and `frontend-render`; the frontend job completed **49/49 Playwright tests passed**.

The PR is intentionally left open for review and CI; it is not merged here.
