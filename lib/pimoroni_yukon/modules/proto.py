# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from .common import YukonModule, LOW, HIGH


class ProtoPotModule(YukonModule):
    NAME = "Proto Potentiometer"

    # | ADC1  | SLOW1 | SLOW2 | SLOW3 | Module               | Condition (if any)          |
    # |-------|-------|-------|-------|----------------------|-----------------------------|
    # | LOW   | 1     | 1     | 0     | Proto Potentiometer  | Pot in low position         |
    # | FLOAT | 1     | 1     | 0     | Proto Potentiometer  | Pot in middle position      |
    # | HIGH  | 1     | 1     | 0     | Proto Potentiometer  | Pot in high position        |
    @staticmethod
    def is_module(adc_level, slow1, slow2, slow3):
        return slow1 is HIGH and slow2 is HIGH and slow3 is LOW

    def __init__(self):
        super().__init__()
        pass

    def read(self):
        return self.__read_adc1() / 3.3


class ProtoPotModule2(YukonModule):
    NAME = "Proto Potentiometer 2"
    PULLUP = 5100

    # | ADC1  | SLOW1 | SLOW2 | SLOW3 | Module               | Condition (if any)          |
    # |-------|-------|-------|-------|----------------------|-----------------------------|
    # | LOW   | 1     | 1     | 0     | Proto Potentiometer  | Pot in low position         |
    # | FLOAT | 1     | 1     | 0     | Proto Potentiometer  | Pot in middle position      |
    # | HIGH  | 1     | 1     | 0     | Proto Potentiometer  | Pot in high position        |
    @staticmethod
    def is_module(adc_level, slow1, slow2, slow3):
        return slow1 is HIGH and slow2 is HIGH and slow3 is LOW

    # ADC2 has a pull-up connected to simplify its use with modules that feature an onboard thermistor.
    # Unfortunately, when connecting up a potentiometer, creating the below circuit, this has the
    # effect of making the output non-linear.
    #
    # Vin ---------------
    #           |       |
    #          | |     | |
    #       rt | |     | | rp
    #          | |     | |
    #           |       |
    #           --------------- Vout
    #           |
    #          | |
    #       rb | |
    #          | |
    #           |
    # Gnd -------
    #
    # Where rt is the top section of the potentiometer, rb is the bottom
    # section of the potentiometer, and rp is the onboard pull-up. Also,
    # The full resistance of the pot, R = rt + rb
    #
    # Below is the equation for calculating the output given a normalised input (e.g. 1V)
    #
    # o =                 rb
    #     ---------------------------------
    #      /             1               \
    #      | ---------------------- + rb |
    #      |  /    1   \   /  1  \       |
    #      |  | ------ | + | --- |       |
    #      \  \ R - rb /   \  rp /       /
    #
    # We want to calculate the inverse of this though... which is this magic equation:
    # https://www.symbolab.com/solver/equation-calculator/o%20%3D%20r%20%2F%20%5Cleft(%201%2F%20%5Cleft(1%2F%5Cleft(10000-r%5Cright)%2B1%2F5100%5Cright)%20%2B%20r%5Cright)?or=input
    # where r is rb, and R and rp are set to 10k and 5.1k, respectively.
    #
    # This can be simplified by normalising the resistor values, by R, giving:
    # https://www.symbolab.com/solver/equation-calculator/o%20%3D%20r%20%2F%20%5Cleft(%201%2F%20%5Cleft(1%2F%5Cleft(1-r%5Cright)%2B1%2F0.51%5Cright)%20%2B%20r%5Cright)?or=input
    def __init__(self, pot_resistance):
        super().__init__()

        # Normalise the pull-up resistance
        pu = self.PULLUP / pot_resistance

        # Pre-calculate values that are independent of the adc reading
        self.sum = pu + 1
        self.const_a = (4 * pu) + 1
        self.const_b = (6 * pu) + 2
        self.const_c = (pu ** 2) + (2 * pu) + 1

    def read(self):
        from math import sqrt
        out = self.__read_adc2() / 3.3
        return (-out + self.sum - sqrt((self.const_a * (out ** 2)) - (self.const_b * out) + self.const_c)) / (2 * (-out + 1))
