#!/usr/bin/with-contenv bashio
set -euo pipefail

config_or_default() {
  local key="$1"
  local default_value="$2"
  if bashio::config.has_value "${key}"; then
    bashio::config "${key}"
  else
    printf '%s\n' "${default_value}"
  fi
}

cleanup_removed_options() {
  local options
  local old_key
  options="$(bashio::addon.options)"

  # These were previously exposed in the Home Assistant Options editor even
  # though they are implementation tuning. Remove stale stored values after an
  # upgrade so Supervisor does not warn about keys that are no longer in the
  # schema. Runtime behavior below uses the supported internal defaults.
  for old_key in \
    reconnect_min_seconds \
    connect_timeout_seconds \
    reconnect_max_seconds \
    frame_idle_ms \
    mqtt_outbound_queue_max \
    mqtt_inflight_messages_max \
    startup_sync_enabled \
    startup_sync_initial_delay_ms \
    startup_sync_command_delay_ms \
    startup_sync_response_timeout_seconds \
    periodic_sync_enabled \
    periodic_sync_interval_seconds \
    periodic_sync_reconnect_after_failures \
    keypad_display_enabled \
    keypad_poll_interval_seconds \
    keypad_event_refresh_delay_ms \
    control_response_timeout_seconds \
    control_verify_delay_ms \
    event_history_enabled \
    event_history_recent_limit \
    keypad_audit_enabled \
    event_history_max_rows \
    transport_print_timeout_seconds \
    transport_print_retry_seconds \
    transport_print_queue_max \
    tx_queue_max \
    raw_tx_queue_max; do
    if bashio::jq.exists "${options}" ".${old_key}"; then
      bashio::log.info "Removing obsolete advanced option '${old_key}'"
      if ! bashio::addon.option "${old_key}"; then
        bashio::log.warning "Could not remove obsolete option '${old_key}'; continuing with internal defaults"
      fi
    fi
  done
}

cleanup_removed_options

# Deployment choices exposed in the Home Assistant Options editor.
export PANEL_HOST="$(bashio::config 'panel_host')"
export PANEL_PORT="$(bashio::config 'panel_port')"
export PANEL_TIMEZONE="$(bashio::config 'panel_timezone')"
export KEYPAD_PARTITIONS="$(bashio::config 'keypad_partitions')"
export CHIME_ZONES="$(bashio::config 'chime_zones')"
export CONTROL_ENABLED="$(bashio::config 'control_enabled')"
export KEYPAD_CONTROL_ENABLED="$(bashio::config 'keypad_control_enabled')"
export NATIVE_ALARM_CONTROL_ENABLED="$(bashio::config 'native_alarm_control_enabled')"
export EVENT_HISTORY_STARTUP_DUMP_ENABLED="$(bashio::config 'event_history_startup_dump_enabled')"
export TRANSPORT_PRINT_ENABLED="$(bashio::config 'transport_print_enabled')"
export TRANSPORT_HOST="$(bashio::config 'transport_host')"
export TRANSPORT_HTTP_PORT="$(bashio::config 'transport_http_port')"
export TRANSPORT_PRINT_WIDTH="$(bashio::config 'transport_print_width')"
export RAW_LOGGING="$(bashio::config 'raw_logging')"
export DEBUG_RAW_TX_ENABLED="$(bashio::config 'debug_raw_tx_enabled')"

# Optional advanced/security settings preserve existing custom deployments but
# are omitted from defaults so upgrades do not fail when an older install lacks
# a newly introduced key.
export EVENT_HISTORY_MAX_AGE_DAYS="$(config_or_default 'event_history_max_age_days' '90')"
export MQTT_BASE_TOPIC="$(config_or_default 'mqtt_base_topic' 'vista128')"
export MQTT_DISCOVERY_PREFIX="$(config_or_default 'mqtt_discovery_prefix' 'homeassistant')"
export MQTT_TLS_ENABLED="$(config_or_default 'mqtt_tls_enabled' 'false')"
export MQTT_TLS_CA="$(config_or_default 'mqtt_tls_ca' '')"
export MQTT_TLS_CLIENT_CERT="$(config_or_default 'mqtt_tls_client_cert' '')"
export MQTT_TLS_CLIENT_KEY="$(config_or_default 'mqtt_tls_client_key' '')"
export RAW_MQTT_ENABLED="$(config_or_default 'raw_mqtt_enabled' 'false')"

# Internal operating defaults. These are intentionally not user-facing; they
# are part of the bridge's supported runtime behavior rather than deployment
# choices.
export MQTT_OUTBOUND_QUEUE_MAX="4096"
export MQTT_INFLIGHT_MESSAGES_MAX="20"
export CONNECT_TIMEOUT_SECONDS="5"
export RECONNECT_MIN_SECONDS="1"
export RECONNECT_MAX_SECONDS="30"
export FRAME_IDLE_MS="250"
export TX_QUEUE_MAX="128"
export RAW_TX_QUEUE_MAX="16"
export STARTUP_SYNC_ENABLED="true"
export STARTUP_SYNC_INITIAL_DELAY_MS="1000"
export STARTUP_SYNC_COMMAND_DELAY_MS="500"
export STARTUP_SYNC_RESPONSE_TIMEOUT_SECONDS="5"
export PERIODIC_SYNC_ENABLED="true"
export PERIODIC_SYNC_INTERVAL_SECONDS="300"
export PERIODIC_SYNC_RECONNECT_AFTER_FAILURES="3"
export KEYPAD_DISPLAY_ENABLED="true"
export KEYPAD_POLL_INTERVAL_SECONDS="7"
export KEYPAD_EVENT_REFRESH_DELAY_MS="250"
export CONTROL_RESPONSE_TIMEOUT_SECONDS="3"
export CONTROL_VERIFY_DELAY_MS="400"
export EVENT_HISTORY_ENABLED="true"
export EVENT_HISTORY_RECENT_LIMIT="20"
export KEYPAD_AUDIT_ENABLED="true"
export EVENT_HISTORY_MAX_ROWS="10000"
export EVENT_HISTORY_SQLITE_PATH="/data/vista128_events.sqlite3"
export TRANSPORT_PRINT_TIMEOUT_SECONDS="5"
export TRANSPORT_PRINT_RETRY_SECONDS="10"
export TRANSPORT_PRINT_QUEUE_MAX="5000"
export TRANSPORT_PRINT_SPOOL_PATH="/data/vista128_print_queue.sqlite3"

export MQTT_HOST="$(bashio::services mqtt 'host')"
export MQTT_PORT="$(bashio::services mqtt 'port')"
export MQTT_USERNAME="$(bashio::services mqtt 'username')"
export MQTT_PASSWORD="$(bashio::services mqtt 'password')"

APP_VERSION="$(python3 -c 'import sys; sys.path.insert(0, "/app"); from vista_bridge.version import VERSION; print(VERSION)')"
bashio::log.info "Starting Vista Turbo RS232 v${APP_VERSION}"
bashio::log.info "Serial server: ${PANEL_HOST}:${PANEL_PORT}"
bashio::log.info "MQTT broker: ${MQTT_HOST}:${MQTT_PORT}"
bashio::log.info "Periodic state reconciliation: every ${PERIODIC_SYNC_INTERVAL_SECONDS}s"
bashio::log.info "Keypad display polling: partitions ${KEYPAD_PARTITIONS}, every ${KEYPAD_POLL_INTERVAL_SECONDS}s"
bashio::log.info "Event journal: ${EVENT_HISTORY_SQLITE_PATH}; recent HA window ${EVENT_HISTORY_RECENT_LIMIT}; retention ${EVENT_HISTORY_MAX_AGE_DAYS}d"
if bashio::var.true "${EVENT_HISTORY_STARTUP_DUMP_ENABLED}"; then
  bashio::log.info "Historical event-log import enabled at startup"
fi
if bashio::var.true "${CONTROL_ENABLED}"; then
  bashio::log.warning "Panel control ENABLED: keypad=${KEYPAD_CONTROL_ENABLED}, native_alarm=${NATIVE_ALARM_CONTROL_ENABLED}"
fi
if bashio::var.true "${TRANSPORT_PRINT_ENABLED}"; then
  bashio::log.info "TransPort event receipts: http://${TRANSPORT_HOST}:${TRANSPORT_HTTP_PORT}/print"
fi

exec python3 -u /app/main.py
