# SPDX-FileCopyrightText: 2023 Christopher Parrott for Pimoroni Ltd
#
# SPDX-License-Identifier: MIT

from .common import YukonModule, ADC_FLOAT, LOW, HIGH
from busio import UART
from digitalio import DigitalInOut
from collections import OrderedDict
from pimoroni_yukon.errors import OverTemperatureError
import struct

# LX-16A Protocol
FRAME_HEADER = 0x55
MOVE_TIME_WRITE = 1
MOVE_TIME_READ = 2
MOVE_TIME_WAIT_WRITE = 7
MOVE_TIME_WAIT_READ = 8
MOVE_START = 11
MOVE_STOP = 12
ID_WRITE = 13
ID_READ = 14
ANGLE_OFFSET_ADJUST = 17
ANGLE_OFFSET_WRITE = 18
ANGLE_OFFSET_READ = 19
ANGLE_LIMIT_WRITE = 20
ANGLE_LIMIT_READ = 21
VIN_LIMIT_WRITE = 22
VIN_LIMIT_READ = 23
TEMP_MAX_LIMIT_WRITE = 24
TEMP_MAX_LIMIT_READ = 25
TEMP_READ = 26
VIN_READ = 27
POS_READ = 28
SERVO_OR_MOTOR_MODE_WRITE = 29
SERVO_OR_MOTOR_MODE_READ = 30
LOAD_OR_UNLOAD_WRITE = 31
LOAD_OR_UNLOAD_READ = 32
LED_CTRL_WRITE = 33
LED_CTRL_READ = 34
LED_ERROR_WRITE = 35
LED_ERROR_READ = 36


def LobotCheckSum(buffer):
    checksum = 0
    length = buffer[3]
    last = length + 2
    for i in range(2, last):
        checksum += buffer[i]

    return ~checksum

def LobotAppendCheckSum(buffer):
    checksum = 0
    length = buffer[3]
    last = length + 2
    for i in range(2, last):
        checksum += buffer[i]

    buffer[last] = ~checksum

def LobotSerialServoMove(uart, id, position, time):
    if position < 0:
        position = 0
    if position > 1000:
        position = 1000

    buffer = bytearray(10)
    struct.pack_into("<BBBBBHH", buffer,
        FRAME_HEADER,
        FRAME_HEADER,
        id,
        len(buffer) - 3,
        MOVE_TIME_WRITE,
        position,
        time)
    LobotAppendCheckSum(buffer)
    uart.write(buffer)

def LobotSerialServoStopMove(uart, id):
    buffer = bytearray(6)
    struct.pack_into("<BBBBB", buffer,
        FRAME_HEADER,
        FRAME_HEADER,
        id,
        len(buffer) - 3,
        MOVE_STOP)
    LobotAppendCheckSum(buffer)
    uart.write(buffer)

def LobotSerialServoSetID(uart, old_id, new_id):
    buffer = bytearray(7)
    struct.pack_into("<BBBBBBB", buffer,
        FRAME_HEADER,
        FRAME_HEADER,
        old_id,
        len(buffer) - 3,
        ID_WRITE,
        new_id)
    LobotAppendCheckSum(buffer)

#ifdef LOBOT_DEBUG
    print("LOBOT SERVO ID WRITE")
    for debug_value_i in range(0, buffer[3] + 3):
        print(hex(buffer[debug_value_i]), end=":")
    print()
#endif
    uart.write(buffer)

def LobotSerialServoSetMode(uart, id, mode, speed):
    buffer = bytearray(10)
    struct.pack_into("<BBBBBBBH", buffer,
        FRAME_HEADER,
        FRAME_HEADER,
        id,
        len(buffer) - 3,
        SERVO_OR_MOTOR_MODE_WRITE,
        mode,
        0
        speed)
    LobotAppendCheckSum(buffer)

#ifdef LOBOT_DEBUG
    print("LOBOT SERVO Set Mode")
    for debug_value_i in range(0, buffer[3] + 3):
        print(hex(buffer[debug_value_i]), end=":")
    print()
#endif
    uart.write(buffer)


def LobotSerialServoLoad(uart, id):
    buffer = bytearray(7)
    struct.pack_into("<BBBBBBB", buffer,
        FRAME_HEADER,
        FRAME_HEADER,
        id,
        len(buffer) - 3,
        LOAD_OR_UNLOAD_WRITE,
        1)
    LobotAppendCheckSum(buffer)

#ifdef LOBOT_DEBUG
    print("LOBOT SERVO LOAD WRITE")
    for debug_value_i in range(0, buffer[3] + 3):
        print(hex(buffer[debug_value_i]), end=":")
    print()
#endif
    uart.write(buffer)

def LobotSerialServoUnload(uart, id):
    buffer = bytearray(7)
    struct.pack_into("<BBBBBBB", buffer,
        FRAME_HEADER,
        FRAME_HEADER,
        id,
        len(buffer) - 3,
        LOAD_OR_UNLOAD_WRITE,
        0)
    LobotAppendCheckSum(buffer)

#ifdef LOBOT_DEBUG
    print("LOBOT SERVO LOAD WRITE")
    for debug_value_i in range(0, buffer[3] + 3):
        print(hex(buffer[debug_value_i]), end=":")
    print()
#endif
    uart.write(buffer)


def LobotSerialServoReceiveHandle(uart):
    frameStarted = False
    frameCount = 0
    dataCount = 0
    dataLength = 2
    rxBuf = 0
    recvBuf = bytearray(32)
    i = 0

    while uart.in_waiting > 0:
        rxBuf = uart.read(1)[0]
        #delayMicroseconds(100);
        if not frameStarted:
            if rxBuf == FRAME_HEADER:
                frameCount += 1
                if frameCount == 2:
                    frameCount = 0
                    frameStarted = True
                    dataCount = 1
            else:
                frameStarted = False
                dataCount = 0
                frameCount = 0

        if frameStarted:
            recvBuf[dataCount] = rxBuf
            if dataCount == 3:
                dataLength = recvBuf[dataCount]
                if dataLength < 3 or dataCount > 7:
                    dataLength = 2
                    frameStarted = False
            dataCount += 1
            if dataCount == dataLength + 3:
        #ifdef LOBOT_DEBUG
                print("RECEIVE DATA:", end="")
                for i in range(0, dataCount):
                    print(hex(recvBuf[i]), end=":")
                    print()
        #endif

                if LobotCheckSum(recvBuf) == recvBuf[dataCount - 1]:
        #ifdef LOBOT_DEBUG
                    print("Check SUM OK!!", end="\n\n")
        #endif

                    frameStarted = False
                    #memcpy(ret, recvBuf + 4, dataLength)
                    return recvBuf[4:4 + dataLength]

    return None

def LobotSerialServoReadPosition(uart, id):
    count = 10000
    ret = 0

    buffer = bytearray(6)
    struct.pack_into("<BBBBB", buffer,
        FRAME_HEADER,
        FRAME_HEADER,
        id,
        len(buffer) - 3,
        POS_READ)
    LobotAppendCheckSum(buffer)

#ifdef LOBOT_DEBUG
    print("LOBOT SERVO Pos READ")
    for debug_value_i in range(0, buffer[3] + 3):
        print(hex(buffer[debug_value_i]), end=":")
    print()
#endif

    while uart.in_waiting > 0:
        uart.read(1)

    uart.write(buffer)

    while uart.in_waiting == 0:
        count -= 1
        if count < 0:
            return -1

    returned_buffer = LobotSerialServoReceiveHandle(uart)
    if returned_buffer is not None:
        ret = struct.unpack("<H", returned_buffer)
    else:
        ret = -1

#ifdef LOBOT_DEBUG
    print(ret)
#endif
    return ret

def LobotSerialServoReadVin(uart, id):
    count = 10000
    ret = 0

    buffer = bytearray(6)
    struct.pack_into("<BBBBB", buffer,
        FRAME_HEADER,
        FRAME_HEADER,
        id,
        len(buffer) - 3,
        VIN_READ)
    LobotAppendCheckSum(buffer)

    #ifdef LOBOT_DEBUG
    print("LOBOT SERVO VIN READ")
    for debug_value_i in range(0, buffer[3] + 3):
        print(hex(buffer[debug_value_i]), end=":")
    print()
    #endif

    while uart.in_waiting > 0:
        uart.read(1)

    uart.write(buffer)

    while uart.in_waiting == 0:
        count -= 1
        if count < 0:
            return -2048

    returned_buffer = LobotSerialServoReceiveHandle(uart)
    if returned_buffer is not None:
        ret = struct.unpack("<H", returned_buffer)
    else:
        ret = -2048

#ifdef LOBOT_DEBUG
        print(ret)
#endif
    return ret


class SerialServoModule(YukonModule):
    NAME = "Serial Bus Servo"
    DEFAULT_BAUDRATE = 115200
    TEMPERATURE_THRESHOLD = 50.0
    PROTOCOL_LOBOT_LX_16A = 0

    # | ADC1  | SLOW1 | SLOW2 | SLOW3 | Module               | Condition (if any)          |
    # |-------|-------|-------|-------|----------------------|-----------------------------|
    # | FLOAT | 1     | 0     | 0     | Serial Servo         |                             |
    @staticmethod
    def is_module(adc_level, slow1, slow2, slow3):
        return adc_level is ADC_FLOAT and slow1 is HIGH and slow2 is LOW and slow3 is LOW

    def __init__(self, baudrate=DEFAULT_BAUDRATE):
        super().__init__()

        self.__baudrate = baudrate

    def initialise(self, slot, adc1_func, adc2_func):
        try:
            # Create the serial object
            self.uart = UART(slot.FAST1, slot.FAST2, baudrate=self.__baudrate)
        except ValueError as e:
            raise type(e)("UART perhiperal already in use. Check that a module in another slot does not share the same UART perhiperal") from None

        # Create the direction pin objects
        self.__tx_to_data_en = DigitalInOut(slot.FAST3)
        self.__data_to_rx_en = DigitalInOut(slot.FAST4)

        # Pass the slot and adc functions up to the parent now that module specific initialisation has finished
        super().initialise(slot, adc1_func, adc2_func)

    def reset(self):
        self.__uart.reset_input_buffer()

        self.__tx_to_data_en.switch_to_output(True)  # Active low
        self.__data_to_rx_en.switch_to_output(True)  # Active low

    def read_temperature(self):
        return self.__read_adc2_as_temp()

    def monitor(self):
        temperature = self.read_temperature()
        if temperature > self.TEMPERATURE_THRESHOLD:
            raise OverTemperatureError(self.__message_header() + f"Temperature of {temperature}°C exceeded the limit of {self.TEMPERATURE_THRESHOLD}°C! Turning off output")

        # Run some user action based on the latest readings
        if self.__monitor_action_callback is not None:
            self.__monitor_action_callback(temperature)

        self.__max_temperature = max(temperature, self.__max_temperature)
        self.__min_temperature = min(temperature, self.__min_temperature)
        self.__avg_temperature += temperature

        self.__count_avg += 1

    def get_readings(self):
        return OrderedDict({
            "T_max": self.__max_temperature,
            "T_min": self.__min_temperature,
            "T_avg": self.__avg_temperature
        })

    def process_readings(self):
        if self.__count_avg > 0:
            self.__avg_temperature /= self.__count_avg

    def clear_readings(self):
        self.__max_temperature = float('-inf')
        self.__min_temperature = float('inf')
        self.__avg_temperature = 0

        self.__count_avg = 0

