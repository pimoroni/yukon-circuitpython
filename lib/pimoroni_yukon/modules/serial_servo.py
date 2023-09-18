# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from .common import YukonModule, ADC_FLOAT, LOW, HIGH


class SerialServoModule(YukonModule):
    NAME = "Serial Bus Servo"
    NUM_SERVOS = 4

    # | ADC1  | SLOW1 | SLOW2 | SLOW3 | Module               | Condition (if any)          |
    # |-------|-------|-------|-------|----------------------|-----------------------------|
    # | FLOAT | 1     | 0     | 0     | Serial Servo         |                             |
    @staticmethod
    def is_module(adc_level, slow1, slow2, slow3):
        return adc_level is ADC_FLOAT and slow1 is HIGH and slow2 is LOW and slow3 is LOW

    def __init__(self):
        super().__init__()

    def initialise(self, slot, adc1_func, adc2_func):
        # TODO implement half-duplex UART here

        # Pass the slot and adc functions up to the parent now that module specific initialisation has finished
        super().initialise(slot, adc1_func, adc2_func)

    def reset(self):
        pass
