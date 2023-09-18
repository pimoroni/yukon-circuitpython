# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from .common import YukonModule, ADC_HIGH, LOW, HIGH
from pwmio import PWMOut
from digitalio import DigitalInOut
from collections import OrderedDict
from pimoroni_yukon.errors import FaultError, OverTemperatureError
import pimoroni_yukon.logging as logging

# The current (in amps) associated with each limit (Do Not Modify!)
CURRENT_LIMIT_1 = 0.161
CURRENT_LIMIT_2 = 0.251
CURRENT_LIMIT_3 = 0.444
CURRENT_LIMIT_4 = 0.786
CURRENT_LIMIT_5 = 1.143
CURRENT_LIMIT_6 = 1.611
CURRENT_LIMIT_7 = 1.890
CURRENT_LIMIT_8 = 2.153
CURRENT_LIMIT_9 = 2.236


class DualMotorModule(YukonModule):
    NAME = "Dual Motor"
    DUAL = 0
    STEPPER = 1
    NUM_MOTORS = 2
    NUM_STEPPERS = 1
    FAULT_THRESHOLD = 0.1
    DEFAULT_FREQUENCY = 25000
    DEFAULT_CURRENT_LIMIT = CURRENT_LIMIT_3
    TEMPERATURE_THRESHOLD = 50.0

    # | ADC1  | SLOW1 | SLOW2 | SLOW3 | Module               | Condition (if any)          |
    # |-------|-------|-------|-------|----------------------|-----------------------------|
    # | HIGH  | 0     | 0     | 1     | Dual Motor           |                             |
    @staticmethod
    def is_module(adc_level, slow1, slow2, slow3):
        return adc_level == ADC_HIGH and slow1 is LOW and slow2 is LOW and slow3 is HIGH

    def __init__(self, motor_type=DUAL, frequency=DEFAULT_FREQUENCY, current_limit=DEFAULT_CURRENT_LIMIT):
        super().__init__()
        self.__motor_type = motor_type
        if self.__motor_type == self.STEPPER:
            self.NAME += " (Stepper)"

        self.__frequency = frequency
        self.__current_limit = current_limit

        # An ascending order list of current limits with the pin states to achieve them
        self.__current_limit_states = OrderedDict({
            CURRENT_LIMIT_1: (0, 0),
            CURRENT_LIMIT_2: (-1, 0),
            CURRENT_LIMIT_3: (0, -1),
            CURRENT_LIMIT_4: (1, 0),
            CURRENT_LIMIT_5: (-1, -1),
            CURRENT_LIMIT_6: (0, 1),
            CURRENT_LIMIT_7: (1, -1),
            CURRENT_LIMIT_8: (-1, 1),
            CURRENT_LIMIT_9: (1, 1),
        })

    def initialise(self, slot, adc1_func, adc2_func):
        try:
            # Create pwm objects
            self.__pwms_p = [PWMOut(slot.FAST2, frequency=self.__frequency),
                             PWMOut(slot.FAST4, frequency=self.__frequency)]
            self.__pwms_n = [PWMOut(slot.FAST1, frequency=self.__frequency),
                             PWMOut(slot.FAST3, frequency=self.__frequency)]
        except ValueError as e:
            if slot.ID <= 2 or slot.ID >= 5:
                conflicting_slot = (((slot.ID - 1) + 4) % 8) + 1
                raise type(e)(f"PWM channel(s) already in use. Check that the module in Slot{conflicting_slot} does not share the same PWM channel(s)") from None
            raise type(e)("PWM channel(s) already in use. Check that a module in another slot does not share the same PWM channel(s)") from None

        if self.__motor_type == self.DUAL:
            from adafruit_motor.motor import DCMotor

            # Create motor objects
            self.motors = [DCMotor(self.__pwms_p[i], self.__pwms_n[i]) for i in range(len(self.__pwms_p))]
        else:
            from adafruit_motor.stepper import StepperMotor

            self.stepper = StepperMotor(self.__pwms_p[0], self.__pwms_n[0], self.__pwms_p[1], self.__pwms_n[1])

        # Create motor control pin objects
        self.__motors_en = DigitalInOut(slot.SLOW3)
        self.__motors_vref1 = DigitalInOut(slot.SLOW1)
        self.__motors_vref2 = DigitalInOut(slot.SLOW2)

        # Pass the slot and adc functions up to the parent now that module specific initialisation has finished
        super().initialise(slot, adc1_func, adc2_func)

    def reset(self):
        if self.__motor_type == self.DUAL:
            for motor in self.motors:
                motor.throttle = None
        else:
            self.stepper.release()

        self.__motors_en.switch_to_output(False)
        self.current_limit(self.__current_limit)

    def enable(self):
        self.__motors_en.value = True

    def disable(self):
        self.__motors_en.value = False

    def is_enabled(self):
        return self.__motors_en.value

    def current_limit(self, amps):
        if amps is None:
            return self.__current_limit
        else:
            if self.is_enabled():
                raise RuntimeError("Cannot change current limit whilst motor driver is active")

            # Start with the lowest limit
            chosen_limit = CURRENT_LIMIT_1
            chosen_state = self.__current_limit_states[CURRENT_LIMIT_1]

            # Find the closest current limit below the given amps value
            for limit, state in self.__current_limit_states.items():
                if limit < amps:
                    break
                chosen_limit = limit
                chosen_state = state

            if chosen_state[0] is -1:
                self.__motors_vref1.switch_to_input()
            elif chosen_state[0] is 0:
                self.__motors_vref1.switch_to_output(False)
            else:
                self.__motors_vref1.switch_to_output(True)

            if chosen_state[1] is -1:
                self.__motors_vref2.switch_to_input()
            elif chosen_state[1] is 0:
                self.__motors_vref2.switch_to_output(False)
            else:
                self.__motors_vref2.switch_to_output(True)

            self.__current_limit = chosen_limit

            logging.info(self.__message_header() + f"Current limit set to {self.__current_limit}A")

    @property
    def motor1(self):
        return self.motors[0]

    @property
    def motor2(self):
        return self.motors[1]

    def read_fault(self):
        return self.__read_adc1() <= self.FAULT_THRESHOLD

    def read_temperature(self):
        return self.__read_adc2_as_temp()

    def monitor(self):
        fault = self.read_fault()
        if fault is True:
            raise FaultError(self.__message_header() + "Fault detected on motor driver! Turning off output")

        temperature = self.read_temperature()
        if temperature > self.TEMPERATURE_THRESHOLD:
            raise OverTemperatureError(self.__message_header() + f"Temperature of {temperature}°C exceeded the limit of {self.TEMPERATURE_THRESHOLD}°C! Turning off output")

        # Run some user action based on the latest readings
        if self.__monitor_action_callback is not None:
            self.__monitor_action_callback(fault, temperature)

        self.__fault_triggered = self.__fault_triggered or fault
        self.__max_temperature = max(temperature, self.__max_temperature)
        self.__min_temperature = min(temperature, self.__min_temperature)
        self.__avg_temperature += temperature
        self.__count_avg += 1

    def get_readings(self):
        return OrderedDict({
            "Fault": self.__fault_triggered,
            "T_max": self.__max_temperature,
            "T_min": self.__min_temperature,
            "T_avg": self.__avg_temperature,
        })

    def process_readings(self):
        if self.__count_avg > 0:
            self.__avg_temperature /= self.__count_avg

    def clear_readings(self):
        self.__fault_triggered = False
        self.__max_temperature = float('-inf')
        self.__min_temperature = float('inf')
        self.__avg_temperature = 0
        self.__count_avg = 0
