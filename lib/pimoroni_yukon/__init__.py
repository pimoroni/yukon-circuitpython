# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

import math
import board
import digitalio
import analogio
import supervisor
import tca

from pimoroni_yukon.modules import KNOWN_MODULES, ADC_FLOAT, ADC_LOW, ADC_HIGH


class Yukon:
    """Yukon class."""

    VOLTAGE_MAX = 17.0
    VOLTAGE_MIN_MEASURE = 0.030
    VOLTAGE_MAX_MEASURE = 2.294

    CURRENT_MAX = 4
    CURRENT_MIN_MEASURE = 0.0162
    CURRENT_MAX_MEASURE = 0.2268

    SWITCH_A = 0
    SWITCH_B = 1
    SWITCH_A_NAME = 'A'
    SWITCH_B_NAME = 'B'
    SWITCH_USER = 2
    NUM_SLOTS = 6
    
    DEFAULT_VOLTAGE_LIMIT = 17.2
    DEFAULT_CURRENT_LIMIT = 15
    DEFAULT_TEMPERATURE_LIMIT = 90

    def __init__(self, voltage_limit=DEFAULT_VOLTAGE_LIMIT, current_limit=DEFAULT_CURRENT_LIMIT, temperature_limit=DEFAULT_TEMPERATURE_LIMIT):
        self.__voltage_limit = voltage_limit
        self.__current_limit = current_limit
        self.__temperature_limit = temperature_limit
        
        from collections import OrderedDict
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

    def __check_slot(self, slot):
        if type(slot) is int:
            if slot < 1 or slot > self.NUM_SLOTS:
                raise ValueError("slot index out of range. Expected 1 to 6, or a slot object")

            slot = list(self.__slot_assignments.keys())[slot - 1]

        elif slot not in self.__slot_assignments:
            raise ValueError("slot is not a valid slot object or index")

        return slot

    def register_with_slot(self, module, slot):
        if self.is_main_output():
            raise RuntimeError("cannot register modules with slots whilst the main output is active")

        slot = self.__check_slot(slot)

        if self.__slot_assignments[slot] is None:
            self.__slot_assignments[slot] = module
            # module.__slot = slot
        else:
            raise RuntimeError("the selected slot is already populated")

    def deregister_slot(self, slot):
        if self.is_main_output():
            raise RuntimeError("cannot deregister module slots whilst the main output is active")

        slot = self.__check_slot(slot)

        module = self.__slot_assignments[slot]
        if module is not None:
            # module.__slot == None
            self.__slot_assignments[slot] = None

    def __match_module(self, adc_level, slow1, slow2, slow3):
        for m in KNOWN_MODULES:
            if m.is_module(adc_level, slow1, slow2, slow3):
                return m
        return None

    def __detect_module(self, slot):
        slow1 = digitalio.DigitalInOut(slot.SLOW1)
        slow1.direction = digitalio.Direction.INPUT

        slow2 = digitalio.DigitalInOut(slot.SLOW2)
        slow2.direction = digitalio.Direction.INPUT

        slow3 = digitalio.DigitalInOut(slot.SLOW3)
        slow3.direction = digitalio.Direction.INPUT

        self.__select_address(slot.ADC1_ADDR)
        adc_val = 0
        for i in range(64):
            adc_val += self.__shared_adc_voltage()
        adc_val /= 64

        # print(adc_val, int(slow1.value), int(slow2.value), int(slow3.value), end="\t")

        adc_level = ADC_FLOAT
        if adc_val <= 0.1:
            adc_level = ADC_LOW
        elif adc_val >= 3.1:
            adc_level = ADC_HIGH

        detected = self.__match_module(adc_level, slow1.value, slow2.value, slow3.value)

        self.__deselect_address()
        slow3.deinit()
        slow2.deinit()
        slow1.deinit()

        return detected

    def detect_module(self, slot):
        if self.is_main_output():
            raise RuntimeError("Cannot detect modules whilst the main output is active")

        slot = self.__check_slot(slot)

        return self.__detect_module(slot)

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

    def __verify_modules(self, allow_unregistered=False, allow_undetected=False, allow_discrepencies=False):
        # Take the allowed parameters and expand them into slot lists that are easier to compare against
        allow_unregistered = self.__expand_slot_list(allow_unregistered)
        allow_undetected = self.__expand_slot_list(allow_undetected)
        allow_discrepencies = self.__expand_slot_list(allow_discrepencies)

        raise_unregistered = False
        raise_undetected = False
        raise_discrepency = False
        slot_num = 1
        for slot, module in self.__slot_assignments.items():
            print(f"[Slot {slot_num}]", end=" ")
            detected = self.__detect_module(slot)

            if detected is None:
                if module is not None:
                    print(f"No module detected! Expected a '{module.NAME}' module.")
                    if slot not in allow_undetected:
                        raise_undetected = True
                else:
                    print(f"Module slot is empty.")
            else:
                if type(module) is detected:
                    print(f"'{module.NAME}' module detected and registered.")
                else:
                    if module is not None:
                        print(f"Module discrepency! Expected a '{module.NAME}' module, but detected a '{detected.NAME}' module.")
                        if slot not in allow_discrepencies:
                            raise_discrepency = True
                    else:
                        print(f"'{detected.NAME}' module detected but not registered.", sep="")
                        if slot not in allow_unregistered:
                            raise_unregistered = True
            slot_num += 1

        if raise_discrepency:
            raise RuntimeError("Detected a different combination of modules than what was registered with Yukon. Please check the modules attached to your board and the program you are running.")

        if raise_undetected:
            raise RuntimeError("Some or all modules registered with Yukon have not been detected. Please check that the modules are correctly attached to your board or disable this warning.")

        if raise_unregistered:
            raise RuntimeError("Detected modules that have not been registered with Yukon, which could behave unexpectedly when connected to power. Please remove these modules or disable this warning.")

    def initialise_modules(self, allow_unregistered=False, allow_undetected=False, allow_discrepencies=False):
        if self.is_main_output():
            raise RuntimeError("Cannot verify modules whilst the main output is active")

        self.__verify_modules(allow_unregistered, allow_undetected, allow_discrepencies)

        for slot, module in self.__slot_assignments.items():
            if module is not None:
                module.init(slot, self.read_slot_adc1)

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
        if self.__main_en.value is False:
            import time
            start = time.monotonic_ns()

            self.__select_address(board.VOLTAGE_SENSE_ADDR)

            old_voltage = max(((self.__shared_adc_voltage() - self.VOLTAGE_MIN_MEASURE) * self.VOLTAGE_MAX) / (self.VOLTAGE_MAX_MEASURE - self.VOLTAGE_MIN_MEASURE), 0.0)
            first_stable_time = 0
            new_voltage = 0
            dur = 100 * 1000 * 1000
            dur_b = 5 * 1000 * 1000

            self.__main_en.value = True
            while True:
                new_voltage = ((self.__shared_adc_voltage() - self.VOLTAGE_MIN_MEASURE) * self.VOLTAGE_MAX) / (self.VOLTAGE_MAX_MEASURE - self.VOLTAGE_MIN_MEASURE)
                if new_voltage > 18:
                    self.__main_en.value = False
                    raise RuntimeError("Voltage exceeded user safe level! Turning off output")

                new_time = time.monotonic_ns()
                if abs(new_voltage - old_voltage) < 0.05:
                    if first_stable_time == 0:
                        first_stable_time = new_time
                    elif new_time - first_stable_time > dur_b:
                        break
                else:
                    first_stable_time = 0

                if new_time - start > dur:
                    self.__main_en.value = False
                    raise RuntimeError("Voltage did not stablise in an acceptable time. Turning off output")

                old_voltage = new_voltage

    def disable_main_output(self):
        self.__main_en.value = False

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
        # return (self.__shared_adc_voltage() * (100 + 16)) / 16
        return max(((self.__shared_adc_voltage() - self.VOLTAGE_MIN_MEASURE) * self.VOLTAGE_MAX) / (self.VOLTAGE_MAX_MEASURE - self.VOLTAGE_MIN_MEASURE), 0.0)

    def read_current(self):
        self.__select_address(board.CURRENT_SENSE_ADDR)
        # return (self.__shared_adc_voltage() - 0.015) / ((1 + (5100 / 27.4)) * 0.0005)
        return max(((self.__shared_adc_voltage() - self.CURRENT_MIN_MEASURE) * self.CURRENT_MAX) / (self.CURRENT_MAX_MEASURE - self.CURRENT_MIN_MEASURE), 0.0)

    def read_temperature(self):
        self.__select_address(board.TEMP_SENSE_ADDR)
        sense = self.__shared_adc_voltage()
        rThermistor = sense / ((3.3 - sense) / 5100)
        ROOM_TEMP = 273.15 + 25
        RESISTOR_ROOM_TEMP = 10000.0
        BETA = 3435
        tKelvin = (BETA * ROOM_TEMP) / (BETA + (ROOM_TEMP * math.log(rThermistor / RESISTOR_ROOM_TEMP)))
        tCelsius = tKelvin - 273.15

        # https://www.allaboutcircuits.com/projects/measuring-temperature-with-an-ntc-thermistor/
        return tCelsius

    def read_expansion(self):
        self.__select_address(board.EX_ADC_ADDR)
        return self.__shared_adc_voltage()

    def read_slot_adc1(self, slot):
        self.__select_address(slot.ADC1_ADDR)
        return self.__shared_adc_voltage()

    def read_slot_adc2(self, slot):
        self.__select_address(slot.ADC2_TEMP_ADDR)
        return self.__shared_adc_voltage()

    def read_slot_adc2_as_temp(self, slot):
        import math
        self.__select_address(slot.ADC2_TEMP_ADDR)
        sense = self.__shared_adc_voltage()
        rThermistor = sense / ((3.3 - sense) / 5100)
        ROOM_TEMP = 273.15 + 25
        RESISTOR_ROOM_TEMP = 10000.0
        BETA = 3435
        tKelvin = (BETA * ROOM_TEMP) / (BETA + (ROOM_TEMP * math.log(rThermistor / RESISTOR_ROOM_TEMP)))
        tCelsius = tKelvin - 273.15

        # https://www.allaboutcircuits.com/projects/measuring-temperature-with-an-ntc-thermistor/
        return tCelsius
    
    def monitor(self):
        voltage = self.read_voltage()
        if voltage > self.__voltage_limit:
            self.disable_main_output()
            raise RuntimeError(f"Voltage of {voltage}V exceeded the user set level of {self.__voltage_limit}V! Turning off output")

        current = self.read_current()
        if current > self.__current_limit:
            self.disable_main_output()
            raise RuntimeError(f"Current of {current}A exceeded the user set level of {self.__current_limit}A! Turning off output")
        
        temp = self.read_temperature()
        if temp > self.__temperature_limit:
            self.disable_main_output()
            raise RuntimeError(f"Temperature of {temp}°C exceeded the user set level of {self.__temperature_limit}°C! Turning off output")

    def monitored_sleep(self, seconds):
        if seconds < 0:
            raise ValueError("sleep length must be non-negative")

        remaining_ms = int(1000.0 * seconds + 0.5)
        end_ms = supervisor.ticks_ms() + remaining_ms

        while remaining_ms > 0:
            self.monitor()
            remaining_ms = end_ms - supervisor.ticks_ms()

    def lcd_dc(self, value):
        self.__lcd_dc.value = value

    def lcd_cs(self, value):
        self.__lcd_cs.value = value

    def lcd_bl(self, value):
        self.__lcd_bl.value = value

    def reset(self):
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
        
        for slot, module in self.__slot_assignments.items():
            if module is not None:
                try:
                    module.reset()
                except AttributeError:
                    # No reset function
                    pass
