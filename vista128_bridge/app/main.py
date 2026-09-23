from __future__ import annotations

import asyncio
import logging
import signal

from vista_bridge.admin_server import AdminServer
from vista_bridge.bridge import VistaBridge
from vista_bridge.config import Settings


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def main() -> None:
    settings = Settings.from_env()
    bridge = VistaBridge(settings)
    admin = AdminServer(bridge)

    loop = asyncio.get_running_loop()
    current_task = asyncio.current_task()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, current_task.cancel)

    await admin.start()
    try:
        await bridge.run()
    except asyncio.CancelledError:
        logging.getLogger(__name__).info("Shutdown requested")
    finally:
        await admin.stop()


if __name__ == "__main__":
    configure_logging()
    asyncio.run(main())
