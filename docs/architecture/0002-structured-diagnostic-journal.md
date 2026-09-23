# ADR 0002: Structured Diagnostic Journal

Status: Accepted  
Date: 2026-09-23

## Context

Vista Turbo has several independent runtime planes that can fail without the others failing. A panel TCP session can remain healthy while Home Assistant delivery is unavailable, and a Home Assistant transport can recover without requiring a VISTA reconnect.

The ordinary Home Assistant App log is useful for live operation, but it is not a durable incident record. Log rotation can remove the beginning of an outage before troubleshooting starts. Persisting every log line or protocol frame would create noise, increase privacy risk, and duplicate the role of a general log platform.

Vista Turbo needs enough durable observability to reconstruct failures and support the upcoming management UI without becoming a log aggregation system.

## Decision

The App owns a small structured Diagnostic Journal backed by a separate SQLite database.

The Diagnostic Journal is operational evidence only. It is separate from:

- the VISTA event journal;
- keypad/control audit records;
- the normal application log.

The default database is:

`/data/vistaturbo_diagnostics.sqlite3`

The default retention policy is:

- 30 days;
- 25,000 records;
- whichever limit is reached first.

Pruning is bounded and incremental.

## Event model

Every diagnostic event has these stable fields:

- event ID;
- occurrence time;
- severity;
- category;
- component;
- event type;
- human-readable message;
- App boot ID;
- panel session ID;
- Home Assistant transport session ID;
- correlation ID;
- sanitized JSON details.

Event types are defined centrally. Runtime code does not invent arbitrary event names.

The initial categories are:

- `system`
- `panel_transport`
- `protocol`
- `synchronization`
- `ha_transport`
- `state_delivery`
- `control`
- `persistence`
- `printer`
- `management`

Severities are:

- `debug`
- `info`
- `warning`
- `error`
- `critical`

Routine successful traffic is not persisted merely because it was logged at INFO.

## What is persisted

The journal records operational transitions and faults such as:

- App start and stop;
- unexpected long-running task termination;
- panel connection failure, loss, recovery, and reconnect scheduling;
- invalid VISTA frames;
- synchronization lifecycle for startup/recovery and any synchronization failure;
- unsafe or tainted VISTA session recovery;
- Home Assistant transport connection, disconnection, watchdog recovery, and replacement;
- Home Assistant state replay start, failure, and completion;
- bounded queue saturation;
- safety-interlock activation;
- sparse health snapshots.

## What is not persisted

The journal does not record:

- every VISTA frame;
- routine keypad polling;
- every MQTT publication;
- successful MQTT heartbeats;
- individual state updates;
- raw protocol payloads;
- panel PINs or installer codes;
- MQTT passwords or tokens;
- Home Assistant credentials;
- TLS private-key material.

The normal application log remains the appropriate place for transient low-level detail during an active troubleshooting session.

## Correlation and sessions

Each App process has a boot ID.

Each successful panel TCP session has a panel session ID.

Each successful Home Assistant transport connection has a transport session ID.

Recovery sequences use correlation IDs. One MQTT watchdog event can therefore appear in the UI as one incident containing:

1. transport watchdog trigger;
2. recovery start;
3. client replacement;
4. transport reconnection;
5. state replay;
6. replay completion.

Panel reconnect retries use the same model.

## Health snapshots

The App writes one structured health snapshot every 15 minutes by default.

The snapshot includes bounded operational state such as:

- App uptime;
- panel connection and state freshness;
- panel state-session generation;
- Home Assistant transport health and acknowledgement age;
- last successful synchronization;
- synchronization failure count;
- RX/TX/invalid frame counters;
- bounded queue depths;
- event-printer status.

Health snapshots provide context before a failure without storing routine traffic.

## Sanitization

Diagnostic details are sanitized before SQLite insertion.

Sensitive keys such as passwords, PINs, credentials, tokens, private keys, command sequences, and raw payloads are replaced with a redaction marker. Nested objects, lists, string length, object depth, and total JSON size are bounded.

Diagnostics are best-effort. Failure to initialize or write the Diagnostic Journal must not stop panel processing or Home Assistant control.

## Management UI contract

The management UI may read the journal through the App backend.

The core journal supports bounded recent-event queries filtered by:

- severity;
- category;
- component;
- event type;
- correlation ID;
- boot ID;
- time range.

Results can be returned newest-first or oldest-first.

The initial UI should expose:

- current health overview;
- diagnostic event table;
- correlation-based incident view;
- sanitized support export.

The journal API is an internal App contract. The browser does not receive direct SQLite access.

## Transport independence

`ha_transport` and `state_delivery` describe product responsibilities, not MQTT specifically.

MQTT is the current Home Assistant transport and remains compatibility infrastructure during the migration defined by ADR 0001. The same diagnostic categories, session model, correlation model, and UI remain valid when the native private API/WebSocket becomes the primary Home Assistant transport.

## Non-goals

This design does not provide:

- centralized remote log ingestion;
- Elasticsearch or OpenSearch;
- distributed tracing;
- general-purpose metrics storage;
- arbitrary log parsing;
- unlimited retention;
- a second security-event journal.

If those capabilities become necessary later, they should consume the structured diagnostic interface rather than expanding this SQLite journal into a general observability platform.
