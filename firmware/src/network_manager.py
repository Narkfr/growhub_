import network
import uasyncio as asyncio
from constants import (
    WIFI_CONNECT_ATTEMPT_SECONDS,
    WIFI_CONNECT_ATTEMPTS,
    WIFI_RETRY_SECONDS,
)


class NetworkManager:
    """Manages Wi-Fi connection and persistence."""

    def __init__(self, ssid, password):
        self.ssid = ssid
        self.password = password
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)

    async def connect(self):
        """Initial connection attempt."""
        if not self.wlan.isconnected():
            print(f"Connecting to {self.ssid}...")
            self.wlan.connect(self.ssid, self.password)

            for _ in range(WIFI_CONNECT_ATTEMPTS):
                if self.wlan.isconnected():
                    break
                await asyncio.sleep(WIFI_CONNECT_ATTEMPT_SECONDS)

        if self.wlan.isconnected():
            print(f"Wi-Fi Connected: {self.wlan.ifconfig()[0]}")
            return True
        return False

    async def keep_connected(self):
        """Background task to ensure the connection stays alive."""
        while True:
            if not self.wlan.isconnected():
                print("Wi-Fi lost, reconnecting...")
                await self.connect()
            await asyncio.sleep(WIFI_RETRY_SECONDS)
