import asyncio
from secrets import secrets

from manifest import MANIFEST
from src.app import GrowHubController


async def main():
    print("Initializing GrowHub...")
    app = GrowHubController(MANIFEST, secrets)
    await app.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("System stopped by user")
