# Vista Turbo RS232

Home Assistant App for the RS-232 automation interface used by Honeywell/Resideo VISTA Turbo alarm panels.

This project has been developed and tested against a **VISTA-128BPT**. Other VISTA Turbo models are currently untested and are not claimed as supported. It is not a general VISTA integration.

Current status: read-only monitoring is operational. The bridge publishes partition state, assigned zones, VISTA alpha descriptors, decoded events, health metrics, and optional TransPort receipt output through MQTT Discovery. Home Assistant arm/disarm commands are not sent to the panel.

## Runtime path

```text
VISTA-128BPT
    |
  RS-232
    |
TCP serial server
    |
Vista Turbo RS232
    |
   MQTT
    |
Home Assistant
```

## Current features

- Raw VISTA frame capture with length and checksum validation
- Startup state and metadata synchronization
- Five-minute state reconciliation by default
- Partition and assigned-zone MQTT Discovery entities
- Real-time `1Bnq` event handling
- Zone alpha descriptor import
- Panel clock-offset diagnostics
- Optional continuous event receipts through TransPort
- Guarded raw transmit for protocol testing

See `DOCS.md` for configuration and protocol behavior.

## AI disclosure

This App was made with the use of AI - ChatGPT Codex, specifically - to understand how the RS232 automation protocol exposed by the Vista works. Much of the information surrounding the Vista Turbo panels was not easily available to me and buried in manufacturer-specific documentation that was not provided by Honeywell. Much of this reverse-engineering was assisted by Crestron's documentation for their integration with the Vista Turbo panels.

Despite my reservations, this would not have been possible without the use of AI. I encourage you to review the source code for yourself to understand how it works. I have taken effort to ensure modularity and optimization in the code to the best I am able to for a project of this size that will only ever likely be used by me. 

I will report back with my experiences as I use this. So far, it is a substantial improvement over the cloud-based TotalConnect 2.0 integration.
