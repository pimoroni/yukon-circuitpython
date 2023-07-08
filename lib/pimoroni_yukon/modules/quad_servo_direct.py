# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from .common import *
from pwmio import PWMOut
from adafruit_motor.servo import Servo


class QuadServoDirectModule(YukonModule):
    NAME = "Quad Servo Direct"
    NUM_SERVOS = 4

    # | ADC1  | SLOW1 | SLOW2 | SLOW3 | Module               | Condition (if any)          |
    # |-------|-------|-------|-------|----------------------|-----------------------------|
    # | LOW   | 0     | 0     | 0     | Quad Servo Direct    | A1 input near 0V            |
    # | FLOAT | 0     | 0     | 0     | Quad Servo Direct    | A1 input between 0 and 3.3V |
    # | HIGH  | 0     | 0     | 0     | Quad Servo Direct    | A1 input near 3.3V          |
    def is_module(adc_level, slow1, slow2, slow3):
        # Current protos need Slow3 jumpered to GND
        return slow1 is LOW and slow2 is LOW and slow3 is LOW

    def __init__(self):
        super().__init__()

    def initialise(self, slot, adc1_func, adc2_func):
        # Create pwm objects
        self.__pwms = [PWMOut(slot.FAST1, frequency=50),
                       PWMOut(slot.FAST2, frequency=50),
                       PWMOut(slot.FAST3, frequency=50),
                       PWMOut(slot.FAST4, frequency=50)]

        # Create servo objects
        self.servos = [Servo(self.__pwms[i]) for i in range(len(self.__pwms))]

        # Configure servos
        self.configure()

        # Pass the slot and adc functions up to the parent now that module specific initialisation has finished
        super().initialise(slot, adc1_func, adc2_func)

    def configure(self):
        for servo in self.servos:
            servo.angle = None

    @property
    def servo1(self):
        return self.servos[0]

    @property
    def servo2(self):
        return self.servos[1]

    @property
    def servo3(self):
        return self.servos[2]

    @property
    def servo4(self):
        return self.servos[3]

    def read_adc1(self):
        return self.__read_adc1()

    def read_adc2(self):
        return self.__read_adc2()
