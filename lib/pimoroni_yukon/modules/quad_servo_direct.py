# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from .common import *

class QuadServoDirectModule(YukonModule):
    NAME = "Quad Servo Direct"
    NUM_SERVOS = 4

    def __init__(self):
        super().__init__()

    def is_module(adc_level, slow1, slow2, slow3):
        # ADC is wired to a user pin, so all 3 states are valid
        if slow1 is LOW and slow2 is LOW and slow3 is HIGH: # Old address 001, will be changed to 000
            return True

        return False

    def reset(self):
        for servo in self.servos:
           servo.angle = None

    def init(self, slot, adc1_func, adc2_func):
        super().init(slot, adc1_func, adc2_func)

        from pwmio import PWMOut
        from adafruit_motor.servo import Servo

        # Create a PWMOut objects
        self.pwms = [PWMOut(slot.FAST1, frequency=50),
                     PWMOut(slot.FAST2, frequency=50),
                     PWMOut(slot.FAST3, frequency=50),
                     PWMOut(slot.FAST4, frequency=50)]

        # Create a servo objects
        self.servos = [Servo(self.pwms[i]) for i in range(len(self.pwms))]

        self.reset()
