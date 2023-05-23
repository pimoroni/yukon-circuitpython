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
        self.frequency = frequency

    def enable(self):
        self.p_en.value = True

    def disable(self):
        self.p_en.value = False

    def reset(self):
        self.motor.throttle = None

        self.nfault.switch_to_input()
        self.p_en.switch_to_output(False)

    def read_fault(self):
        return not self.nfault.value
    
    def read_current(self):
        # This needs more validation
        return (abs(self.__read_adc1() - (3.3 / 2))) / (self.SHUNT_RESISTOR * self.GAIN)

    def read_temperature(self):
        return self.__read_adc2_as_temp()

    def init(self, slot, adc1_func, adc2_func):
        super().init(slot, adc1_func, adc2_func)

        # Create PWMOut objects
        self.pwm_p = PWMOut(slot.FAST4, frequency=self.frequency)
        self.pwm_n = PWMOut(slot.FAST3, frequency=self.frequency)

        # Create motor objects
        self.motor = DCMotor(self.pwm_p, self.pwm_n)

        self.p_en = DigitalInOut(slot.SLOW3)
        self.nfault = DigitalInOut(slot.SLOW2)

        self.reset()

    def monitor(self):
        if self.read_fault():
            raise RuntimeError(f"Fault detected on motor driver")

        temp = self.read_temperature()
        if temp > self.TEMPERATURE_THRESHOLD:
            raise RuntimeError(f"Temperature of {temp}°C exceeded the user set level of {self.TEMPERATURE_THRESHOLD}°C")

        current = self.read_current()
        if current > 10:
            raise RuntimeError(f"Current of {current}A exceeded the user set level of 10A")

        return None
