# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from digitalio import DigitalInOut
from pwmio import PWMOut
from .common import *

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

    def __init__(self):
        super().__init__()
        pass

    def is_module(adc_level, slow1, slow2, slow3):
        # May not be able to rely on the ADC level being low to detect this module
        if adc_level == ADC_LOW and slow1 is HIGH and slow2 is LOW and slow3 is LOW:
            return True

        return False

    def enable(self):
        self.p_en.value = True

    def disable(self):
        self.p_en.value = False
            
    def set_pwm(self, percent):
        if percent < 0 or percent > 1.0:
            raise ValueError("percent out of range. Expected 0.0 to 1.0")

        self.voltage_pwm.duty_cycle = int(((2 ** 16) - 1) * percent)
        
    def read_voltage(self):
        # return (self.__shared_adc_voltage() * (100 + 22)) / 22
        voltage = self.read_adc1(self.slot)
        if voltage >= self.VOLTAGE_MID_MEASURE:
            return ((voltage - self.VOLTAGE_MID_MEASURE) * (self.VOLTAGE_MAX - self.VOLTAGE_MID)) / (self.VOLTAGE_MAX_MEASURE - self.VOLTAGE_MID_MEASURE) + self.VOLTAGE_MID
        else:
            return max(((voltage - self.VOLTAGE_MIN_MEASURE) * (self.VOLTAGE_MID - self.VOLTAGE_MIN)) / (self.VOLTAGE_MID_MEASURE - self.VOLTAGE_MIN_MEASURE) + self.VOLTAGE_MIN, 0.0)

    def set_target_voltage(self, voltage):
        if voltage >= self.VOLTAGE_MID:
            percent = min((voltage - self.VOLTAGE_MID) * 0.5 / (self.VOLTAGE_MAX - self.VOLTAGE_MID) + 0.5, 1.0)
        else:
            percent = max((voltage - self.VOLTAGE_MIN) * 0.5 / (self.VOLTAGE_MID - self.VOLTAGE_MIN), 0.0)
        self.set_target(percent)
        
    def set_target(self, percent):
        if percent < 0 or percent > 1.0:
            raise ValueError("percent out of range. Expected 0.0 to 1.0")

        duty = (percent * (self.PWM_MAX - self.PWM_MIN)) + self.PWM_MIN
        self.voltage_pwm.duty_cycle = int(((2 ** 16) - 1) * duty)
        
    def reset(self):
        if self.slot is not None:
            self.voltage_pwm.duty_cycle = 0
            self.p_en.switch_to_output(False)
            self.p_good.switch_to_input()

    def init(self, slot, adc1_func, adc2_func):
        super().init(slot, adc1_func, adc2_func)

        self.voltage_pwm = PWMOut(slot.FAST2, duty_cycle=0, frequency=250000)

        self.p_en = DigitalInOut(slot.FAST1)
        self.p_good = DigitalInOut(slot.SLOW1)

        self.reset()
