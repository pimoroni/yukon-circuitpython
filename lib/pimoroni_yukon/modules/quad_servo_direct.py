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
        self.__initialised = False

    def setup(self, slot, adc1_func, adc2_func):
        super().setup(slot, adc1_func, adc2_func)

        # Create a PWMOut objects
        self.__pwms = [PWMOut(slot.FAST1, frequency=50),
                       PWMOut(slot.FAST2, frequency=50),
                       PWMOut(slot.FAST3, frequency=50),
                       PWMOut(slot.FAST4, frequency=50)]
        
        print(self.__pwms)

        # Create a servo objects
        self.servos = [Servo(self.__pwms[i]) for i in range(len(self.__pwms))]

        self.__initialised = True
        self.reset()

    def reset(self):
        if self.slot is not None and self.__initialised:
            for servo in self.servos:
                servo.angle = None

    def read_adc1(self):
        return self.__read_adc1()

    def read_adc2(self):
        return self.__read_adc2()
