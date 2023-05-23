# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from digitalio import DigitalInOut, Pull
from .common import *
from collections import OrderedDict

class LEDStripModule(YukonModule):
    NAME = "LED Strip"
    NEOPIXEL = 0
    DOTSTAR = 1
    TEMPERATURE_THRESHOLD = 50.0

    # | ADC1  | SLOW1 | SLOW2 | SLOW3 | Module               | Condition (if any)          |
    # |-------|-------|-------|-------|----------------------|-----------------------------|
    # | LOW   | 1     | 1     | 1     | LED Strip            |                             |
    def is_module(adc_level, slow1, slow2, slow3):
        return adc_level == ADC_LOW and slow1 is HIGH and slow2 is HIGH and slow3 is HIGH

    def __init__(self, strip_type, num_pixels, brightness=1.0, halt_on_not_pgood=True):
        super().__init__()
        self.strip_type = strip_type
        if self.strip_type == self.NEOPIXEL:
            self.NAME += " (NeoPixel)"
        else:
            self.NAME += " (DotStar)"

        self.num_pixels = num_pixels
        self.brightness = brightness
        self.halt_on_not_pgood = halt_on_not_pgood
        self.__last_pgood = False
        self.__last_temp = 0

    def enable(self):
        self.p_en.value = True

    def disable(self):
        self.p_en.value = False

    def reset(self):
        self.p_en.switch_to_output(False)
        self.p_good.switch_to_input(Pull.UP)

    def read_power_good(self):
        return self.p_good.value

    def read_temperature(self):
        return self.__read_adc2_as_temp()

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

    def monitor(self, debug_level=0):
        pgood = self.read_power_good()
        if pgood is not True:
            if self.halt_on_not_pgood:
                raise RuntimeError(f"Power is not good")

        temp = self.read_temperature()
        if temp > self.TEMPERATURE_THRESHOLD:
            raise RuntimeError(f"Temperature of {temp}°C exceeded the user set level of {self.TEMPERATURE_THRESHOLD}°C")

        message = None
        if debug_level >= 1:
            if self.__last_pgood is True and pgood is not True:
                message = f"Power is not good"
            elif self.__last_pgood is not True and pgood is True:
                message = f"Power is good"

        self.__last_pgood = pgood
        self.__last_temp = temp

        return message

    def last_monitored(self):
        return OrderedDict({
            "PGood": self.__last_pgood,
            "T": self.__last_temp
        })
