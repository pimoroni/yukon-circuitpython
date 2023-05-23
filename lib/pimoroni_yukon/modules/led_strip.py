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

    def __init__(self, strip_type, num_pixels, brightness=1.0, halt_on_not_pgood=False):
        super().__init__()
        self.__strip_type = strip_type
        if self.__strip_type == self.NEOPIXEL:
            self.NAME += " (NeoPixel)"
        else:
            self.NAME += " (DotStar)"

        self.__num_pixels = num_pixels
        self.__brightness = brightness
        self.halt_on_not_pgood = halt_on_not_pgood

        self.__last_pgood = False
        self.__last_temp = 0

    def setup(self, slot, adc1_func, adc2_func):
        super().setup(slot, adc1_func, adc2_func)

        if self.__strip_type == self.NEOPIXEL:
            from neopixel import NeoPixel
            self.pixels = NeoPixel(slot.FAST4, self.__num_pixels, brightness=self.__brightness, auto_write=False)
        else:
            from adafruit_dotstar import DotStar
            self.pixels = DotStar(slot.FAST3, slot.FAST4, self.__num_pixels, brightness=self.__brightness, auto_write=False)

        self.__power_good = DigitalInOut(slot.FAST1)
        self.__power_en = DigitalInOut(slot.FAST2)

        self.reset()

    def reset(self):
        if self.slot is not None:
            self.__power_en.switch_to_output(False)
            self.__power_good.switch_to_input(Pull.UP)

    def enable(self):
        self.__power_en.value = True

    def disable(self):
        self.__power_en.value = False

    def is_enabled(self):
        return self.__power_en.value

    def read_power_good(self):
        return self.__power_good.value

    def read_temperature(self):
        return self.__read_adc2_as_temp()

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
