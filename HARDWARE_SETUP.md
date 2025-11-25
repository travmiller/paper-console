# Hardware Setup Guide

This guide will help you set up the physical hardware for your Paper Console.

## Prerequisites

1. **Raspberry Pi Zero 2 W** with Raspberry Pi OS Lite installed
2. **Thermal Printer** (QR204/CSN-A2 or compatible 58mm TTL/USB thermal printer)
3. **1-Pole 8-Position Rotary Switch**
4. **Momentary Push Button** (optional, for manual trigger)

## Installation

### 1. Install Dependencies

On your Raspberry Pi, install the required Python packages:

```bash
pip install -r requirements.txt
```

This will install `pyserial` and `RPi.GPIO` along with other dependencies.

### 2. Enable Serial Interface

Enable the serial interface on your Raspberry Pi:

```bash
sudo raspi-config
```

Navigate to:
- **Interface Options** → **Serial Port**
- Enable serial port hardware
- Disable serial login shell (if prompted)

Reboot after making changes:
```bash
sudo reboot
```

### 3. Connect the Thermal Printer

#### USB Connection
If your printer connects via USB:
1. Connect the printer to a USB port on the Raspberry Pi
2. The device should appear as `/dev/ttyUSB0` or `/dev/ttyACM0`
3. Check available serial devices: `ls -l /dev/tty*`

#### TTL Serial Connection
If your printer uses TTL serial:
1. Connect:
   - **VCC** → 5V (Pin 2 or 4)
   - **GND** → Ground (Pin 6 or any GND)
   - **RX** → GPIO 14 (TXD, Pin 8) - **Note:** You may need a level shifter if printer is 3.3V
   - **TX** → GPIO 15 (RXD, Pin 9)
2. Enable serial in `raspi-config` (see step 2)
3. The device will appear as `/dev/serial0` or `/dev/ttyAMA0`

#### Configure Printer Port (if needed)
If your printer is on a different port, you can modify `app/drivers/printer_serial.py`:

```python
printer = PrinterDriver(width=32, port="/dev/ttyUSB0", baudrate=19200)
```

Common baud rates: 9600, 19200, 38400, 115200 (check your printer manual)

### 4. Connect the Rotary Switch

The 1-pole 8-position rotary switch needs to be connected to GPIO pins:

#### Wiring
- **Common terminal** → GND
- **Position 1** → GPIO 5 (Pin 29)
- **Position 2** → GPIO 6 (Pin 31)
- **Position 3** → GPIO 13 (Pin 33)
- **Position 4** → GPIO 19 (Pin 35)
- **Position 5** → GPIO 26 (Pin 37)
- **Position 6** → GPIO 16 (Pin 36)
- **Position 7** → GPIO 20 (Pin 38)
- **Position 8** → GPIO 21 (Pin 40)

**Note:** These are the default GPIO pins. You can customize them in `app/drivers/dial_gpio.py`:

```python
dial = DialDriver(gpio_pins=[5, 6, 13, 19, 26, 16, 20, 21])
```

#### How It Works
- Each position connects the common terminal to a different GPIO pin
- The driver uses pull-up resistors (internal to Raspberry Pi)
- When a position is selected, that GPIO pin reads LOW (connected to GND)
- The driver continuously monitors all pins to detect position changes

### 5. Connect the Push Button (Optional)

The push button can be connected to trigger the current channel:

#### Wiring
- **One terminal** → GPIO 18 (Pin 12)
- **Other terminal** → GND
- Add a 10kΩ pull-up resistor between GPIO 18 and 3.3V (or use internal pull-up)

#### Software Integration
You'll need to add a GPIO interrupt handler. Create a simple script or add to `app/main.py`:

```python
import RPi.GPIO as GPIO

BUTTON_PIN = 18

def button_callback(channel):
    """Called when button is pressed."""
    asyncio.create_task(trigger_current_channel())

# In lifespan startup:
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING, callback=button_callback, bounce_time=200)
```

## Network & Auto-Start Setup

To make the device accessible via `http://pc-1.local` (without a port number) and ensure it starts automatically on boot:

1.  **Copy the setup script to your Pi:**
    (You can do this via scp or just create the file on the Pi)

2.  **Run the setup script:**
    ```bash
    cd /home/pi/paper-console
    chmod +x scripts/setup_pi.sh
    sudo scripts/setup_pi.sh
    ```

3.  **Follow the prompts:**
    - Enter your desired hostname (default: `pc-1`)
    - The script will install Nginx (web proxy), Avahi (mDNS), and configure the systemd service.

4.  **Access the device:**
    Open your browser and go to `http://pc-1.local` (or whatever hostname you chose).

## Testing

### Test the Printer

1. Start the server:
```bash
uvicorn app.main:app --reload --port 8000
```

2. Send a test print:
```bash
curl -X POST http://localhost:8000/debug/print-test
```

You should see output on your thermal printer.

### Test the Rotary Switch

1. Check current position:
```bash
curl http://localhost:8000/status
```

2. Turn the dial and check again - the `current_channel` should update.

3. You can also manually set position for testing:
```bash
curl -X POST http://localhost:8000/action/dial/3
```

## Troubleshooting

### Printer Not Working

1. **Check serial port:**
   ```bash
   ls -l /dev/tty*
   dmesg | grep tty
   ```

2. **Check permissions:**
   ```bash
   sudo usermod -a -G dialout $USER
   # Log out and back in
   ```

3. **Test serial connection:**
   ```bash
   python3 -c "import serial; s = serial.Serial('/dev/ttyUSB0', 19200); s.write(b'Test\n'); s.close()"
   ```

4. **Check baud rate:** Verify your printer's baud rate matches the driver (default: 19200)

### Dial Not Reading Positions

1. **Check wiring:** Ensure common terminal is connected to GND
2. **Test GPIO pins:**
   ```bash
   python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); GPIO.setup(5, GPIO.IN, pull_up_down=GPIO.PUD_UP); print(GPIO.input(5))"
   ```
   Should print `1` (HIGH) when position 1 is not selected, `0` (LOW) when selected.

3. **Check for shorts:** Ensure no two position pins are shorted together

4. **Verify switch continuity:** Use a multimeter to verify the switch works correctly

### Platform Detection

The system automatically detects if it's running on a Raspberry Pi by checking for `/proc/device-tree/model`. If detection fails:

1. Check you're running Raspberry Pi OS (not generic Linux)
2. Manually force hardware mode by modifying `app/main.py`:
   ```python
   _is_raspberry_pi = True  # Force hardware mode
   ```

## Next Steps

Once hardware is working:

1. Configure your channels via the web UI at `http://localhost:8000/docs` or the React frontend
2. Set up scheduled printing for specific channels
3. Test each module type (news, weather, calendar, etc.)
4. Fine-tune printer settings (width, encoding) if needed

## GPIO Pin Reference

For Raspberry Pi Zero 2 W (40-pin header):

```
    3.3V  [1]  [2]  5V
   GPIO2  [3]  [4]  5V
   GPIO3  [5]  [6]  GND
   GPIO4  [7]  [8]  GPIO14 (TXD)
     GND  [9]  [10] GPIO15 (RXD)
  GPIO17 [11]  [12] GPIO18
  GPIO27 [13]  [14] GND
  GPIO22 [15]  [16] GPIO23
    3.3V [17]  [18] GPIO24
  GPIO10 [19]  [20] GND
   GPIO9 [21]  [22] GPIO25
  GPIO11 [23]  [24] GPIO8
     GND [25]  [26] GPIO7
   GPIO0 [27]  [28] GPIO1
   GPIO5 [29]  [30] GND
   GPIO6 [31]  [32] GPIO12
  GPIO13 [33]  [34] GND
  GPIO19 [35]  [36] GPIO16
  GPIO26 [37]  [38] GPIO20
     GND [39]  [40] GPIO21
```

## Safety Notes

- **Double-check all connections** before powering on
- **Use appropriate voltage levels** - Raspberry Pi GPIO is 3.3V, not 5V tolerant
- **Add current-limiting resistors** if connecting LEDs or other components
- **Test with a multimeter** before connecting to GPIO pins
- **Start with low-power testing** before connecting the printer

