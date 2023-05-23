# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from .common import *
from digitalio import DigitalInOut
from pwmio import PWMOut
from adafruit_motor.motor import DCMotor

class BigMotorModule(YukonModule):
    NAME = "Big Motor + Encoder"
    DEFAULT_FREQUENCY = 25000
    TEMPERATURE_THRESHOLD = 50.0
    CURRENT_THRESHOLD = 10.0
    SHUNT_RESISTOR = 0.001
    GAIN = 80

    # | ADC1  | SLOW1 | SLOW2 | SLOW3 | Module               | Condition (if any)          |
    # |-------|-------|-------|-------|----------------------|-----------------------------|
    # | LOW   | 0     | 0     | 1     | Big Motor            | Not in fault                |
    # | LOW   | 0     | 1     | 1     | Big Motor            | In fault                    |
    def is_module(adc_level, slow1, slow2, slow3):
        return adc_level == ADC_LOW and slow1 is LOW and slow3 is HIGH

    def __init__(self, frequency=DEFAULT_FREQUENCY):
        super().__init__()
        self.__frequency = frequency

        self.__last_fault = False
        self.__last_current = 0
        self.__last_temp = 0

    def setup(self, slot, adc1_func, adc2_func):
        super().setup(slot, adc1_func, adc2_func)

        # Create PWMOut objects
        self.__pwm_p = PWMOut(slot.FAST4, frequency=self.__frequency)
        self.__pwm_n = PWMOut(slot.FAST3, frequency=self.__frequency)

        # Create motor objects
        self.motor = DCMotor(self.__pwm_p, self.__pwm_n)

        self.__motor_en = DigitalInOut(slot.SLOW3)
        self.__motor_nfault = DigitalInOut(slot.SLOW2)

        self.reset()

    def reset(self):
        if self.slot is not None:
            self.motor.throttle = None

            self.__motor_nfault.switch_to_input()
            self.__motor_en.switch_to_output(False)

    def enable(self):
        self.__motor_en.value = True

    def disable(self):
        self.__motor_en.value = False

    def is_enabled(self):
        return self.__motor_en.value

    def read_fault(self):
        return not self.__motor_nfault.value

    def read_current(self):
        # This needs more validation
        return (abs(self.__read_adc1() - (3.3 / 2))) / (self.SHUNT_RESISTOR * self.GAIN)

    def read_temperature(self):
        return self.__read_adc2_as_temp()

    def monitor(self):
        fault = self.read_fault()
        if fault is True:
            raise RuntimeError(f"Fault detected on motor driver")

        current = self.read_current()
        if current > self.CURRENT_THRESHOLD:
            raise RuntimeError(f"Current of {current}A exceeded the user set level of {self.CURRENT_THRESHOLD}A")

        temp = self.read_temperature()
        if temp > self.TEMPERATURE_THRESHOLD:
            raise RuntimeError(f"Temperature of {temp}°C exceeded the user set level of {self.TEMPERATURE_THRESHOLD}°C")

        self.__last_fault = fault
        self.__last_current = current
        self.__last_temp = temp

        return None

    def last_monitored(self):
        return OrderedDict({
            "Fault": self.__last_fault,
            "C": self.__last_current,
            "T": self.__last_temp
        })
