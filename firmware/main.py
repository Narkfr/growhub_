import asyncio
from secrets import secrets

from constants import WATCHDOG_FEED_SECONDS, WATCHDOG_TIMEOUT_MS
from machine import WDT
from manifest import MANIFEST
from src.app import GrowHubController


async def _feed_watchdog(wdt):
    """Feed the watchdog so the board reboots if the loop hangs."""
    while True:
        wdt.feed()
        await asyncio.sleep(WATCHDOG_FEED_SECONDS)


async def main():
    print("Initializing GrowHub...")
    wdt = WDT(timeout=WATCHDOG_TIMEOUT_MS)
    app = GrowHubController(MANIFEST, secrets)
    await asyncio.gather(app.run(), _feed_watchdog(wdt))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("System stopped by user")
