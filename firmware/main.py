import time

from machine import Pin

# Internal LED on Pico W
led = Pin("LED", Pin.OUT)

print("--- Smart Greenhouse Pico W Starting ---")

# Blink 3 times to signal startup
for _ in range(3):
    led.on()
    time.sleep(0.1)
    led.off()
    time.sleep(0.1)

while True:
    print("Heartbeat: PiPico is alive and syncing.")
    led.toggle()
    time.sleep(5)
