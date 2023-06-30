# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from .common import *
from pwmio import PWMOut
from digitalio import DigitalInOut
from adafruit_motor.servo import Servo
from collections import OrderedDict


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

    def initialise(self, slot, adc1_func, adc2_func):
        # Create pwm objects
        self.__pwms = [PWMOut(slot.FAST1, frequency=50),
                       PWMOut(slot.FAST2, frequency=50),
                       PWMOut(slot.FAST3, frequency=50),
                       PWMOut(slot.FAST4, frequency=50)]

        # Create servo objects
        self.servos = [Servo(self.__pwms[i]) for i in range(len(self.__pwms))]

        # Create the power control pin objects
        self.__power_en = DigitalInOut(slot.SLOW1)
        self.__power_good = DigitalInOut(slot.SLOW2)

        # Configure servos and power pins
        self.configure()

        # Pass the slot and adc functions up to the parent now that module specific initialisation has finished
        super().initialise(slot, adc1_func, adc2_func)

    def configure(self):
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

        temperature = self.read_temperature()
        if temperature > self.TEMPERATURE_THRESHOLD:
            raise RuntimeError(f"Temperature of {temperature}°C exceeded the user set level of {self.TEMPERATURE_THRESHOLD}°C")

        message = None
        if debug_level >= 1:
            if self.__last_pgood is True and pgood is not True:
                message = f"Power is not good"
            elif self.__last_pgood is not True and pgood is True:
                message = f"Power is good"

        self.__last_pgood = pgood
        self.__power_good_throughout = self.__power_good_throughout and pgood

        self.__max_temperature = max(temperature, self.__max_temperature)
        self.__min_temperature = min(temperature, self.__min_temperature)
        self.__avg_temperature += temperature
        self.__count_avg += 1

        return message

    def get_readings(self):
        return OrderedDict({
            "PGood": self.__power_good_throughout,
            "T_max": self.__max_temperature,
            "T_min": self.__min_temperature,
            "T_avg": self.__avg_temperature
        })

    def process_readings(self):
        if self.__count_avg > 0:
            self.__avg_temperature /= self.__count_avg

    def clear_readings(self):
        self.__power_good_throughout = True
        self.__max_temperature = float('-inf')
        self.__min_temperature = float('inf')
        self.__avg_temperature = 0
        self.__count_avg = 0
