# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

import digitalio
import pwmio

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
        self.adc1_func = None
        pass

    def is_module(adc_level, slow1, slow2, slow3):
        return False

    def init(self, slot, adc1_func):
        self.slot = slot
        self.adc1_func = adc1_func


class LEDStripModule(YukonModule):
    NAME = "LED Strip"
    NEOPIXEL = 0
    DOTSTAR = 1

    def __init__(self, strip_type, num_pixels, brightness=1.0):
        super().__init__()
        self.strip_type = strip_type
        if self.strip_type == self.NEOPIXEL:
            self.NAME += " [NeoPixel]"
        else:
            self.NAME += " [DotStar]"

        self.num_pixels = num_pixels
        self.brightness = brightness

    def is_module(adc_level, slow1, slow2, slow3):
        if adc_level == ADC_LOW and slow1 is HIGH and slow2 is HIGH and slow3 is HIGH:
            return True

        return False

    def enable(self):
        self.p_en.value = True

    def disable(self):
        self.p_en.value = False

    def reset(self):
        self.p_good.direction = digitalio.Direction.INPUT
        self.p_en.direction = digitalio.Direction.OUTPUT
        self.p_en.value = False

    def init(self, slot, adc1_func):
        super().init(slot, adc1_func)

        if self.strip_type == self.NEOPIXEL:
            import neopixel
            self.pixels = neopixel.NeoPixel(slot.FAST4, self.num_pixels, brightness=self.brightness, auto_write=False)
        else:
            import adafruit_dotstar
            self.pixels = adafruit_dotstar.DotStar(slot.FAST3, slot.FAST4, self.num_pixels, brightness=self.brightness, auto_write=False)

        self.p_good = digitalio.DigitalInOut(slot.FAST1)
        self.p_en = digitalio.DigitalInOut(slot.FAST2)

        self.reset()


class QuadServoDirectModule(YukonModule):
    NAME = "Quad Servo Direct"

    def __init__(self):
        super().__init__()
        pass

    def is_module(adc_level, slow1, slow2, slow3):
        if slow1 is LOW and slow2 is LOW and slow3 is LOW:
            return True

        return False


class QuadServoRegModule(YukonModule):
    NAME = "Quad Servo Regulated"

    def __init__(self):
        super().__init__()
        pass

    def is_module(adc_level, slow1, slow2, slow3):
        if adc_level == ADC_FLOAT and slow1 is LOW and slow2 is HIGH and slow3 is LOW:
            return True
        return False


class BigMotorModule(YukonModule):
    NAME = "Big Motor + Encoder"

    def __init__(self):
        super().__init__()
        pass

    def is_module(adc_level, slow1, slow2, slow3):
        if adc_level == ADC_LOW and slow1 is LOW and slow2 is LOW and slow3 is HIGH:
            return True

        return False


class BenchPowerModule(YukonModule):
    NAME = "Bench Power"
    
    VOLTAGE_MAX = 12.3953
    VOLTAGE_MID = 6.5052
    VOLTAGE_MIN = 0.6713
    VOLTAGE_MIN_MEASURE = 0.1477
    VOLTAGE_MID_MEASURE = 1.1706
    VOLTAGE_MAX_MEASURE = 2.2007
    PWM_MIN = 0.3
    PWM_MAX = 0.0

    def __init__(self):
        super().__init__()
        pass

    def is_module(adc_level, slow1, slow2, slow3):
        # May not be able to rely on the ADC level being low to detect this module
        if adc_level == ADC_LOW and slow1 is HIGH and slow2 is LOW and slow3 is LOW:
            return True

        return False

    def enable(self):
        self.p_en.value = True

    def disable(self):
        self.p_en.value = False
            
    def set_pwm(self, percent):
        if percent < 0 or percent > 1.0:
            raise ValueError("percent out of range. Expected 0.0 to 1.0")

        self.voltage_pwm.duty_cycle = int(((2 ** 16) - 1) * percent)
        
    def read_voltage(self):
        # return (self.__shared_adc_voltage() * (100 + 22)) / 22
        voltage = self.adc1_func(self.slot)
        if voltage >= self.VOLTAGE_MID_MEASURE:
            return ((voltage - self.VOLTAGE_MID_MEASURE) * (self.VOLTAGE_MAX - self.VOLTAGE_MID)) / (self.VOLTAGE_MAX_MEASURE - self.VOLTAGE_MID_MEASURE) + self.VOLTAGE_MID
        else:
            return max(((voltage - self.VOLTAGE_MIN_MEASURE) * (self.VOLTAGE_MID - self.VOLTAGE_MIN)) / (self.VOLTAGE_MID_MEASURE - self.VOLTAGE_MIN_MEASURE) + self.VOLTAGE_MIN, 0.0)

    def set_target_voltage(self, voltage):
        if voltage >= self.VOLTAGE_MID:
            percent = min((voltage - self.VOLTAGE_MID) * 0.5 / (self.VOLTAGE_MAX - self.VOLTAGE_MID) + 0.5, 1.0)
        else:
            percent = max((voltage - self.VOLTAGE_MIN) * 0.5 / (self.VOLTAGE_MID - self.VOLTAGE_MIN), 0.0)
        self.set_target(percent)
        
    def set_target(self, percent):
        if percent < 0 or percent > 1.0:
            raise ValueError("percent out of range. Expected 0.0 to 1.0")

        duty = (percent * (self.PWM_MAX - self.PWM_MIN)) + self.PWM_MIN
        self.voltage_pwm.duty_cycle = int(((2 ** 16) - 1) * duty)
        
    def reset(self):
        if self.slot is not None:
            self.voltage_pwm.duty_cycle = 0

            self.p_en.switch_to_output(False)

            self.p_good.switch_to_input()

    def init(self, slot, adc1_func):
        super().init(slot, adc1_func)

        self.voltage_pwm = pwmio.PWMOut(slot.FAST2, duty_cycle=0, frequency=250000)

        self.p_en = digitalio.DigitalInOut(slot.FAST1)

        self.p_good = digitalio.DigitalInOut(slot.SLOW1)

        self.reset()


class DualSwitchedModule(YukonModule):
    NAME = "Dual Switched Output"
    NUM_SWITCHES = 2

    def __init__(self):
        super().__init__()
        pass

    def is_module(adc_level, slow1, slow2, slow3):
        if adc_level == ADC_FLOAT and slow1 is HIGH and slow2 is LOW and slow3 is HIGH:
            return True

        return False
    
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

    def init(self, slot, adc1_func):
        super().init(slot, adc1_func)

        self.output_pins = (digitalio.DigitalInOut(slot.FAST1),
                            digitalio.DigitalInOut(slot.FAST3))

        self.n_shutdown = (digitalio.DigitalInOut(slot.FAST2),
                       digitalio.DigitalInOut(slot.FAST4))

        self.p_good = (digitalio.DigitalInOut(slot.SLOW1),
                       digitalio.DigitalInOut(slot.SLOW3))

        self.reset()


class DualMotorModule(YukonModule):
    NAME = "Dual Motor / Stepper"

    def __init__(self):
        super().__init__()
        pass

    def is_module(adc_level, slow1, slow2, slow3):
        if adc_level == ADC_HIGH and slow1 is HIGH and slow2 is HIGH and slow3 is HIGH:
            return True

        return False


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
        if self.slot is not None and self.adc1_func is not None:
            return self.adc1_func(self.slot) / 3.3
        return 0.0


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


KNOWN_MODULES = (
    LEDStripModule,
    QuadServoDirectModule,
    QuadServoRegModule,
    BigMotorModule,
    DualMotorModule,
    DualSwitchedModule,
    BenchPowerModule,
    ProtoPotModule,
    AudioAmpModule)
