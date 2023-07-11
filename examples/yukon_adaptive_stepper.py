from pimoroni_yukon import Yukon
from pimoroni_yukon.modules import DualMotorModule

# Create a Yukon object to begin using the board
yukon = Yukon()

# List to store the modules
motor_modules = []

try:
    # Create a Quad Servo Direct class for each populated module slot
    for slot in yukon.find_slots_with_module(DualMotorModule):
        stepper = DualMotorModule(DualMotorModule.STEPPER)
        yukon.register_with_slot(stepper, slot)
        motor_modules.append(stepper)

    # Initialise Yukon's registered modules
    yukon.initialise_modules(allow_unregistered=True)

    NUM_STEPPERS = len(motor_modules) * DualMotorModule.NUM_STEPPERS
    print(f"Up to {NUM_STEPPERS} steppers available")

    # Turn on the module power
    yukon.enable_main_output()

    # Enable the outputs on the regulated servo modules
    for module in motor_modules:
        try:
            module.enable()
        except AttributeError:
            # No enable function
            pass

    while not yukon.is_boot_pressed():

        # Update all the Steppers
        for module in motor_modules:
            module.stepper.onestep()

        yukon.monitored_sleep(0.01)

finally:
    # Put the board back into a safe state, regardless of how the program may have ended
    yukon.reset()

