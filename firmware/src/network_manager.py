import network
import uasyncio as asyncio


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

            # Timeout of 10 seconds
            for _ in range(10):
                if self.wlan.isconnected():
                    break
                await asyncio.sleep(1)

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
            await asyncio.sleep(30)
