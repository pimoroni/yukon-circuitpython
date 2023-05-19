from pimoroni_yukon import Yukon
from pimoroni_yukon.modules import LEDStripModule
from rainbowio import colorwheel
import asyncio

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


async def check_system():
    while True:
        print(yukon.read_current())
        await asyncio.sleep(0.001)  # Don't forget the await!


async def logic():  # Don't forget the async!
    # Go through each Yukon slot, and detect which have LED strips attached
    for slot in range(1, yukon.NUM_SLOTS + 1):  # Loop from 1 to 6
        detected = yukon.detect_module(slot)
        if detected is LEDStripModule:
            strip = LEDStripModule(STRIP_TYPE, LEDS_PER_STRIP, BRIGHTNESS)
            yukon.register_with_slot(strip, slot)
            strips.append(strip)

    # Initialise Yukon's registered modules
    yukon.initialise_modules(allow_unregistered=True)

    # Turn on the module power
    yukon.enable_main_output()
    print("Output Enabled")

    # Enable each strip module's regulator
    for strip in strips:
        strip.enable()

    offset = 0
    while True:
        for strip in strips:
            update_rainbow(strip, offset)

        offset += SPEED
        if offset >= 255:
            offset -= 255

        await asyncio.sleep(0.1)  # Don't forget the await!


async def main():
    main_task = asyncio.create_task(logic())
    background_task = asyncio.create_task(check_system())

    await asyncio.gather(main_task, background_task)  # Don't forget "await"!
    print("done")


try:
    asyncio.run(main())
finally:
    # Put the board back into a safe state, regardless of how the program may have ended
    yukon.reset()
    print("Output Disabled")
