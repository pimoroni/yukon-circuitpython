# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from .common import *

class BigMotorModule(YukonModule):
    NAME = "Big Motor + Encoder"

    def __init__(self):
        super().__init__()
        pass

    def is_module(adc_level, slow1, slow2, slow3):
        if adc_level == ADC_LOW and slow1 is LOW and slow2 is LOW and slow3 is HIGH:
            return True

        return False
