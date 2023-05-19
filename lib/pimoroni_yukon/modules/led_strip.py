# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from digitalio import DigitalInOut
from .common import *

class LEDStripModule(YukonModule):
    NAME = "LED Strip"
    NEOPIXEL = 0
    DOTSTAR = 1

    def __init__(self, strip_type, num_pixels, brightness=1.0):
        super().__init__()
        self.strip_type = strip_type
        if self.strip_type == self.NEOPIXEL:
            self.NAME += " [NeoPixel]"
        else:
            self.NAME += " [DotStar]"

        self.num_pixels = num_pixels
        self.brightness = brightness

    def is_module(adc_level, slow1, slow2, slow3):
        if adc_level == ADC_LOW and slow1 is HIGH and slow2 is HIGH and slow3 is HIGH:
            return True

        return False

    def enable(self):
        self.p_en.value = True

    def disable(self):
        self.p_en.value = False

    def reset(self):
        self.p_en.switch_to_output(False)
        self.p_good.switch_to_input()

    def init(self, slot, adc1_func, adc2_func):
        super().init(slot, adc1_func, adc2_func)

        if self.strip_type == self.NEOPIXEL:
            from neopixel import NeoPixel
            self.pixels = NeoPixel(slot.FAST4, self.num_pixels, brightness=self.brightness, auto_write=False)
        else:
            from adafruit_dotstar import DotStar
            self.pixels = DotStar(slot.FAST3, slot.FAST4, self.num_pixels, brightness=self.brightness, auto_write=False)

        self.p_good = DigitalInOut(slot.FAST1)
        self.p_en = DigitalInOut(slot.FAST2)

        self.reset()
