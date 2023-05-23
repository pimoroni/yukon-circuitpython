# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from .common import *
from digitalio import DigitalInOut
from pwmio import PWMOut
from adafruit_motor.motor import DCMotor


class DualMotorModule(YukonModule):
    NAME = "Dual Motor"
    NUM_MOTORS = 2
    FAULT_THRESHOLD = 0.1
    DEFAULT_FREQUENCY = 25000
    TEMPERATURE_THRESHOLD = 50.0

    # | ADC1  | SLOW1 | SLOW2 | SLOW3 | Module               | Condition (if any)          |
    # |-------|-------|-------|-------|----------------------|-----------------------------|
    # | HIGH  | 1     | 1     | 1     | Dual Motor           |                             |
    def is_module(adc_level, slow1, slow2, slow3):
        return adc_level == ADC_HIGH and slow1 is HIGH and slow2 is HIGH and slow3 is HIGH

    def __init__(self, frequency=DEFAULT_FREQUENCY):
        super().__init__()
        self.frequency = frequency

    def enable(self):
        self.p_en.value = True

    def disable(self):
        self.p_en.value = False

    def reset(self):
        for motor in self.motors:
           motor.throttle = None

        self.p_decay.switch_to_output(False)
        self.p_toff.switch_to_output(False)
        self.p_en.switch_to_output(False)

    def read_fault(self):
        return self.__read_adc1() <= self.FAULT_THRESHOLD

    def read_temperature(self):
        return self.__read_adc2()

    def init(self, slot, adc1_func, adc2_func):
        super().init(slot, adc1_func, adc2_func)

        # Create PWMOut objects
        self.pwms_p = [PWMOut(slot.FAST2, frequency=self.frequency),
                       PWMOut(slot.FAST4, frequency=self.frequency)]
        self.pwms_n = [PWMOut(slot.FAST1, frequency=self.frequency),
                       PWMOut(slot.FAST3, frequency=self.frequency)]

        # Create motor objects
        self.motors = [DCMotor(self.pwms_p[i], self.pwms_n[i]) for i in range(len(self.pwms_p))]

        self.p_decay = DigitalInOut(slot.SLOW1)
        self.p_toff = DigitalInOut(slot.SLOW2)
        self.p_en = DigitalInOut(slot.SLOW3)

        self.reset()

    def monitor(self):
        if self.read_fault():
            raise RuntimeError(f"Fault detected on motor driver")

        temp = self.read_temperature()
        if temp > self.TEMPERATURE_THRESHOLD:
            raise RuntimeError(f"Temperature of {temp}°C exceeded the user set level of {self.TEMPERATURE_THRESHOLD}°C")

        return None
