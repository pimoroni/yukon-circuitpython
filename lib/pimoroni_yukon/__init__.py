# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

import time
import board
import digitalio
import analogio
import tca

from pimoroni_yukon.modules import KNOWN_MODULES
from pimoroni_yukon.modules.common import ADC_FLOAT, ADC_LOW, ADC_HIGH, YukonModule
import pimoroni_yukon.logging as logging
from pimoroni_yukon.errors import OverVoltageError, UnderVoltageError, OverCurrentError, OverTemperatureError, FaultError, VerificationError
from pimoroni_yukon.timing import ticks_ms, ticks_add, ticks_diff, TICKS_PERIOD
from pimoroni_yukon.conversion import u16_to_voltage_in, u16_to_voltage_out, u16_to_current, analog_to_temp
from collections import OrderedDict


class Yukon:
    """Yukon class."""
    SWITCH_A = 0
    SWITCH_B = 1
    SWITCH_A_NAME = 'A'
    SWITCH_B_NAME = 'B'
    SWITCH_USER = 2
    NUM_SLOTS = 6

    DEFAULT_VOLTAGE_LIMIT = 17.2
    VOLTAGE_LOWER_LIMIT = 4.8
    VOLTAGE_ZERO_LEVEL = 0.05
    VOLTAGE_SHORT_LEVEL = 0.5
    DEFAULT_CURRENT_LIMIT = 20
    DEFAULT_TEMPERATURE_LIMIT = 80
    ABSOLUTE_MAX_VOLTAGE_LIMIT = 18

    DETECTION_SAMPLES = 64
    DETECTION_ADC_LOW = 0.2
    DETECTION_ADC_HIGH = 3.2

    OUTPUT_STABLISE_TIMEOUT_NS = 200 * 1000 * 1000
    OUTPUT_STABLISE_TIME_NS = 10 * 1000 * 1000
    OUTPUT_STABLISE_V_DIFF = 0.1

    OUTPUT_DISSIPATE_TIMEOUT_S = 15  # When a bench power module is attached and there is no additional output load, it can take a while for it to return to an idle state
    OUTPUT_DISSIPATE_TIMEOUT_NS = OUTPUT_DISSIPATE_TIMEOUT_S * 1000 * 1000 * 1000
    OUTPUT_DISSIPATE_LEVEL = 0.4  # The voltage below which we can reliably obtain the address of attached modules

    def __init__(self, voltage_limit=DEFAULT_VOLTAGE_LIMIT, current_limit=DEFAULT_CURRENT_LIMIT, temperature_limit=DEFAULT_TEMPERATURE_LIMIT, logging_level=logging.LOG_INFO):
        self.__voltage_limit = min(voltage_limit, self.ABSOLUTE_MAX_VOLTAGE_LIMIT)
        self.__current_limit = current_limit
        self.__temperature_limit = temperature_limit
        logging.level = logging_level

        self.__slot_assignments = OrderedDict({
            board.SLOT1: None,
            board.SLOT2: None,
            board.SLOT3: None,
            board.SLOT4: None,
            board.SLOT5: None,
            board.SLOT6: None
        })

        # Main output enable
        self.__main_en = digitalio.DigitalInOut(board.MAIN_EN)
        self.__main_en.switch_to_output(False)

        # User/Boot switch
        self.__sw_boot = digitalio.DigitalInOut(board.USER_SW)
        self.__sw_boot.switch_to_input()

        # ADC mux enable pins
        self.__adc_mux_ens = (digitalio.DigitalInOut(board.ADC_MUX_EN_1),
                              digitalio.DigitalInOut(board.ADC_MUX_EN_2))
        self.__adc_mux_ens[0].switch_to_output(False)
        self.__adc_mux_ens[1].switch_to_output(False)

        # ADC mux address pins
        self.__adc_mux_addrs = (digitalio.DigitalInOut(board.ADC_ADDR_1),
                                digitalio.DigitalInOut(board.ADC_ADDR_2),
                                digitalio.DigitalInOut(board.ADC_ADDR_3))
        self.__adc_mux_addrs[0].switch_to_output(False)
        self.__adc_mux_addrs[1].switch_to_output(False)
        self.__adc_mux_addrs[2].switch_to_output(False)

        self.__adc_io_chip = tca.get_chip(board.ADC_ADDR_1)
        self.__adc_io_ens_addrs = (1 << tca.get_number(board.ADC_MUX_EN_1),
                                   1 << tca.get_number(board.ADC_MUX_EN_2))
        self.__adc_io_adc_addrs = (1 << tca.get_number(board.ADC_ADDR_1),
                                   1 << tca.get_number(board.ADC_ADDR_2),
                                   1 << tca.get_number(board.ADC_ADDR_3))
        self.__adc_io_mask = self.__adc_io_ens_addrs[0] | self.__adc_io_ens_addrs[1] | \
                             self.__adc_io_adc_addrs[0] | self.__adc_io_adc_addrs[1] | self.__adc_io_adc_addrs[2]

        # User switches
        self.__switches = (digitalio.DigitalInOut(board.SW_A),
                           digitalio.DigitalInOut(board.SW_B))
        self.__switches[0].switch_to_input()
        self.__switches[1].switch_to_input()

        # User LEDs
        self.__leds = (digitalio.DigitalInOut(board.LED_A),
                       digitalio.DigitalInOut(board.LED_B))
        self.__leds[0].switch_to_output(False)
        self.__leds[1].switch_to_output(False)

        # Shared analog input
        self.__shared_adc = analogio.AnalogIn(board.SHARED_ADC)

        self.__clear_readings()

        self.__monitor_action_callback = None

    def reset(self):
        # Only disable the output if enabled (avoids duplicate messages)
        if self.is_main_output_enabled() is True:
            self.disable_main_output()

        self.__adc_mux_ens[0].value = False
        self.__adc_mux_ens[1].value = False

        self.__adc_mux_addrs[0].value = False
        self.__adc_mux_addrs[1].value = False
        self.__adc_mux_addrs[2].value = False

        self.__leds[0].value = False
        self.__leds[1].value = False

        # Configure each module so they go back to their default states
        for module in self.__slot_assignments.values():
            if module is not None and module.is_initialised():
                module.reset()

    def change_logging(self, logging_level):
        logging.level = logging_level

    def __check_slot(self, slot):
        if isinstance(slot, int):
            if slot < 1 or slot > self.NUM_SLOTS:
                raise ValueError("slot index out of range. Expected 1 to 6, or a slot object")

            slot = list(self.__slot_assignments.keys())[slot - 1]

        elif slot not in self.__slot_assignments:
            raise ValueError("slot is not a valid slot object or index")

        return slot

    def find_slots_with_module(self, module_type):
        if self.is_main_output_enabled():
            raise RuntimeError("Cannot find slots with modules whilst the main output is active")

        logging.info(f"> Finding slots with '{module_type.NAME}' module")

        slots = []
        for slot in self.__slot_assignments.keys():
            logging.info(f"[Slot{slot.ID}]", end=" ")
            detected = self.__detect_module(slot)

            if detected is module_type:
                logging.info(f"Found '{detected.NAME}' module")
                slots.append(slot.ID)
            else:
                logging.info(f"No '{module_type.NAME}` module")

        return slots

    def register_with_slot(self, module, slot):
        if self.is_main_output_enabled():
            raise RuntimeError("Cannot register modules with slots whilst the main output is active")

        slot = self.__check_slot(slot)

        module_type = type(module)
        if module_type is YukonModule:
            raise ValueError("Cannot register YukonModule")

        if module_type not in KNOWN_MODULES:
            raise ValueError(f"{module_type} is not a known module. If this is custom module, be sure to include it in the KNOWN_MODULES list.")

        if self.__slot_assignments[slot] is None:
            self.__slot_assignments[slot] = module
        else:
            raise ValueError("The selected slot is already populated")

    def deregister_slot(self, slot):
        if self.is_main_output_enabled():
            raise RuntimeError("Cannot deregister module slots whilst the main output is active")

        slot = self.__check_slot(slot)

        module = self.__slot_assignments[slot]
        if module is not None:
            module.deregister()
            self.__slot_assignments[slot] = None

    def __match_module(self, adc_level, slow1, slow2, slow3):
        for m in KNOWN_MODULES:
            if m.is_module(adc_level, slow1, slow2, slow3):
                return m
        if YukonModule.is_module(adc_level, slow1, slow2, slow3):
            return YukonModule
        return None

    def __detect_module(self, slot):
        slow1 = digitalio.DigitalInOut(slot.SLOW1)
        slow1.switch_to_input()

        slow2 = digitalio.DigitalInOut(slot.SLOW2)
        slow2.switch_to_input()

        slow3 = digitalio.DigitalInOut(slot.SLOW3)
        slow3.switch_to_input()

        self.__select_address(slot.ADC1_ADDR)
        adc_val = 0
        for i in range(self.DETECTION_SAMPLES):
            adc_val += self.__shared_adc_voltage()
        adc_val /= self.DETECTION_SAMPLES

        logging.debug(f"ADC1 = {adc_val}, SLOW1 = {int(slow1.value)}, SLOW2 = {int(slow2.value)}, SLOW3 = {int(slow3.value)}", end=", ")

        adc_level = ADC_FLOAT
        if adc_val <= self.DETECTION_ADC_LOW:
            adc_level = ADC_LOW
        elif adc_val >= self.DETECTION_ADC_HIGH:
            adc_level = ADC_HIGH

        detected = self.__match_module(adc_level, slow1.value, slow2.value, slow3.value)

        self.__deselect_address()
        slow3.deinit()
        slow2.deinit()
        slow1.deinit()

        return detected

    def detect_module(self, slot):
        if self.is_main_output_enabled():
            raise RuntimeError("Cannot detect modules whilst the main output is active")

        slot = self.__check_slot(slot)

        return self.__detect_module(slot)

    def __expand_slot_list(self, slot_list):
        if isinstance(slot_list, bool):
            if slot_list:
                return list(self.__slot_assignments.keys())
            else:
                return []

        if isinstance(slot_list, (list, tuple)):
            exp_list = []
            for slot in slot_list:
                exp_list.append(self.__check_slot(slot))
            return exp_list

        return [self.__check_slot(slot_list)]

    def __verify_modules(self, allow_unregistered, allow_undetected, allow_discrepencies, allow_no_modules):
        # Take the allowed parameters and expand them into slot lists that are easier to compare against
        allow_unregistered = self.__expand_slot_list(allow_unregistered)
        allow_undetected = self.__expand_slot_list(allow_undetected)
        allow_discrepencies = self.__expand_slot_list(allow_discrepencies)

        raise_unregistered = False
        raise_undetected = False
        raise_discrepency = False
        unregistered_slots = 0

        for slot, module in self.__slot_assignments.items():
            logging.info(f"[Slot{slot.ID}]", end=" ")
            detected = self.__detect_module(slot)

            if detected is None:
                if module is not None:
                    logging.info(f"No module detected! Expected a '{module.NAME}' module.")
                    if slot not in allow_undetected:
                        raise_undetected = True
                else:
                    logging.info("Module slot is empty.")
                    unregistered_slots += 1
            else:
                if module is not None:
                    if type(module) is detected:
                        logging.info(f"'{module.NAME}' module detected and registered.")
                    else:
                        logging.info(f"Module discrepency! Expected a '{module.NAME}' module, but detected a '{detected.NAME}' module.")
                        if slot not in allow_discrepencies:
                            raise_discrepency = True
                else:
                    logging.info(f"'{detected.NAME}' module detected but not registered.")
                    if slot not in allow_unregistered:
                        raise_unregistered = True
                    unregistered_slots += 1

        if not allow_no_modules and unregistered_slots == self.NUM_SLOTS:
            raise VerificationError("No modules have been registered with Yukon. At least one module needs to be registered to enable the output")

        if raise_discrepency:
            raise VerificationError("Detected a different combination of modules than what was registered with Yukon. Please check the modules attached to your board and the program you are running.")

        if raise_undetected:
            raise VerificationError("Some or all modules registered with Yukon have not been detected. Please check that the modules are correctly attached to your board or disable this warning.")

        if raise_unregistered:
            raise VerificationError("Detected modules that have not been registered with Yukon, which could behave unexpectedly when connected to power. Please remove these modules or disable this warning.")

        logging.info()  # New line

    def initialise_modules(self, allow_unregistered=False, allow_undetected=False, allow_discrepencies=False, allow_no_modules=False):
        if self.is_main_output_enabled():
            raise RuntimeError("Cannot verify modules whilst the main output is active")

        logging.info("> Checking output voltage ...")
        if self.read_output_voltage() >= self.OUTPUT_DISSIPATE_LEVEL:
            logging.info(f"> Waiting for output voltage to dissipate ...")

            start = time.monotonic_ns()
            while True:
                new_voltage = self.read_output_voltage()
                if new_voltage < self.OUTPUT_DISSIPATE_LEVEL:
                    break

                new_time = time.monotonic_ns()
                if new_time - start > self.OUTPUT_DISSIPATE_TIMEOUT_NS:
                    raise FaultError("[Yukon] Output voltage did not dissipate in an acceptable time. Aborting module initialisation")


        logging.info("> Verifying modules")

        self.__verify_modules(allow_unregistered, allow_undetected, allow_discrepencies, allow_no_modules)

        logging.info("> Initialising modules")

        for slot, module in self.__slot_assignments.items():
            if module is not None:
                logging.info(f"[Slot{slot.ID} '{module.NAME}'] Initialising ... ", end="")
                module.initialise(slot, self.read_slot_adc1, self.read_slot_adc2)
                logging.info("done")

        logging.info()  # New line

    def is_pressed(self, switch):
        if switch is self.SWITCH_A_NAME:
            switch = self.SWITCH_A
        elif switch is self.SWITCH_B_NAME:
            switch = self.SWITCH_B
        elif switch < 0 or switch > 1:
            raise ValueError("switch out of range. Expected 'A' or 'B', or SWITCH_A (0) or SWITCH_B (1)")

        return not self.__switches[switch].value

    def is_boot_pressed(self):
        return not self.__sw_boot.value

    def set_led(self, switch, value):
        if switch is self.SWITCH_A_NAME:
            switch = self.SWITCH_A
        elif switch is self.SWITCH_B_NAME:
            switch = self.SWITCH_B
        elif switch < 0 or switch > 1:
            raise ValueError("switch out of range. Expected 'A' or 'B', or SWITCH_A (0) or SWITCH_B (1)")

        self.__leds[switch].value = value

    def enable_main_output(self):
        if self.is_main_output_enabled() is False:
            logging.info("> Checking input voltage ...")
            voltage_in = self.read_input_voltage()
            if voltage_in > self.ABSOLUTE_MAX_VOLTAGE_LIMIT:
                raise OverVoltageError(f"[Yukon] Input voltage of {voltage_in}V exceeds the maximum of {self.ABSOLUTE_MAX_VOLTAGE_LIMIT}V! Aborting enable output")

            if voltage_in > self.__voltage_limit:
                raise OverVoltageError(f"[Yukon] Input voltage of {voltage_in}V exceeds the user set limit of {self.__voltage_limit}V! Aborting enable output")

            if voltage_in < self.VOLTAGE_ZERO_LEVEL:
                raise UnderVoltageError("[Yukon] No input voltage detected! Make sure power is being provided to the XT-30 (yellow) connector")

            if voltage_in < self.VOLTAGE_LOWER_LIMIT:
                raise UnderVoltageError(f"[Yukon] Input voltage below minimum operating level of {self.VOLTAGE_LOWER_LIMIT}V! Aborting enable output")

            start = time.monotonic_ns()

            old_voltage = self.read_output_voltage()
            first_stable_time = 0
            new_voltage = 0

            logging.info("> Enabling output ...")
            self.__enable_main_output()
            while True:
                new_voltage = self.read_output_voltage()
                if new_voltage > self.__voltage_limit:  # User limit cannot be beyond the absolute max, so this check is fine
                    self.disable_main_output()
                    if new_voltage > self.ABSOLUTE_MAX_VOLTAGE_LIMIT:
                        raise OverVoltageError(f"[Yukon] Output voltage of {new_voltage}V exceeded the maximum of {self.ABSOLUTE_MAX_VOLTAGE_LIMIT}V! Turning off output")
                    else:
                        raise OverVoltageError(f"[Yukon] Output voltage of {new_voltage}V exceeded the user set limit of {self.__voltage_limit}V! Turning off output")

                new_time = time.monotonic_ns()
                if abs(new_voltage - old_voltage) < self.OUTPUT_STABLISE_V_DIFF:
                    if first_stable_time == 0:
                        first_stable_time = new_time
                    elif new_time - first_stable_time > self.OUTPUT_STABLISE_TIME_NS:
                        break
                else:
                    first_stable_time = 0

                if new_time - start > self.OUTPUT_STABLISE_TIMEOUT_NS:
                    self.disable_main_output()
                    raise FaultError("[Yukon] Output voltage did not stablise in an acceptable time. Turning off output")

                old_voltage = new_voltage

            # Short Circuit
            if new_voltage < self.VOLTAGE_SHORT_LEVEL:
                self.disable_main_output()
                raise FaultError(f"[Yukon] Possible short circuit! Output voltage was {new_voltage}V whilst the input voltage was {voltage_in}V. Turning off output")

            # Under Voltage
            if new_voltage < self.VOLTAGE_LOWER_LIMIT:
                self.disable_main_output()
                raise UnderVoltageError(f"[Yukon] Output voltage of {new_voltage}V below minimum operating level. Turning off output")

            self.clear_readings()

            logging.info("> Output enabled")

    def __enable_main_output(self):
        self.__main_en.value = True

    def disable_main_output(self):
        self.__main_en.value = False
        logging.info("> Output disabled")

    def is_main_output_enabled(self):
        return self.__main_en.value

    def __deselect_address(self):
        self.__adc_mux_ens[0].value = False
        self.__adc_mux_ens[1].value = False

    def __select_address(self, address):
        if address < 0:
            raise ValueError("address is less than zero")
        elif address > 0b1111:
            raise ValueError("address is greater than number of available addresses")
        else:
            state = 0x0000

            if address & 0b0001 > 0:
                state |= self.__adc_io_adc_addrs[0]

            if address & 0b0010 > 0:
                state |= self.__adc_io_adc_addrs[1]

            if address & 0b0100 > 0:
                state |= self.__adc_io_adc_addrs[2]

            if address & 0b1000 > 0:
                state |= self.__adc_io_ens_addrs[0]
            else:
                state |= self.__adc_io_ens_addrs[1]

            tca.change_output_mask(self.__adc_io_chip, self.__adc_io_mask, state)

    def __shared_adc_voltage(self):
        return (self.__shared_adc.value * 3.3) / 65535  # This has been checked to be correct

    def read_input_voltage(self):
        self.__select_address(board.VOLTAGE_IN_SENSE_ADDR)
        return u16_to_voltage_in(self.__shared_adc.value)

    def read_output_voltage(self):
        self.__select_address(board.VOLTAGE_OUT_SENSE_ADDR)
        return u16_to_voltage_out(self.__shared_adc.value)

    def read_current(self):
        self.__select_address(board.CURRENT_SENSE_ADDR)
        return u16_to_current(self.__shared_adc.value)

    def read_temperature(self):
        self.__select_address(board.TEMP_SENSE_ADDR)
        return analog_to_temp(self.__shared_adc_voltage())

    def read_slot_adc1(self, slot):
        self.__select_address(slot.ADC1_ADDR)
        return self.__shared_adc_voltage()

    def read_slot_adc2(self, slot):
        self.__select_address(slot.ADC2_TEMP_ADDR)
        return self.__shared_adc_voltage()

    def assign_monitor_action(self, callback_function):
        if not None and not callable(callback_function):
            raise TypeError("callback is not callable or None")

        self.__monitor_action_callback = callback_function

    def monitor(self):
        voltage_in = self.read_input_voltage()

        # Over Voltage
        if voltage_in > self.__voltage_limit:  # User limit cannot be beyond the absolute max, so this check is fine
            self.disable_main_output()
            if voltage_in > self.ABSOLUTE_MAX_VOLTAGE_LIMIT:
                raise OverVoltageError(f"[Yukon] Input voltage of {voltage_in}V exceeded the maximum of {self.ABSOLUTE_MAX_VOLTAGE_LIMIT}V! Turning off output")
            else:
                raise OverVoltageError(f"[Yukon] Input voltage of {voltage_in}V exceeded the user set limit of {self.__voltage_limit}V! Turning off output")

        # Under Voltage
        if voltage_in < self.VOLTAGE_LOWER_LIMIT:
            self.disable_main_output()
            raise UnderVoltageError(f"[Yukon] Input voltage of {voltage_in}V below minimum operating level. Turning off output")

        # Short Circuit
        voltage_out = self.read_output_voltage()
        if voltage_out < self.VOLTAGE_SHORT_LEVEL:
            self.disable_main_output()
            raise FaultError(f"[Yukon] Possible short circuit! Output voltage was {voltage_out}V whilst the input voltage was {voltage_in}V. Turning off output")

        # Under Voltage
        if voltage_out < self.VOLTAGE_LOWER_LIMIT:
            self.disable_main_output()
            raise UnderVoltageError(f"[Yukon] Output voltage of {voltage_out}V below minimum operating level. Turning off output")

        # Over Current
        current = self.read_current()
        if current > self.__current_limit:
            self.disable_main_output()
            raise OverCurrentError(f"[Yukon] Current of {current}A exceeded the user set limit of {self.__current_limit}A! Turning off output")

        # Over Temperature
        temperature = self.read_temperature()
        if temperature > self.__temperature_limit:
            self.disable_main_output()
            raise OverTemperatureError(f"[Yukon] Temperature of {temperature}°C exceeded the user set limit of {self.__temperature_limit}°C! Turning off output")

        # Run some user action based on the latest readings
        if self.__monitor_action_callback is not None:
            self.__monitor_action_callback(voltage_in, voltage_out, current, temperature)

        for module in self.__slot_assignments.values():
            if module is not None:
                try:
                    module.monitor()
                except Exception:
                    self.disable_main_output()
                    raise  # Now the output is off, let the exception continue into user code

        self.__max_voltage_in = max(voltage_in, self.__max_voltage_in)
        self.__min_voltage_in = min(voltage_in, self.__min_voltage_in)
        self.__avg_voltage_in += voltage_in

        self.__max_voltage_out = max(voltage_out, self.__max_voltage_out)
        self.__min_voltage_out = min(voltage_out, self.__min_voltage_out)
        self.__avg_voltage_out += voltage_out

        self.__max_current = max(current, self.__max_current)
        self.__min_current = min(current, self.__min_current)
        self.__avg_current += current

        self.__max_temperature = max(temperature, self.__max_temperature)
        self.__min_temperature = min(temperature, self.__min_temperature)
        self.__avg_temperature += temperature

        self.__count_avg += 1

    def monitored_sleep(self, seconds, allowed=None, excluded=None):
        # Convert and handle the sleep as milliseconds
        self.monitored_sleep_ms(1000.0 * seconds + 0.5, allowed=allowed, excluded=excluded)

    def monitored_sleep_ms(self, ms, allowed=None, excluded=None):
        if ms < 0:
            raise ValueError("sleep length must be non-negative")

        # Calculate the time this sleep should end at, and monitor until then
        self.monitor_until_ms(ticks_add(ticks_ms(), int(ms)), allowed=allowed, excluded=excluded)

    def monitor_until_ms(self, end_ms, allowed=None, excluded=None):
        if end_ms < 0 or end_ms >= TICKS_PERIOD:
            raise ValueError("end_ms out or range. Must be a value obtained from supervisor.ticks_ms()")

        # Clear any readings from previous monitoring attempts
        self.clear_readings()

        # Ensure that at least one monitor check is performed
        self.monitor()
        remaining_ms = ticks_diff(end_ms, ticks_ms())

        # Perform any subsequent monitors until the end time is reached
        while remaining_ms > 0:
            self.monitor()
            remaining_ms = ticks_diff(end_ms, ticks_ms())

        # Process any readings that need it (e.g. averages)
        self.process_readings()

        if logging.level >= logging.LOG_INFO:
            self.__print_readings(allowed, excluded)

    def monitor_once(self, allowed=None, excluded=None):
        # Clear any readings from previous monitoring attempts
        self.clear_readings()

        # Perform a single monitoring check
        self.monitor()

        # Process any readings that need it (e.g. averages)
        self.process_readings()

        if logging.level >= logging.LOG_INFO:
            self.__print_readings(allowed, excluded)

    def __print_readings(self, allowed=None, excluded=None):
        self.__print_dict("[Yukon]", self.get_readings(), allowed, excluded)

        for slot, module in self.__slot_assignments.items():
            if module is not None:
                self.__print_dict(f"[Slot{slot.ID}]", module.get_readings(), allowed, excluded)
        print()

    def get_readings(self):
        return OrderedDict({
            "Vi_max": self.__max_voltage_in,
            "Vi_min": self.__min_voltage_in,
            "Vi_avg": self.__avg_voltage_in,
            "Vo_max": self.__max_voltage_out,
            "Vo_min": self.__min_voltage_out,
            "Vo_avg": self.__avg_voltage_out,
            "C_max": self.__max_current,
            "C_min": self.__min_current,
            "C_avg": self.__avg_current,
            "T_max": self.__max_temperature,
            "T_min": self.__min_temperature,
            "T_avg": self.__avg_temperature
        })

    def process_readings(self):
        if self.__count_avg > 0:
            self.__avg_voltage_in /= self.__count_avg
            self.__avg_voltage_out /= self.__count_avg
            self.__avg_current /= self.__count_avg
            self.__avg_temperature /= self.__count_avg

        for module in self.__slot_assignments.values():
            if module is not None:
                module.process_readings()

    def __clear_readings(self):
        self.__max_voltage_in = float('-inf')
        self.__min_voltage_in = float('inf')
        self.__avg_voltage_in = 0
        
        self.__max_voltage_out = float('-inf')
        self.__min_voltage_out = float('inf')
        self.__avg_voltage_out = 0

        self.__max_current = float('-inf')
        self.__min_current = float('inf')
        self.__avg_current = 0

        self.__max_temperature = float('-inf')
        self.__min_temperature = float('inf')
        self.__avg_temperature = 0

        self.__count_avg = 0

    def clear_readings(self):
        self.__clear_readings()
        for module in self.__slot_assignments.values():
            if module is not None:
                module.clear_readings()

    def __print_dict(self, section_name, readings, allowed=None, excluded=None):
        if len(readings) > 0:
            print(section_name, end=" ")
            for name, value in readings.items():
                if ((allowed is None) or (allowed is not None and name in allowed)) and ((excluded is None) or (excluded is not None and name not in excluded)):
                    if isinstance(value, bool):
                        print(f"{name} = {int(value)},", end=" ")  # Output 0 or 1 rather than True of False, so bools can appear on plotter charts
                    else:
                        print(f"{name} = {value},", end=" ")
