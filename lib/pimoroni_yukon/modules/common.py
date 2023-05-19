# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

ADC_LOW = 0
ADC_HIGH = 1
ADC_FLOAT = 2
ADC_ANY = 3
LOW = False
HIGH = True


class YukonModule:
    NAME = "Unnamed"

    def __init__(self):
        self.slot = None
        self.read_adc1 = None
        self.read_adc2 = None
        pass

    def is_module(adc_level, slow1, slow2, slow3):
        return False

    def init(self, slot, adc1_func, adc2_func):
        self.slot = slot
        self.read_adc1 = adc1_func
        self.read_adc2 = adc2_func

    def monitor(self):
        return None
