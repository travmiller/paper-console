import platform
from typing import Callable, Optional, List
import threading
import time
import os

# Try to import our new ioctl-based driver
GPIO_AVAILABLE = False
try:
    from app.drivers.gpio_ioctl import (
        GpioChip, 
        GPIOHANDLE_REQUEST_INPUT, 
        GPIOHANDLE_REQUEST_OUTPUT,
        GPIOHANDLE_REQUEST_BIAS_PULL_UP,
        GPIOHANDLE_REQUEST_ACTIVE_LOW
    )
    # Check if gpiochip0 exists
    if os.path.exists("/dev/gpiochip0"):
        GPIO_AVAILABLE = True
    else:
        print("[DIAL] /dev/gpiochip0 not found (not on Raspberry Pi?)")
except ImportError:
    print("[DIAL] ioctl GPIO driver not available (not on Linux?)")
except Exception as e:
    print(f"[DIAL] Error importing GPIO driver: {e}")

class DialDriver:
    """
    Real hardware driver for 1-pole 8-position rotary switch.
    Reads GPIO pins to determine the current position using Linux ioctl interface.
    
    Wiring assumption:
    - The rotary switch has 8 positions (1-8)
    - Each position connects a common pin to a different GPIO pin
    - Common pin connected to GND
    - Position pins connected to GPIO pins with pull-up resistors
    """
    
    def __init__(self, gpio_pins: Optional[list] = None, common_pin: Optional[int] = None):
        """
        Initialize GPIO dial driver.
        
        Args:
            gpio_pins: List of 8 GPIO pin numbers for positions 1-8 (BCM numbering)
                      Default: [5, 6, 13, 19, 26, 16, 20, 21] (common GPIO pins)
            common_pin: GPIO pin for common connection (if using separate common pin)
                       If None, assumes common is GND
        """
        self.current_position = 1
        self.callbacks = []
        self.monitoring = False
        self.monitor_thread = None
        
        # Default GPIO pins (BCM numbering) - adjust based on your wiring
        if gpio_pins is None:
            self.gpio_pins = [5, 6, 13, 19, 26, 16, 20, 21]
        else:
            if len(gpio_pins) != 8:
                raise ValueError("Must provide exactly 8 GPIO pins for 8 positions")
            self.gpio_pins = gpio_pins
        
        self.common_pin = common_pin
        self.gpio_available = GPIO_AVAILABLE
        
        self.chip = None
        self.input_handle = None
        self.common_handle = None

        if not self.gpio_available:
            print("[DIAL] Running in fallback mode (GPIO not available)")
            print("[DIAL] Use set_position() to simulate dial changes")
            return
        
        try:
            # Initialize Chip
            self.chip = GpioChip("/dev/gpiochip0")
            
            # Request all 8 position pins as INPUT with PULL_UP
            # We use the built-in pull-ups so when switch connects to GND (Common), it reads 0
            flags = GPIOHANDLE_REQUEST_INPUT | GPIOHANDLE_REQUEST_BIAS_PULL_UP
            self.input_handle = self.chip.request_lines(self.gpio_pins, flags, label="dial_input")
            
            # Set up common pin if specified
            if self.common_pin is not None:
                # Common pin as Output, initialized to LOW (GND)
                # Active Low means writing 1 sets it LOW? No, usually:
                # Standard output: 0=Low, 1=High.
                # If we want it to be GND, we set it to 0.
                flags_common = GPIOHANDLE_REQUEST_OUTPUT
                self.common_handle = self.chip.request_lines([self.common_pin], flags_common, label="dial_common")
                self.common_handle.set_values([0])
            
            # Read initial position
            self.current_position = self._read_gpio_position()
            print(f"[DIAL] Initialized at position {self.current_position}")
            
            # Start monitoring thread for callbacks
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_position, daemon=True)
            self.monitor_thread.start()
            
        except Exception as e:
            print(f"[DIAL ERROR] Failed to initialize GPIO: {e}")
            print("[DIAL] Falling back to mock mode")
            self.gpio_available = False
            self.cleanup()
    
    def _read_gpio_position(self) -> int:
        """Read the current dial position from GPIO pins."""
        if not self.gpio_available or not self.input_handle:
            return self.current_position
        
        try:
            # Get values of all 8 pins
            values = self.input_handle.get_values()
            
            # We expect one pin to be LOW (0) if selected (because of pull-up and connection to GND)
            # All others should be HIGH (1)
            for i, val in enumerate(values, start=1):
                if val == 0:
                    return i
            
            # If no pin is LOW, return current position (switch might be between positions)
            return self.current_position
            
        except Exception as e:
            print(f"[DIAL ERROR] Failed to read GPIO: {e}")
            return self.current_position
    
    def _monitor_position(self):
        """Background thread to monitor dial position changes."""
        last_position = self.current_position
        
        while self.monitoring:
            try:
                new_position = self._read_gpio_position()
                
                if new_position != last_position:
                    self.current_position = new_position
                    print(f"[DIAL] Position changed to {new_position}")
                    
                    # Notify callbacks
                    for cb in self.callbacks:
                        try:
                            cb(new_position)
                        except Exception as e:
                            print(f"[DIAL] Callback error: {e}")
                    
                    last_position = new_position
                
                time.sleep(0.1)  # Check every 100ms
                
            except Exception as e:
                print(f"[DIAL] Monitor error: {e}")
                time.sleep(1)
    
    def register_callback(self, callback: Callable[[int], None]):
        """Register a function to be called when the dial changes."""
        self.callbacks.append(callback)
    
    def read_position(self) -> int:
        """Read the current dial position."""
        if self.gpio_available:
            # Update from GPIO
            self.current_position = self._read_gpio_position()
        return self.current_position
    
    def set_position(self, position: int):
        """
        Manually set position (for testing/debugging).
        Note: This doesn't actually change the hardware, just the software state.
        """
        if 1 <= position <= 8:
            if self.current_position != position:
                self.current_position = position
                print(f"[DIAL] Position set to {position} (software override)")
                # Notify listeners
                for cb in self.callbacks:
                    try:
                        cb(position)
                    except Exception as e:
                        print(f"[DIAL] Callback error: {e}")
        else:
            print(f"[DIAL] Invalid position {position}")
    
    def cleanup(self):
        """Clean up GPIO resources."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
        
        if self.input_handle:
            self.input_handle.close()
            self.input_handle = None
            
        if self.common_handle:
            self.common_handle.close()
            self.common_handle = None
            
        if self.chip:
            self.chip.close()
            self.chip = None
            
        print("[DIAL] GPIO cleaned up")
