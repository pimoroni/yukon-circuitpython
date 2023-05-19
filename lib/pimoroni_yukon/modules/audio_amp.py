# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from .common import *

class AudioAmpModule(YukonModule):
    NAME = "Audio Amp"

    def __init__(self):
        super().__init__()
        pass

    def is_module(adc_level, slow1, slow2, slow3):
        if adc_level == ADC_FLOAT and slow1 is HIGH and slow2 is HIGH and slow3 is HIGH:
            # pretend to do some I2C comms here
            return False

        return False
