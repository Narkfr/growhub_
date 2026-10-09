import asyncio
from secrets import secrets

from machine import WDT
from manifest import MANIFEST
from src.app import GrowHubController


async def _feed_watchdog(wdt):
    """Feed the watchdog so the board reboots if the loop hangs."""
    while True:
        wdt.feed()
        await asyncio.sleep(2)


async def main():
    print("Initializing GrowHub...")
    wdt = WDT(timeout=8000)
    app = GrowHubController(MANIFEST, secrets)
    await asyncio.gather(app.run(), _feed_watchdog(wdt))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("System stopped by user")
