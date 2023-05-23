# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

import math

ADC_LOW = 0
ADC_HIGH = 1
ADC_FLOAT = 2
ADC_ANY = 3
LOW = False
HIGH = True

class YukonModule:
    NAME = "Unnamed"

    ROOM_TEMP = 273.15 + 25
    RESISTOR_AT_ROOM_TEMP = 10000.0
    BETA = 3435

    def is_module(adc_level, slow1, slow2, slow3):
        return False

    def __init__(self):
        self.slot = None
        self.__adc1_func = None
        self.__adc2_func = None

    def init(self, slot, adc1_func, adc2_func):
        self.slot = slot
        self.__adc1_func = adc1_func
        self.__adc2_func = adc2_func

    def monitor(self, debug_level=0):
        return None

    def last_monitored(self):
        return OrderedDict()

    def __read_adc1(self):
        return self.__adc1_func(self.slot)

    def __read_adc2(self):
        return self.__adc2_func(self.slot)

    def __read_adc2_as_temp(self):
        sense = self.__adc2_func(self.slot)
        r_thermistor = sense / ((3.3 - sense) / 5100)
        t_kelvin = (self.BETA * self.ROOM_TEMP) / (self.BETA + (self.ROOM_TEMP * math.log(r_thermistor / self.RESISTOR_AT_ROOM_TEMP)))
        t_celsius = t_kelvin - 273.15
        # https://www.allaboutcircuits.com/projects/measuring-temperature-with-an-ntc-thermistor/
        return t_celsius
