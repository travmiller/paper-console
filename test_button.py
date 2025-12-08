import time
from app.drivers.gpio_ioctl import (
    GpioChip,
    GPIOHANDLE_REQUEST_INPUT,
    GPIOHANDLE_REQUEST_BIAS_PULL_UP,
)

print("Testing GPIO 3 (Pin 5)...")
print("Press the button now (Ctrl+C to exit)")

try:
    chip = GpioChip("/dev/gpiochip0")
    # Request GPIO 3 as input with pull-up
    handle = chip.request_lines(
        [3],
        GPIOHANDLE_REQUEST_INPUT | GPIOHANDLE_REQUEST_BIAS_PULL_UP,
        label="test_button",
    )

    last_val = -1
    while True:
        # Read value (0 = Pressed/GND, 1 = Released/3.3V)
        values = handle.get_values()
        val = values[0]

        if val != last_val:
            state = "PRESSED" if val == 0 else "RELEASED"
            print(f"Button State: {state} (Value: {val})")
            last_val = val

        time.sleep(0.1)

except Exception as e:
    print(f"Error: {e}")
finally:
    if "handle" in locals():
        handle.close()
    if "chip" in locals():
        chip.close()
