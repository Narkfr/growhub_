"""GrowHub display package.

Provides a hardware-agnostic wrapper around the connected OLED display
(currently an SSD1306 128x64 driven over I2C).
"""

from .display import Display

__all__ = ["Display"]
