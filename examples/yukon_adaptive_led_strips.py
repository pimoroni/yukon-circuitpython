import time
from pimoroni_yukon import Yukon
from pimoroni_yukon.modules import LEDStripModule
from rainbowio import colorwheel

STRIP_TYPE = LEDStripModule.NEOPIXEL  # change to LEDStripModule.DOTSTAR for APA102 style strips
SPEED = 2
LEDS_PER_STRIP = 60
BRIGHTNESS = 1.0

# Create a Yukon object to begin using the board
yukon = Yukon()

# List to store the strips
strips = []


def update_rainbow(strip, offset):
    for px in range(strip.pixels.n):
        rc_index = (px * 256 // strip.pixels.n) + offset
        col = colorwheel(rc_index & 255)
        strip.pixels[px] = col

    strip.pixels.show()


try:
    # Create a LED Strip class for each populated module slot
    for slot in yukon.find_slots_with_module(LEDStripModule):
        strip = LEDStripModule(STRIP_TYPE, LEDS_PER_STRIP, BRIGHTNESS)
        yukon.register_with_slot(strip, slot)
        strips.append(strip)

    # Initialise Yukon's registered modules
    yukon.initialise_modules(allow_unregistered=True)

    # Turn on the module power
    yukon.enable_main_output()

    # Enable each strip module's regulator
    for strip in strips:
        strip.enable()

    offset = 0
    while not yukon.is_boot_pressed():
        for strip in strips:
            update_rainbow(strip, offset)

        offset += SPEED
        if offset >= 255:
            offset -= 255

        yukon.monitored_sleep(0.1)

finally:
    # Put the board back into a safe state, regardless of how the program may have ended
    yukon.reset()
