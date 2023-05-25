# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from digitalio import DigitalInOut
from pwmio import PWMOut
from .common import *
from collections import OrderedDict

class BenchPowerModule(YukonModule):
    NAME = "Bench Power"

    VOLTAGE_MAX = 12.3953
    VOLTAGE_MID = 6.5052
    VOLTAGE_MIN = 0.6713
    VOLTAGE_MIN_MEASURE = 0.1477
    VOLTAGE_MID_MEASURE = 1.1706
    VOLTAGE_MAX_MEASURE = 2.2007
    PWM_MIN = 0.3
    PWM_MAX = 0.0

    TEMPERATURE_THRESHOLD = 50.0

    # | ADC1  | SLOW1 | SLOW2 | SLOW3 | Module               | Condition (if any)          |
    # |-------|-------|-------|-------|----------------------|-----------------------------|
    # | LOW   | 1     | 0     | 0     | Bench Power          |                             |
    # | FLOAT | 1     | 0     | 0     | Bench Power          | When V+ is discharging      |
    # FLOAT address included as may not be able to rely on the ADC level being low
    def is_module(adc_level, slow1, slow2, slow3):
        return slow1 is HIGH and slow2 is LOW and slow3 is LOW

    def __init__(self, halt_on_not_pgood=False):
        super().__init__()

        self.halt_on_not_pgood = halt_on_not_pgood

        self.__last_pgood = False
        self.__last_voltage = 0
        self.__last_temp = 0

    def setup(self, slot, adc1_func, adc2_func):
        super().setup(slot, adc1_func, adc2_func)

        self.voltage_pwm = PWMOut(slot.FAST2, duty_cycle=0, frequency=250000)

        self.__power_en = DigitalInOut(slot.FAST1)
        self.__power_good = DigitalInOut(slot.SLOW1)

        self.reset()

    def reset(self):
        if self.slot is not None:
            self.voltage_pwm.duty_cycle = 0
            self.__power_en.switch_to_output(False)
            self.__power_good.switch_to_input()

    def enable(self):
        self.__power_en.value = True

    def disable(self):
        self.__power_en.value = False

    def is_enabled(self):
        return self.__motors_en.value

    def __set_pwm(self, percent):
        self.voltage_pwm.duty_cycle = int(((2 ** 16) - 1) * percent)

    def set_target_voltage(self, voltage):
        if voltage >= self.VOLTAGE_MID:
            percent = min((voltage - self.VOLTAGE_MID) * 0.5 / (self.VOLTAGE_MAX - self.VOLTAGE_MID) + 0.5, 1.0)
        else:
            percent = max((voltage - self.VOLTAGE_MIN) * 0.5 / (self.VOLTAGE_MID - self.VOLTAGE_MIN), 0.0)
        self.set_target(percent)

    def set_target(self, percent):
        if percent < 0 or percent > 1.0:
            raise ValueError("percent out of range. Expected 0.0 to 1.0")

        self.__set_pwm((percent * (self.PWM_MAX - self.PWM_MIN)) + self.PWM_MIN)

    def read_voltage(self):
        # return (self.__shared_adc_voltage() * (100 + 22)) / 22
        voltage = self.__read_adc1()
        if voltage >= self.VOLTAGE_MID_MEASURE:
            return ((voltage - self.VOLTAGE_MID_MEASURE) * (self.VOLTAGE_MAX - self.VOLTAGE_MID)) / (self.VOLTAGE_MAX_MEASURE - self.VOLTAGE_MID_MEASURE) + self.VOLTAGE_MID
        else:
            return max(((voltage - self.VOLTAGE_MIN_MEASURE) * (self.VOLTAGE_MID - self.VOLTAGE_MIN)) / (self.VOLTAGE_MID_MEASURE - self.VOLTAGE_MIN_MEASURE) + self.VOLTAGE_MIN, 0.0)

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
        self.__last_voltage = self.read_voltage()
        self.__last_temp = temp

        return None

    def last_monitored(self):
        return OrderedDict({
            "PGood": self.__last_pgood,
            "VOut": self.__last_voltage,
            "T": self.__last_temp
        })
