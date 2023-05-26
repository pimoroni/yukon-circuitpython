# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from .common import *
from pwmio import PWMOut
from digitalio import DigitalInOut
from adafruit_motor.motor import DCMotor
from collections import OrderedDict


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
        self.__frequency = frequency

        self.__last_fault = False

    def initialise(self, slot, adc1_func, adc2_func):
        super().initialise(slot, adc1_func, adc2_func)

        # Create pwm objects
        self.__pwms_p = [PWMOut(slot.FAST2, frequency=self.__frequency),
                         PWMOut(slot.FAST4, frequency=self.__frequency)]
        self.__pwms_n = [PWMOut(slot.FAST1, frequency=self.__frequency),
                         PWMOut(slot.FAST3, frequency=self.__frequency)]

        # Create motor objects
        self.motors = [DCMotor(self.__pwms_p[i], self.__pwms_n[i]) for i in range(len(self.__pwms_p))]

        # Create motor control pin objects
        self.__motors_decay = DigitalInOut(slot.SLOW1)
        self.__motors_toff = DigitalInOut(slot.SLOW2)
        self.__motors_en = DigitalInOut(slot.SLOW3)

        # Configure motors
        self.configure()

        # Pass the slot and adc functions up to the parent now that module specific initialisation has finished
        super().initialise(slot, adc1_func, adc2_func)

    def configure(self):
        for motor in self.motors:
            motor.throttle = None

        self.__motors_decay.switch_to_output(False)
        self.__motors_toff.switch_to_output(False)
        self.__motors_en.switch_to_output(False)

    def enable(self):
        self.__motors_en.value = True

    def disable(self):
        self.__motors_en.value = False

    def is_enabled(self):
        return self.__motors_en.value

    def decay(self, value=None):
        if value is None:
            return self.__motors_decay
        else:
            self.__motors_decay = value

    def toff(self, value=None):
        if value is None:
            return self.__motors_toff
        else:
            self.__motors_toff = value

    def read_fault(self):
        return self.__read_adc1() <= self.FAULT_THRESHOLD

    def read_temperature(self):
        return self.__read_adc2_as_temp()

    def monitor(self, debug_level=0):
        fault = self.read_fault()
        if fault is True:
            raise RuntimeError(f"Fault detected on motor driver")

        temperature = self.read_temperature()
        if temperature > self.TEMPERATURE_THRESHOLD:
            raise RuntimeError(f"Temperature of {temperature}°C exceeded the user set level of {self.TEMPERATURE_THRESHOLD}°C")

        self.__last_fault = fault

        self.__max_temperature = max(temperature, self.__max_temperature)
        self.__min_temperature = min(temperature, self.__min_temperature)
        self.__avg_temperature += temperature
        self.__count_avg += 1

        return None

    def get_readings(self):
        return OrderedDict({
            "Fault": self.__last_fault,
            "T_max": self.__max_temperature,
            "T_min": self.__min_temperature,
            "T_avg": self.__avg_temperature,
        })

    def process_readings(self):
        if self.__count_avg > 0:
            self.__avg_temperature /= self.__count_avg

    def clear_readings(self):
        self.__max_temperature = float('-inf')
        self.__min_temperature = float('inf')
        self.__avg_temperature = 0
        self.__count_avg = 0