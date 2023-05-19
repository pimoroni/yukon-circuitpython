# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from .common import *

class ProtoPotModule(YukonModule):
    NAME = "Proto Potentiometer"

    def __init__(self):
        super().__init__()
        pass

    def is_module(adc_level, slow1, slow2, slow3):
        if slow1 is HIGH and slow2 is HIGH and slow3 is LOW:
            return True

        return False

    def read(self):
        if self.slot is not None and self.read_adc1 is not None:
            return self.read_adc1(self.slot) / 3.3
        return 0.0
