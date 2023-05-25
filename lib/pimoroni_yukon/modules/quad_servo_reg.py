# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from digitalio import DigitalInOut
from .common import *
from collections import OrderedDict
from pwmio import PWMOut
from adafruit_motor.servo import Servo


class QuadServoRegModule(YukonModule):
    NAME = "Quad Servo Regulated"
    NUM_SERVOS = 4
    TEMPERATURE_THRESHOLD = 50.0

    # | ADC1  | SLOW1 | SLOW2 | SLOW3 | Module               | Condition (if any)          |
    # |-------|-------|-------|-------|----------------------|-----------------------------|
    # | FLOAT | 0     | 1     | 0     | Quad Servo Regulated |                             |
    def is_module(adc_level, slow1, slow2, slow3):
        return adc_level == ADC_FLOAT and slow1 is LOW and slow2 is HIGH and slow3 is LOW

    def __init__(self, halt_on_not_pgood=False):
        super().__init__()
        self.halt_on_not_pgood = halt_on_not_pgood

        self.__last_pgood = False
        self.__last_temp = 0
        
        self.__initialised = False

    def setup(self, slot, adc1_func, adc2_func):
        super().setup(slot, adc1_func, adc2_func)

        # Create PWMOut objects
        self.__pwms = [PWMOut(slot.FAST1, frequency=50),
                       PWMOut(slot.FAST2, frequency=50),
                       PWMOut(slot.FAST3, frequency=50),
                       PWMOut(slot.FAST4, frequency=50)]

        # Create servo objects
        self.servos = [Servo(self.__pwms[i]) for i in range(len(self.__pwms))]

        self.__power_en = DigitalInOut(slot.SLOW1)
        self.__power_good = DigitalInOut(slot.SLOW2)

        self.__initialised = True
        self.reset()

    def reset(self):
        if self.slot is not None and self.__initialised:
            for servo in self.servos:
                servo.angle = None

            self.__power_en.switch_to_output(False)
            self.__power_good.switch_to_input()

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
