import time
import math
from pimoroni_yukon import Yukon
from pimoroni_yukon.modules import BigMotorModule

SPEED = 5             # The speed that the motors will cycle at
UPDATES = 50          # How many times to update LEDs and Servos per second
MOTOR_EXTENT = 1.0   # How far from zero to drive the motors

# Create a Yukon object to begin using the board
yukon = Yukon()

# List to store the modules
motor_modules = []

try:
    # Create a Big Motor Module instance for each populated module slot
    for slot in yukon.find_slots_with_module(BigMotorModule):
        big_motor = BigMotorModule()
        yukon.register_with_slot(big_motor, slot)
        motor_modules.append(big_motor)

    # Initialise Yukon's registered modules
    yukon.initialise_modules(allow_unregistered=True)

    NUM_MOTORS = len(motor_modules)
    print(f"Up to {NUM_MOTORS} motors available")

    # Turn on the module power
    yukon.enable_main_output()

    # Enable the outputs on the regulated servo modules
    for module in motor_modules:
        try:
            module.enable()
        except AttributeError:
            # No enable function
            pass

    offset = 0
    while not yukon.is_boot_pressed():
        offset += SPEED / 1000.0

        # Update all the Motors
        i = 0
        for module in motor_modules:
            angle = ((i / NUM_MOTORS) + offset) * math.pi * 2
            module.motor.throttle = (math.sin(angle) * MOTOR_EXTENT)
            i += 1

        yukon.monitored_sleep(1.0 / UPDATES)

finally:
    # Put the board back into a safe state, regardless of how the program may have ended
    yukon.reset()
