from constants import (
    DISPLAY_DEFAULT_ADDR,
    DISPLAY_DEFAULT_HEIGHT,
    DISPLAY_DEFAULT_WIDTH,
    DISPLAY_I2C_FREQ,
    DISPLAY_I2C_ID,
    DISPLAY_I2C_SCL,
    DISPLAY_I2C_SDA,
)
from lib.ssd1306 import SSD1306_I2C
from machine import I2C, Pin


class Display:
    """SSD1306 OLED display driven over I2C.

    The `config` dict is read from the manifest and expected to look like:

        {
            "type": "ssd1306",
            "width": 128,
            "height": 64,
            "i2c": {"id": 0, "sda": 4, "scl": 5},
            "addr": 0x3C,
        }
    """

    def __init__(self, config):
        i2c_cfg = config.get("i2c", {})
        self.i2c = I2C(
            i2c_cfg.get("id", DISPLAY_I2C_ID),
            scl=Pin(i2c_cfg.get("scl", DISPLAY_I2C_SCL)),
            sda=Pin(i2c_cfg.get("sda", DISPLAY_I2C_SDA)),
            freq=i2c_cfg.get("freq", DISPLAY_I2C_FREQ),
        )
        self.oled = SSD1306_I2C(
            config.get("width", DISPLAY_DEFAULT_WIDTH),
            config.get("height", DISPLAY_DEFAULT_HEIGHT),
            self.i2c,
            addr=config.get("addr", DISPLAY_DEFAULT_ADDR),
        )

    def clear(self):
        """Blank the display buffer."""
        self.oled.fill(0)

    def text(self, string, x, y, color=1):
        """Draw text at the given pixel coordinates."""
        self.oled.text(string, x, y, color)

    def show(self):
        """Push the buffer to the physical display."""
        self.oled.show()
