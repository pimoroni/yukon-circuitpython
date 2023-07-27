from pimoroni_yukon import Yukon
from pimoroni_yukon.modules import DualMotorModule
import adafruit_motor.stepper

# Create a Yukon object to begin using the board
yukon = Yukon()

# Select the slot that the module is installed in
SLOT = 3
STEPS = 400

try:
    stepper = DualMotorModule(DualMotorModule.STEPPER)
    yukon.register_with_slot(stepper, SLOT)

    # Initialise Yukon's registered modules
    yukon.initialise_modules(allow_unregistered=True)

    # Turn on the module power
    yukon.enable_main_output()
    # Enable the modules motor output
    stepper.enable()

    yukon.set_led('A', True)

    while not yukon.is_boot_pressed():
        if yukon.is_pressed('A'):
            [stepper.stepper.onestep(style=adafruit_motor.stepper.MICROSTEP) for _ in range(STEPS)]
        if yukon.is_pressed('B'):
            [stepper.stepper.onestep(style=adafruit_motor.stepper.MICROSTEP, direction=adafruit_motor.stepper.BACKWARD) for _ in range(STEPS)]
        yukon.monitored_sleep(0)

finally:
    # Put the board back into a safe state, regardless of how the program may have ended
    yukon.reset()
