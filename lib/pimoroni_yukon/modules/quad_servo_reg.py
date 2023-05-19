# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from digitalio import DigitalInOut
from .common import *

class QuadServoRegModule(YukonModule):
    NAME = "Quad Servo Regulated"
    NUM_SERVOS = 4

    def __init__(self):
        super().__init__()
        pass

    def is_module(adc_level, slow1, slow2, slow3):
        if adc_level == ADC_FLOAT and slow1 is LOW and slow2 is HIGH and slow3 is LOW:
            return True
        return False

    def enable(self):
        self.p_en.value = True

    def disable(self):
        self.p_en.value = False

    def power_good(self):
        return self.p_good.value

    def reset(self):
        for servo in self.servos:
           servo.angle = None

        self.p_en.switch_to_output(False)
        self.p_good.switch_to_input()

    def init(self, slot, adc1_func, adc2_func):
        super().init(slot, adc1_func, adc2_func)

        from pwmio import PWMOut
        from adafruit_motor.servo import Servo

        # Create PWMOut objects
        self.pwms = [PWMOut(slot.FAST1, frequency=50),
                     PWMOut(slot.FAST2, frequency=50),
                     PWMOut(slot.FAST3, frequency=50),
                     PWMOut(slot.FAST4, frequency=50)]

        # Create servo objects
        self.servos = [Servo(self.pwms[i]) for i in range(len(self.pwms))]

        self.p_en = DigitalInOut(slot.SLOW1)
        self.p_good = DigitalInOut(slot.SLOW2)

        self.reset()
