# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from .common import *


class AudioAmpModule(YukonModule):
    NAME = "Audio Amp"

    # | ADC1  | SLOW1 | SLOW2 | SLOW3 | Module               | Condition (if any)          |
    # |-------|-------|-------|-------|----------------------|-----------------------------|
    # | FLOAT | 0     | 1     | 1     | [Proposed] Audio Amp |                             |
    def is_module(adc_level, slow1, slow2, slow3):
        return adc_level == ADC_FLOAT and slow1 is LOW and slow2 is HIGH and slow3 is HIGH

    def __init__(self):
        super().__init__()
