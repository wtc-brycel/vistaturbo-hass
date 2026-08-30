# ADR 0001: Home Assistant-native VISTA Turbo suite

- Status: Accepted
- Accepted: 2026-08-30
- Scope: Product architecture for Vista Turbo HASS

## Context

Vista Turbo HASS began as a Home Assistant App that translated the VISTA Turbo RS-232 automation interface into MQTT Discovery entities and custom Lovelace cards. That approach proved the panel protocol, state model, event journal, control transaction model, fail-safe availability behavior, and frontend concepts, but MQTT is not the desired long-term architectural center of a product that exists exclusively inside Home Assistant.

The project now has a mature protocol foundation: validated framing, authoritative panel state, protocol-correct startup/recovery synchronization, event-driven zone projection, a canonical `VistaCommand` model, serialized control transactions, verification, bounded audit storage, and explicit fail-safe handling of stale or ambiguous state.

The next phase adds broader alarm-system management, beginning with panel user management and later extending selectively into outputs, partitions/zones, VistaKey/access control, schedules, timers, diagnostics, and other supported system features. This requires a deliberate split between VISTA protocol/domain responsibilities, Home Assistant-native responsibilities, and human administration.

## Decision

Vista Turbo HASS is a **Home Assistant-native alarm-system suite**. It is not an MQTT bridge with an attached web page.

The product will use three explicit architectural planes.

### 1. Protocol plane: Home Assistant App

The existing App remains the sole VISTA protocol and domain engine.

It owns:

- RS-232/TCP transport and framing;
- packet validation and corruption recovery;
- protocol parsing and model-specific behavior;
- `VistaState` and authoritative state/freshness rules;
- `VistaCommand`, planning, serialization, prompt/transaction state machines, and verification;
- panel user-management transactions and write-only credential storage;
- event/audit persistence;
- recovery/reconnect policy;
- a private API/event stream for the Home Assistant integration;
- the backend for the ingress management application.

No Home Assistant integration code or browser code may implement a second VISTA protocol stack.

### 2. Home Assistant integration plane: `custom_components/vistaturbo`

A first-class companion integration will become the primary Home Assistant-facing API.

It owns:

- one UI-created ConfigEntry per VISTA installation;
- app discovery/bootstrap appropriate to Home Assistant Supervisor;
- native device/entity registration;
- native `alarm_control_panel`, `binary_sensor`, `sensor`, `event`, `switch`, `button`, `lock`, or other entities only where their semantics genuinely match the VISTA capability;
- Home Assistant actions for operations that do not have a correct native entity action;
- Home Assistant `Context.user_id` attribution and permission-aware execution;
- push-driven state updates over the private bridge API/WebSocket;
- integration availability, diagnostics, Repairs, translations, reconfigure/options flows, and other modern Home Assistant lifecycle facilities.

The integration speaks semantic bridge APIs. It does not know keypad byte sequences, `#77` prompt grammar, panel framing, or other VISTA transport details.

### 3. Management plane: Supervisor ingress application

The App will expose a first-class management SPA through Home Assistant Supervisor ingress.

The UI is intentionally a curated **Compass-like management layer**, not a replacement for Honeywell Compass or a raw panel-programming workstation.

Initial management areas:

- Overview
- Users
- Events
- Diagnostics

Expected future areas, where panel behavior is sufficiently understood and safely supported:

- Partitions and zones
- Bypasses
- Outputs and output groups
- VistaKey/access control
- Schedules and device timers
- Interface/system health
- Command/audit history

Raw programming-field editing, arbitrary memory editing, and broad reproduction of installer programming are non-goals.

## Authentication and authorization

### Human UI authentication

The management UI uses **Home Assistant authentication exclusively** through Supervisor ingress.

There is no separate Vista Turbo username/password, HTTP basic-auth realm, browser API key, local user database, or second MFA/session system.

The ingress backend consumes the authenticated `X-Remote-User-*` identity supplied by Supervisor and restricts its human-facing server to the ingress path/proxy. The ingress service is not published as a normal LAN web server.

Administrative management surfaces begin as admin-only. Any later non-admin surface must be deliberately permission-scoped rather than achieved by weakening the management console globally.

### Core-to-App authentication

The Home Assistant integration uses a private machine-to-machine channel on the Home Assistant/Supervisor application network. It must not require a human to create, copy, or manage another credential.

An automatically provisioned installation-local machine trust mechanism may be used as defense in depth. This is distinct from human authentication and must remain invisible to the user.

## Source-of-truth hierarchy

### Panel authority

The VISTA panel is authoritative for physical/security state, including:

- armed state;
- zone conditions;
- alarms;
- bypasses;
- output state when authoritative readback exists;
- programmed user/access configuration when it can be observed authoritatively;
- other panel state exposed by validated protocol evidence.

Unknown, incomplete, stale, or unverifiable panel state remains unknown/unavailable. The management database is never allowed to make uncertain panel state appear confirmed.

### Bridge authority

The App is authoritative for VISTA protocol/domain interpretation and transactional evidence.

### Home Assistant authority

Home Assistant is authoritative for Home Assistant identity, permissions, entity/device semantics, configuration lifecycle, and automation context.

## Home Assistant identity and VISTA users

Home Assistant users and VISTA users are linked identities, not a shared credential system.

A managed panel user may contain:

- panel user number;
- friendly/display name;
- optional Home Assistant user ID mapping;
- home partition and partition permissions;
- authority level and supported user attributes;
- access-group/RF metadata where supported;
- management/confirmation state;
- write-only credential presence;
- audit metadata.

VISTA PINs remain VISTA credentials. Home Assistant passwords are never reused as panel codes.

### Credential handling

A VISTA PIN may be retained only when necessary to execute explicitly supported identity-based panel operations. It is write-only from all normal product surfaces.

PINs must never be exposed through:

- Home Assistant entity state or attributes;
- Recorder;
- Home Assistant event payloads;
- MQTT telemetry/discovery;
- diagnostics or Repairs;
- normal logs;
- user-list API responses;
- browser localStorage/sessionStorage;
- management list/read endpoints.

APIs may report `credential_present: true`; they do not return the credential.

### Runtime attribution

Human Home Assistant actions use `Context.user_id` and the configured HA-to-VISTA mapping.

Background automations without a human context use an explicitly configured automation VISTA identity. They must never silently borrow a human Master credential.

Ingress management operations are attributed to the authenticated ingress HA user.

## Home Assistant object-model rules

### Config entries

Use one ConfigEntry per VISTA installation. Do not create ConfigEntries or Config Subentries for every VISTA user, zone, output, or partition merely as a storage mechanism.

### Devices

Do not fabricate physical topology. The panel is a real device. Logical partitions and zones do not automatically become fake devices. Child devices are created only when the underlying hardware identity is genuinely known and useful.

### Entities

Use native entities when semantics fit:

- partitions: `alarm_control_panel`;
- persistent binary conditions: `binary_sensor`;
- persistent authoritative on/off outputs: `switch`;
- momentary operations: `button` where appropriate;
- transient occurrences: `event` where appropriate;
- access-control state: `lock` only if the actual panel semantics genuinely match a lock.

Do not create entities merely to make configuration editable. In particular, panel users must not become hundreds of `text`, `select`, or `switch` entities.

### Actions

Prefer native entity actions when Home Assistant already models the operation correctly. Add `vistaturbo.*` actions only for semantic operations that do not have a correct native entity model.

Administrative user provisioning is initially a management-console workflow, not a general automation action surface.

## Push model and private API

The native integration is push-first.

Target flow:

```text
Home Assistant integration
        |
        | private authenticated WebSocket/API
        v
VISTA Turbo App
        |
        | authoritative snapshot + state/event stream
        v
Home Assistant entities/events
```

On connection/reconnection, the bridge supplies an authoritative snapshot. Subsequent validated changes are pushed. Recovery/freshness semantics remain owned by the bridge.

The integration must not replace MQTT polling with HTTP polling.

The human ingress surface and the machine integration API are separate trust surfaces. The ingress browser path is not reused as the Core RPC authentication model.

## MQTT policy

MQTT is retained for compatibility during migration, but is no longer the architectural contract between Vista Turbo HASS and Home Assistant.

Target architecture:

```text
                 +--> native private API --> Home Assistant integration
VISTA --> App ---|
                 +--> MQTT compatibility output (optional)
```

Existing MQTT behavior should remain compatible while native coverage is incomplete. Once native integration coverage is sufficient, MQTT becomes optional compatibility/interop infrastructure rather than a mandatory Home Assistant dependency.

New product features should not be designed around MQTT solely because older features used it.

## Management UI principles

The ingress UI is an overall alarm-system administration console.

It should:

- use semantic domain concepts rather than raw keypad sequences;
- clearly distinguish confirmed, partially confirmed, observed, and uncertain panel configuration;
- present destructive/security-sensitive operations deliberately;
- use Home Assistant identity for attribution;
- remain useful on desktop and mobile within the HA shell;
- expose advanced diagnostics separately from ordinary administration;
- remain extensible as supported VISTA capabilities grow.

It must not:

- duplicate Home Assistant dashboards/entities as a second general control UI;
- expose secrets for convenience;
- claim authoritative readback the protocol cannot provide;
- turn into an unrestricted Compass/programming clone.

## Quality bar

The native integration and App management surface are designed to current Home Assistant conventions from their first implementation rather than written as legacy-style custom code and modernized later.

Engineering targets include:

- async/non-blocking Home Assistant integration code;
- UI configuration and reconfiguration;
- push-first state updates;
- correct availability semantics;
- stable unique IDs and conservative device modeling;
- translations/localizable user-facing strings;
- Repairs for actionable configuration/integrity problems;
- privacy-safe diagnostics;
- strong automated coverage, using current Home Assistant Gold/Platinum quality practices as the design benchmark even while the component is custom;
- explicit failure/unknown states instead of optimistic security state.

## Development tracks

Future roadmap work is separated into parallel tracks sharing the same bridge domain layer.

### Protocol track

- P1: native output/status control
- P2: complete event taxonomy
- P3: semantic event metadata
- P4: native zone-list bypass/unbypass
- P5: authoritative zone metadata/CO
- P6: VistaKey/access control
- later model-specific capabilities

### Home Assistant platform track

- HA0: native integration and private API foundation
- HA1: native panel/partition entities
- HA2: native zones/events
- HA3: native semantic control/actions and identity attribution
- HA4: remove MQTT as a required Home Assistant transport once parity is sufficient

### Management track

- M0: ingress application shell and authenticated identity plumbing
- M1: panel user management and HA-user mapping
- M2: outputs
- M3: partitions/zones
- M4: access control
- M5: schedules/timers and other intentionally supported administration

Tracks may advance independently, but they may not violate the three-plane boundary.

## Pull-request review invariants

Every future PR should be reviewed against these questions:

1. Is VISTA protocol/domain logic implemented only in the App/bridge?
2. Does Home Assistant receive semantic state/actions rather than panel byte grammar?
3. Is the panel still authoritative, with uncertainty represented fail-safe?
4. Is this capability represented using the most correct native HA entity/action/lifecycle model?
5. Is human authentication delegated to Home Assistant rather than reimplemented?
6. Are user identity and permissions attributable through Home Assistant context where applicable?
7. Are credentials excluded from state, telemetry, diagnostics, browser storage, and normal logs?
8. Does the ingress UI remain a management console rather than a second Home Assistant dashboard system?
9. Is MQTT compatibility being preserved without making MQTT the design constraint for new native functionality?
10. Does the change preserve push-first, bounded, non-blocking and recovery-safe behavior?

A PR that violates one of these invariants requires an explicit architecture amendment rather than silently changing the product model.

## Consequences

This decision adds a companion Home Assistant integration and a private App API in addition to the existing App. That increases implementation surface, but creates clean responsibility boundaries and allows substantially tighter Home Assistant integration without placing long-running VISTA protocol state machines inside Home Assistant Core.

The management UI can grow into a coherent alarm-system suite without forcing complex administration into entity state or ConfigFlow forms. Home Assistant can use its native authentication, permissions, entities, actions, Repairs, diagnostics and automation context. MQTT can be preserved for compatibility while ceasing to limit the product's design.

This ADR supersedes any assumption that MQTT Discovery is the permanent primary Home Assistant integration architecture.