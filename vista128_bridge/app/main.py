from __future__ import annotations

import asyncio
import logging
import os
import signal

from vista_bridge.bridge import VistaBridge
from vista_bridge.config import Settings
from vista_bridge.native_api import DEFAULT_PORT, NativeApiServer

LOG = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def main() -> None:
    settings = Settings.from_env()
    bridge = VistaBridge(settings)
    native_api: NativeApiServer | None = None

    token = os.environ.get("NATIVE_API_TOKEN", "").strip()
    if token:
        try:
            port = int(os.environ.get("NATIVE_API_PORT", str(DEFAULT_PORT)))
            native_api = NativeApiServer(bridge, token, port)
            await native_api.start()
        except Exception:
            native_api = None
            LOG.exception(
                "Native Home Assistant API failed to start; MQTT compatibility bridge remains active"
            )
    else:
        LOG.info("Native Home Assistant API disabled because no machine token was supplied")

    loop = asyncio.get_running_loop()
    current_task = asyncio.current_task()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, current_task.cancel)

    try:
        await bridge.run()
    except asyncio.CancelledError:
        LOG.info("Shutdown requested")
    finally:
        if native_api is not None:
            await native_api.stop()


if __name__ == "__main__":
    configure_logging()
    asyncio.run(main())
