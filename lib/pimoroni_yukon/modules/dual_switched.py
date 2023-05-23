# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from digitalio import DigitalInOut
from .common import *

class DualSwitchedModule(YukonModule):
    NAME = "Dual Switched Output"
    NUM_SWITCHES = 2

    # | ADC1  | SLOW1 | SLOW2 | SLOW3 | Module               | Condition (if any)          |
    # |-------|-------|-------|-------|----------------------|-----------------------------|
    # | FLOAT | 1     | 0     | 1     | Dual Switched Output |                             |
    def is_module(adc_level, slow1, slow2, slow3):
        return adc_level == ADC_FLOAT and slow1 is HIGH and slow2 is LOW and slow3 is HIGH

    def __init__(self):
        super().__init__()
        pass

    def enable(self, switch=None):
        if switch is not None:
            if switch < 1 or switch > self.NUM_SWITCHES:
                raise ValueError("switch index out of range. Expected 1 to 2")

            self.n_shutdown[switch - 1].value = True
        else:
            self.n_shutdown[0].value = True
            self.n_shutdown[1].value = True

    def disable(self, switch=None):
        if switch is not None:
            if switch < 1 or switch > self.NUM_SWITCHES:
                raise ValueError("switch index out of range. Expected 1 to 2")

            self.n_shutdown[switch - 1].value = False
        else:
            self.n_shutdown[0].value = False
            self.n_shutdown[1].value = False

    def output(self, switch, value):
        if switch < 1 or switch > self.NUM_SWITCHES:
            raise ValueError("switch index out of range. Expected 1 to 2")

        self.output_pins[switch - 1].value = value

    def read_output(self, switch):
        if switch < 1 or switch > self.NUM_SWITCHES:
            raise ValueError("switch index out of range. Expected 1 to 2")

        return self.output_pins[switch - 1].value

    def reset(self):
        self.output_pins[0].switch_to_output(False)
        self.output_pins[1].switch_to_output(False)

        self.n_shutdown[0].switch_to_output(False)
        self.n_shutdown[1].switch_to_output(False)

        self.p_good[0].switch_to_input()
        self.p_good[1].switch_to_input()

    def init(self, slot, adc1_func, adc2_func):
        super().init(slot, adc1_func, adc2_func)

        self.output_pins = (DigitalInOut(slot.FAST1),
                            DigitalInOut(slot.FAST3))

        self.n_shutdown = (DigitalInOut(slot.FAST2),
                       DigitalInOut(slot.FAST4))

        self.p_good = (DigitalInOut(slot.SLOW1),
                       DigitalInOut(slot.SLOW3))

        self.reset()
