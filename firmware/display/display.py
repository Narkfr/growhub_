from machine import I2C, Pin

from .ssd1306 import SSD1306_I2C


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
            i2c_cfg.get("id", 0),
            scl=Pin(i2c_cfg.get("scl", 5)),
            sda=Pin(i2c_cfg.get("sda", 4)),
            freq=i2c_cfg.get("freq", 400000),
        )
        self.oled = SSD1306_I2C(
            config.get("width", 128),
            config.get("height", 64),
            self.i2c,
            addr=config.get("addr", 0x3C),
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
