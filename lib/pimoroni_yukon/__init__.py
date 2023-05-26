# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

import time
import math
import board
import digitalio
import analogio
import supervisor
import tca

from pimoroni_yukon.modules import KNOWN_MODULES, ADC_FLOAT, ADC_LOW, ADC_HIGH
from collections import OrderedDict


class Yukon:
    """Yukon class."""

    VOLTAGE_MAX = 17.0
    VOLTAGE_MIN_MEASURE = 0.030
    VOLTAGE_MAX_MEASURE = 2.294

    CURRENT_MAX = 10
    CURRENT_MIN_MEASURE = 0.0147
    CURRENT_MAX_MEASURE = 0.9307

    SWITCH_A = 0
    SWITCH_B = 1
    SWITCH_A_NAME = 'A'
    SWITCH_B_NAME = 'B'
    SWITCH_USER = 2
    NUM_SLOTS = 6

    DEFAULT_VOLTAGE_LIMIT = 17.2
    VOLTAGE_LOWER_LIMIT = 4.8
    VOLTAGE_ZERO_LEVEL = 0.05
    DEFAULT_CURRENT_LIMIT = 20
    DEFAULT_TEMPERATURE_LIMIT = 90
    ABSOLUTE_MAX_VOLTAGE_LIMIT = 18

    DETECTION_SAMPLES = 64
    DETECTION_ADC_LOW = 0.1
    DETECTION_ADC_HIGH = 3.2

    def __init__(self, voltage_limit=DEFAULT_VOLTAGE_LIMIT, current_limit=DEFAULT_CURRENT_LIMIT, temperature_limit=DEFAULT_TEMPERATURE_LIMIT):
        self.__voltage_limit = min(voltage_limit, self.ABSOLUTE_MAX_VOLTAGE_LIMIT)
        self.__current_limit = current_limit
        self.__temperature_limit = temperature_limit

        self.__slot_assignments = OrderedDict({
            board.SLOT1: None,
            board.SLOT2: None,
            board.SLOT3: None,
            board.SLOT4: None,
            board.SLOT5: None,
            board.SLOT6: None
        })
        self.__slots_initialised = False

        # Main output enable
        self.__main_en = digitalio.DigitalInOut(board.MAIN_EN)
        self.__main_en.direction = digitalio.Direction.OUTPUT

        # User/Boot switch
        self.__sw_boot = digitalio.DigitalInOut(board.USER_SW)
        self.__sw_boot.direction = digitalio.Direction.INPUT

        # ADC mux enable pins
        self.__adc_mux_ens = (digitalio.DigitalInOut(board.ADC_MUX_EN_1),
                              digitalio.DigitalInOut(board.ADC_MUX_EN_2))
        self.__adc_mux_ens[0].direction = digitalio.Direction.OUTPUT
        self.__adc_mux_ens[1].direction = digitalio.Direction.OUTPUT

        # ADC mux address pins
        self.__adc_mux_addrs = (digitalio.DigitalInOut(board.ADC_ADDR_1),
                                digitalio.DigitalInOut(board.ADC_ADDR_2),
                                digitalio.DigitalInOut(board.ADC_ADDR_3))
        self.__adc_mux_addrs[0].direction = digitalio.Direction.OUTPUT
        self.__adc_mux_addrs[1].direction = digitalio.Direction.OUTPUT
        self.__adc_mux_addrs[2].direction = digitalio.Direction.OUTPUT

        # User switches
        self.__switches = (digitalio.DigitalInOut(board.SW_A),
                           digitalio.DigitalInOut(board.SW_B))
        self.__switches[0].direction = digitalio.Direction.INPUT
        self.__switches[1].direction = digitalio.Direction.INPUT

        # User LEDs
        self.__leds = (digitalio.DigitalInOut(board.LED_A),
                       digitalio.DigitalInOut(board.LED_B))
        self.__leds[0].direction = digitalio.Direction.OUTPUT
        self.__leds[1].direction = digitalio.Direction.OUTPUT

        # Extension header (LCD) pins
        self.__lcd_bl = digitalio.DigitalInOut(board.LCD_BL)
        self.__lcd_bl.direction = digitalio.Direction.OUTPUT

        self.__lcd_cs = digitalio.DigitalInOut(board.LCD_CS)
        self.__lcd_cs.direction = digitalio.Direction.OUTPUT

        self.__lcd_dc = digitalio.DigitalInOut(board.LCD_DC)
        self.__lcd_dc.direction = digitalio.Direction.OUTPUT

        # Shared analog input
        self.__shared_adc = analogio.AnalogIn(board.SHARED_ADC)

        self.__clear_readings()

    def __check_slot(self, slot):
        if type(slot) is int:
            if slot < 1 or slot > self.NUM_SLOTS:
                raise ValueError("slot index out of range. Expected 1 to 6, or a slot object")

            slot = list(self.__slot_assignments.keys())[slot - 1]

        elif slot not in self.__slot_assignments:
            raise ValueError("slot is not a valid slot object or index")

        return slot

    def find_slots_with_module(self, module_type, debug_level=0):
        if self.is_main_output():
            raise RuntimeError("Cannot find slots with modules whilst the main output is active")

        if debug_level >= 1:
            print(f"> Finding slots with '{module_type.NAME}' module")

        slots = []
        slot_num = 1

        for slot, module in self.__slot_assignments.items():
            if debug_level >= 1:
                print(f"[Slot{slot_num}]", end=" ")
            detected = self.__detect_module(slot, debug_level=debug_level)

            if detected is module_type:
                if debug_level >= 1:
                    print(f"Found '{detected.NAME}' module")
                slots.append(slot_num)
            else:
                if debug_level >= 1:
                    print(f"No '{module_type.NAME}` module")

            slot_num += 1
        return slots

    def register_with_slot(self, module, slot):
        if self.is_main_output():
            raise RuntimeError("Cannot register modules with slots whilst the main output is active")

        slot = self.__check_slot(slot)

        if self.__slot_assignments[slot] is None:
            self.__slot_assignments[slot] = module
        else:
            raise RuntimeError("The selected slot is already populated")

    def deregister_slot(self, slot):
        if self.is_main_output():
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
        return None

    def __detect_module(self, slot, debug_level):
        slow1 = digitalio.DigitalInOut(slot.SLOW1)
        slow1.direction = digitalio.Direction.INPUT

        slow2 = digitalio.DigitalInOut(slot.SLOW2)
        slow2.direction = digitalio.Direction.INPUT

        slow3 = digitalio.DigitalInOut(slot.SLOW3)
        slow3.direction = digitalio.Direction.INPUT

        self.__select_address(slot.ADC1_ADDR)
        adc_val = 0
        for i in range(self.DETECTION_SAMPLES):
            adc_val += self.__shared_adc_voltage()
        adc_val /= self.DETECTION_SAMPLES

        if debug_level >= 2:
            print(f"ADC1 = {adc_val}, SLOW1 = {int(slow1.value)}, SLOW2 = {int(slow2.value)}, SLOW3 = {int(slow3.value)}", end=", ")

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

    def detect_module(self, slot, debug_level=1):
        if self.is_main_output():
            raise RuntimeError("Cannot detect modules whilst the main output is active")

        slot = self.__check_slot(slot)

        return self.__detect_module(slot, debug_level=debug_level)

    def __expand_slot_list(self, slot_list):
        if type(slot_list) is bool:
            if slot_list:
                return list(self.__slot_assignments.keys())
            else:
                return []

        if type(slot_list) in (list, tuple):
            exp_list = []
            for slot in slot_list:
                exp_list.append(self.__check_slot(slot))
            return exp_list

        return [self.__check_slot(slot_list)]

    def __verify_modules(self, allow_unregistered, allow_undetected, allow_discrepencies, allow_no_modules, debug_level):
        # Take the allowed parameters and expand them into slot lists that are easier to compare against
        allow_unregistered = self.__expand_slot_list(allow_unregistered)
        allow_undetected = self.__expand_slot_list(allow_undetected)
        allow_discrepencies = self.__expand_slot_list(allow_discrepencies)

        raise_unregistered = False
        raise_undetected = False
        raise_discrepency = False
        unregistered_slots = 0
        slot_num = 1

        for slot, module in self.__slot_assignments.items():
            if debug_level >= 1:
                print(f"[Slot{slot_num}]", end=" ")
            detected = self.__detect_module(slot, debug_level=debug_level)

            if detected is None:
                if module is not None:
                    if debug_level >= 1:
                        print(f"No module detected! Expected a '{module.NAME}' module.")
                    if slot not in allow_undetected:
                        raise_undetected = True
                else:
                    if debug_level >= 1:
                        print(f"Module slot is empty.")
                    unregistered_slots += 1
            else:
                if type(module) is detected:
                    if debug_level >= 1:
                        print(f"'{module.NAME}' module detected and registered.")
                else:
                    if module is not None:
                        if debug_level >= 1:
                            print(f"Module discrepency! Expected a '{module.NAME}' module, but detected a '{detected.NAME}' module.")
                        if slot not in allow_discrepencies:
                            raise_discrepency = True
                    else:
                        if debug_level >= 1:
                            print(f"'{detected.NAME}' module detected but not registered.", sep="")
                        if slot not in allow_unregistered:
                            raise_unregistered = True
                        unregistered_slots += 1
            slot_num += 1

        if not allow_no_modules and unregistered_slots == 6:
            raise RuntimeError("No modules have been registered with Yukon. At least one module needs to be registered to enable the output")

        if raise_discrepency:
            raise RuntimeError("Detected a different combination of modules than what was registered with Yukon. Please check the modules attached to your board and the program you are running.")

        if raise_undetected:
            raise RuntimeError("Some or all modules registered with Yukon have not been detected. Please check that the modules are correctly attached to your board or disable this warning.")

        if raise_unregistered:
            raise RuntimeError("Detected modules that have not been registered with Yukon, which could behave unexpectedly when connected to power. Please remove these modules or disable this warning.")

        if debug_level >= 1:
            print()

    def initialise_modules(self, allow_unregistered=False, allow_undetected=False, allow_discrepencies=False, allow_no_modules=False, debug_level=1):
        if self.is_main_output():
            raise RuntimeError("Cannot verify modules whilst the main output is active")

        if debug_level >= 1:
            print(f"> Verifying modules")

        self.__verify_modules(allow_unregistered, allow_undetected, allow_discrepencies, allow_no_modules, debug_level=debug_level)

        if debug_level >= 1:
            print(f"> Initialising modules")

        slot_num = 1
        for slot, module in self.__slot_assignments.items():
            if module is not None:
                if debug_level >= 1:
                    print(f"[Slot{slot_num} '{module.NAME}'] Initialising ... ", end="")
                module.initialise(slot, self.read_slot_adc1, self.read_slot_adc2)
                if debug_level >= 1:
                    print(f"done")
            slot_num += 1

        if debug_level >= 1:
            print()

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

    def enable_main_output(self, debug_level=1):
        if self.is_main_output() is False:
            start = time.monotonic_ns()

            self.__select_address(board.VOLTAGE_SENSE_ADDR)

            old_voltage = max(((self.__shared_adc_voltage() - self.VOLTAGE_MIN_MEASURE) * self.VOLTAGE_MAX) / (self.VOLTAGE_MAX_MEASURE - self.VOLTAGE_MIN_MEASURE), 0.0)
            first_stable_time = 0
            new_voltage = 0
            dur = 100 * 1000 * 1000
            dur_b = 5 * 1000 * 1000

            if debug_level >= 1:
                print("> Enabling output ...")
            self.__enable_main_output()
            while True:
                new_voltage = ((self.__shared_adc_voltage() - self.VOLTAGE_MIN_MEASURE) * self.VOLTAGE_MAX) / (self.VOLTAGE_MAX_MEASURE - self.VOLTAGE_MIN_MEASURE)
                if new_voltage > self.ABSOLUTE_MAX_VOLTAGE_LIMIT:
                    self.disable_main_output()
                    raise RuntimeError("[Yukon] Voltage exceeded user safe level! Turning off output")

                new_time = time.monotonic_ns()
                if abs(new_voltage - old_voltage) < 0.05:
                    if first_stable_time == 0:
                        first_stable_time = new_time
                    elif new_time - first_stable_time > dur_b:
                        break
                else:
                    first_stable_time = 0

                if new_time - start > dur:
                    self.disable_main_output()
                    raise RuntimeError("[Yukon] Voltage did not stablise in an acceptable time. Turning off output")

                old_voltage = new_voltage

            if new_voltage < self.VOLTAGE_ZERO_LEVEL:
                self.disable_main_output()
                raise RuntimeError("[Yukon] No voltage detected! Make sure power is being provided to the XT-30 (yellow) connector")
            elif new_voltage < self.VOLTAGE_LOWER_LIMIT:
                self.disable_main_output()
                raise RuntimeError("[Yukon] Voltage below minimum operating level. Turning off output")

            if debug_level >= 1:
                print("> Output enabled")

    def __enable_main_output(self):
        self.__main_en.value = True

    def disable_main_output(self, debug_level=1):
        self.__main_en.value = False
        if debug_level >= 1:
            print("> Output disabled")

    def is_main_output(self):
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
            set_list = []
            clr_list = []
            if address & 0b0001 > 0:
                set_list.append(board.ADC_ADDR_1)
            else:
                clr_list.append(board.ADC_ADDR_1)

            if address & 0b0010 > 0:
                set_list.append(board.ADC_ADDR_2)
            else:
                clr_list.append(board.ADC_ADDR_2)

            if address & 0b0100 > 0:
                set_list.append(board.ADC_ADDR_3)
            else:
                clr_list.append(board.ADC_ADDR_3)

            if address & 0b1000 > 0:
                clr_list.append(board.ADC_MUX_EN_2)
                set_list.append(board.ADC_MUX_EN_1)
            else:
                clr_list.append(board.ADC_MUX_EN_1)
                set_list.append(board.ADC_MUX_EN_2)

            tca.change_output(set=set_list, clear=clr_list)

    def __shared_adc_voltage(self):
        return (self.__shared_adc.value * 3.3) / 65536

    def read_voltage(self):
        self.__select_address(board.VOLTAGE_SENSE_ADDR)
        # return (self.__shared_adc_voltage() * (100 + 16)) / 16  # Old equation, kept for reference
        return max(((self.__shared_adc_voltage() - self.VOLTAGE_MIN_MEASURE) * self.VOLTAGE_MAX) / (self.VOLTAGE_MAX_MEASURE - self.VOLTAGE_MIN_MEASURE), 0.0)

    def read_current(self):
        self.__select_address(board.CURRENT_SENSE_ADDR)
        # return (self.__shared_adc_voltage() - 0.015) / ((1 + (5100 / 27.4)) * 0.0005)  # Old equation, kept for reference
        return max(((self.__shared_adc_voltage() - self.CURRENT_MIN_MEASURE) * self.CURRENT_MAX) / (self.CURRENT_MAX_MEASURE - self.CURRENT_MIN_MEASURE), 0.0)

    def read_temperature(self):
        self.__select_address(board.TEMP_SENSE_ADDR)
        sense = self.__shared_adc_voltage()
        r_thermistor = sense / ((3.3 - sense) / 5100)
        ROOM_TEMP = 273.15 + 25
        RESISTOR_AT_ROOM_TEMP = 10000.0
        BETA = 3435
        t_kelvin = (BETA * ROOM_TEMP) / (BETA + (ROOM_TEMP * math.log(r_thermistor / RESISTOR_AT_ROOM_TEMP)))
        t_celsius = t_kelvin - 273.15

        # https://www.allaboutcircuits.com/projects/measuring-temperature-with-an-ntc-thermistor/
        return t_celsius

    def read_expansion(self):
        self.__select_address(board.EX_ADC_ADDR)
        return self.__shared_adc_voltage()

    def read_slot_adc1(self, slot):
        self.__select_address(slot.ADC1_ADDR)
        return self.__shared_adc_voltage()

    def read_slot_adc2(self, slot):
        self.__select_address(slot.ADC2_TEMP_ADDR)
        return self.__shared_adc_voltage()

    def monitor(self, debug_level=0):
        voltage = self.read_voltage()
        if voltage > self.__voltage_limit:
            self.disable_main_output()
            raise RuntimeError(f"[Yukon] Voltage of {voltage}V exceeded the user set level of {self.__voltage_limit}V! Turning off output")
        elif voltage < self.VOLTAGE_LOWER_LIMIT:
            self.disable_main_output()
            raise RuntimeError(f"[Yukon] Voltage of {voltage}V below minimum operating level. Turning off output")

        current = self.read_current()
        if current > self.__current_limit:
            self.disable_main_output()
            raise RuntimeError(f"[Yukon] Current of {current}A exceeded the user set level of {self.__current_limit}A! Turning off output")

        temperature = self.read_temperature()
        if temperature > self.__temperature_limit:
            self.disable_main_output()
            raise RuntimeError(f"[Yukon] Temperature of {temperature}°C exceeded the user set level of {self.__temperature_limit}°C! Turning off output")

        slot_num = 1
        for slot, module in self.__slot_assignments.items():
            if module is not None:
                try:
                    message = module.monitor(debug_level=debug_level)
                    if message is not None:
                        print(f"[Slot{slot_num} '{module.NAME}'] {message}")
                except RuntimeError as e:
                    self.disable_main_output()
                    raise RuntimeError(f"[Slot{slot_num} '{module.NAME}'] {str(e)}! Turning off output") from None
            slot_num += 1

        self.__max_voltage = max(voltage, self.__max_voltage)
        self.__min_voltage = min(voltage, self.__min_voltage)
        self.__avg_voltage += voltage

        self.__max_current = max(current, self.__max_current)
        self.__min_current = min(current, self.__min_current)
        self.__avg_current += current

        self.__max_temperature = max(temperature, self.__max_temperature)
        self.__min_temperature = min(temperature, self.__min_temperature)
        self.__avg_temperature += temperature

        self.__count_avg += 1

    def monitored_sleep(self, seconds, debug_level=0):
        if seconds < 0:
            raise ValueError("sleep length must be non-negative")

        self.clear_readings()

        remaining_ms = int(1000.0 * seconds + 0.5)
        end_ms = supervisor.ticks_ms() + remaining_ms

        while remaining_ms > 0:
            #start_ticks = supervisor.ticks_ms()
            self.monitor(debug_level=debug_level)
            #ticks_diff = supervisor.ticks_ms() - start_ticks
            #print(ticks_diff)
            remaining_ms = end_ms - supervisor.ticks_ms()

        self.__process_readings()

        if debug_level >= 2:
            self.__print_readings()

    # TODO
    # def monitor_until(self, time, debug_level=0)

    def __print_readings(self):
        self.__print_dict(f"[Yukon]", self.get_readings())

        slot_num = 1
        for slot, module in self.__slot_assignments.items():
            if module is not None:
                self.__print_dict(f"[Slot{slot_num}]", module.get_readings())
            slot_num += 1
        print()

    def get_readings(self):
        return OrderedDict({
            "V_max": self.__max_voltage,
            "V_min": self.__min_voltage,
            "V_avg": self.__avg_voltage,
            "C_max": self.__max_current,
            "C_min": self.__min_current,
            "C_avg": self.__avg_current,
            "T_max": self.__max_temperature,
            "T_min": self.__min_temperature,
            "T_avg": self.__avg_temperature
        })

    def process_readings(self):
        if self.__count_avg > 0:
            self.__avg_voltage /= self.__count_avg
            self.__avg_current /= self.__count_avg
            self.__avg_temperature /= self.__count_avg

        for slot, module in self.__slot_assignments.items():
            if module is not None:
                module.process_readings()

    def __clear_readings(self):
        self.__max_voltage = float('-inf')
        self.__min_voltage = float('inf')
        self.__avg_voltage = 0

        self.__max_current = float('-inf')
        self.__min_current = float('inf')
        self.__avg_current = 0

        self.__max_temperature = float('-inf')
        self.__min_temperature = float('inf')
        self.__avg_temperature = 0

        self.__count_avg = 0

    def clear_readings(self):
        self.__clear_readings()
        for slot, module in self.__slot_assignments.items():
            if module is not None:
                module.clear_readings()

    def __print_dict(self, section_name, readings):
        if len(readings) > 0:
            print(section_name, end=" ")
            for name, value in readings.items():
                if type(value) is bool:
                    print(f"{name} = {int(value)},", end=" ")
                else:
                    print(f"{name} = {value},", end=" ")

    def lcd_dc(self, value):
        self.__lcd_dc.value = value

    def lcd_cs(self, value):
        self.__lcd_cs.value = value

    def lcd_bl(self, value):
        self.__lcd_bl.value = value

    def reset(self):
        # Only disable the output if enabled (avoids duplicate messages)
        if self.is_main_output() is True:
            self.disable_main_output()

        self.__adc_mux_ens[0].value = False
        self.__adc_mux_ens[1].value = False

        self.__adc_mux_addrs[0].value = False
        self.__adc_mux_addrs[1].value = False
        self.__adc_mux_addrs[2].value = False

        self.__leds[0].value = False
        self.__leds[1].value = False

        self.__lcd_bl.value = False
        self.__lcd_cs.value = False
        self.__lcd_dc.value = False

        # Configure each module so they go back to their default states
        for slot, module in self.__slot_assignments.items():
            if module is not None and module.is_initialised():
                module.configure()
