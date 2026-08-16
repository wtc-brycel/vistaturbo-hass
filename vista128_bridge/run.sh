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

export PANEL_HOST="$(bashio::config 'panel_host')"
export PANEL_PORT="$(bashio::config 'panel_port')"
export PANEL_TIMEZONE="$(config_or_default 'panel_timezone' 'America/New_York')"
export MQTT_BASE_TOPIC="$(bashio::config 'mqtt_base_topic')"
export MQTT_DISCOVERY_PREFIX="$(bashio::config 'mqtt_discovery_prefix')"
export CONNECT_TIMEOUT_SECONDS="$(bashio::config 'connect_timeout_seconds')"
export RECONNECT_MIN_SECONDS="$(bashio::config 'reconnect_min_seconds')"
export RECONNECT_MAX_SECONDS="$(bashio::config 'reconnect_max_seconds')"
export FRAME_IDLE_MS="$(bashio::config 'frame_idle_ms')"
export RAW_LOGGING="$(bashio::config 'raw_logging')"
export DEBUG_RAW_TX_ENABLED="$(bashio::config 'debug_raw_tx_enabled')"
export STARTUP_SYNC_ENABLED="$(bashio::config 'startup_sync_enabled')"
export STARTUP_SYNC_INITIAL_DELAY_MS="$(bashio::config 'startup_sync_initial_delay_ms')"
export STARTUP_SYNC_COMMAND_DELAY_MS="$(bashio::config 'startup_sync_command_delay_ms')"
export STARTUP_SYNC_RESPONSE_TIMEOUT_SECONDS="$(bashio::config 'startup_sync_response_timeout_seconds')"
export PERIODIC_SYNC_ENABLED="$(config_or_default 'periodic_sync_enabled' 'true')"
export PERIODIC_SYNC_INTERVAL_SECONDS="$(config_or_default 'periodic_sync_interval_seconds' '300')"
export PERIODIC_SYNC_RECONNECT_AFTER_FAILURES="$(config_or_default 'periodic_sync_reconnect_after_failures' '3')"
export KEYPAD_DISPLAY_ENABLED="$(config_or_default 'keypad_display_enabled' 'true')"
export KEYPAD_PARTITIONS="$(config_or_default 'keypad_partitions' '1')"
export KEYPAD_POLL_INTERVAL_SECONDS="$(config_or_default 'keypad_poll_interval_seconds' '7')"
export KEYPAD_EVENT_REFRESH_DELAY_MS="$(config_or_default 'keypad_event_refresh_delay_ms' '250')"
export TRANSPORT_PRINT_ENABLED="$(config_or_default 'transport_print_enabled' 'false')"
export TRANSPORT_HOST="$(config_or_default 'transport_host' '')"
export TRANSPORT_HTTP_PORT="$(config_or_default 'transport_http_port' '9101')"
export TRANSPORT_PRINT_TIMEOUT_SECONDS="$(config_or_default 'transport_print_timeout_seconds' '5')"
export TRANSPORT_PRINT_RETRY_SECONDS="$(config_or_default 'transport_print_retry_seconds' '10')"
export TRANSPORT_PRINT_QUEUE_MAX="$(config_or_default 'transport_print_queue_max' '5000')"
export TRANSPORT_PRINT_WIDTH="$(config_or_default 'transport_print_width' '32')"
export TRANSPORT_PRINT_SPOOL_PATH="/data/vista128_print_queue.sqlite3"

export MQTT_HOST="$(bashio::services mqtt 'host')"
export MQTT_PORT="$(bashio::services mqtt 'port')"
export MQTT_USERNAME="$(bashio::services mqtt 'username')"
export MQTT_PASSWORD="$(bashio::services mqtt 'password')"

APP_VERSION="$(python3 -c 'import sys; sys.path.insert(0, "/app"); from vista_bridge.version import VERSION; print(VERSION)')"
bashio::log.info "Starting Vista Turbo RS232 v${APP_VERSION}"
bashio::log.info "Serial server: ${PANEL_HOST}:${PANEL_PORT}"
bashio::log.info "MQTT broker: ${MQTT_HOST}:${MQTT_PORT}"
if bashio::var.true "${PERIODIC_SYNC_ENABLED}"; then
  bashio::log.info "Periodic state reconciliation: every ${PERIODIC_SYNC_INTERVAL_SECONDS}s"
fi
if bashio::var.true "${KEYPAD_DISPLAY_ENABLED}"; then
  bashio::log.info "Keypad display polling: partitions ${KEYPAD_PARTITIONS}, every ${KEYPAD_POLL_INTERVAL_SECONDS}s"
fi
if bashio::var.true "${TRANSPORT_PRINT_ENABLED}"; then
  bashio::log.info "TransPort event receipts: http://${TRANSPORT_HOST}:${TRANSPORT_HTTP_PORT}/print"
fi

exec python3 -u /app/main.py
