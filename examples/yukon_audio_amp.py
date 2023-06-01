import time
from pimoroni_yukon import Yukon
from pimoroni_yukon.modules import AudioAmpModule

import audiobusio
import audiocore
import array
import time
import math
from audiocore import WaveFile

# Select the slot that the module is installed in
SLOT = 3

# Create a Yukon object to begin using the board
yukon = Yukon()

try:
    # Create an AudioAmpModule and register it with a slot on Yukon
    amp = AudioAmpModule()
    yukon.register_with_slot(amp, SLOT)

    # Initialise Yukon's registered modules
    yukon.initialise_modules(allow_unregistered=True)

    # Turn on the module power
    yukon.enable_main_output()

    # Enable the switched outputs
    amp.enable()
    amp.set_volume(0.3)

    wave_file_a = open("ahoy.wav", "rb")
    wave_a = WaveFile(wave_file_a)
    #wave_b = WaveFile(wave_file_b)
    i2s = audiobusio.I2SOut(amp.I2S_CLK, amp.I2S_FS, amp.I2S_DATA)
    #i2s.stop()

    sw_a_state = False
    sw_b_state = False
    last_sw_a_state = False
    last_sw_b_state = False
    while not yukon.is_boot_pressed():
        sw_a_state = yukon.is_pressed('A')
        sw_b_state = yukon.is_pressed('B')

        if sw_a_state is True and sw_a_state != last_sw_a_state:
            if not i2s.playing:
                i2s.play(wave_a, loop=False)
                amp.exit_soft_shutdown()  # This is currently needed after a second play, resulting in an 8.5m delay from sound starting to it being heard
                print("Playing")
            else:
                i2s.stop()
                print("Stopping")
        
        if sw_b_state is True and sw_b_state != last_sw_b_state:
            if not i2s.playing:
                #i2s.play(wave_b, loop=False)
                #amp.exit_soft_shutdown()  # This is currently needed after a second play, resulting in an 8.5m delay from sound starting to it being heard
                print("Playing")
            else:
                i2s.stop()
                print("Stopping")

        last_sw_a_state = sw_a_state
        last_sw_b_state = sw_b_state

        yukon.set_led('A', i2s.playing)

        yukon.monitored_sleep(0)  # Monitor for the shortest time possible

finally:
    # Put the board back into a safe state, regardless of how the program may have ended
    yukon.reset()
