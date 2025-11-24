import platform
from typing import Callable, Optional
import threading
import time

# Only import RPi.GPIO on Raspberry Pi
GPIO_AVAILABLE = False
GPIO = None

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    print("[DIAL] RPi.GPIO not available (not running on Raspberry Pi)")

class DialDriver:
    """
    Real hardware driver for 1-pole 8-position rotary switch.
    Reads GPIO pins to determine the current position.
    
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
        
        if not GPIO_AVAILABLE or GPIO is None:
            print("[DIAL] Running in fallback mode (RPi.GPIO not available)")
            print("[DIAL] Use set_position() to simulate dial changes")
            return
        
        try:
            # Set up GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            # Set up each position pin as input with pull-up
            for pin in self.gpio_pins:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            # Set up common pin if specified
            if self.common_pin is not None:
                GPIO.setup(self.common_pin, GPIO.OUT)
                GPIO.output(self.common_pin, GPIO.LOW)
            
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
            global GPIO_AVAILABLE
            GPIO_AVAILABLE = False
    
    def _read_gpio_position(self) -> int:
        """Read the current dial position from GPIO pins."""
        if not GPIO_AVAILABLE:
            return self.current_position
        
        try:
            # Check each position pin (1-8)
            # When a position is selected, that pin should read LOW (connected to GND)
            for i, pin in enumerate(self.gpio_pins, start=1):
                if GPIO.input(pin) == GPIO.LOW:
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
        if GPIO_AVAILABLE:
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
        
        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup()
                print("[DIAL] GPIO cleaned up")
            except Exception as e:
                print(f"[DIAL] Cleanup error: {e}")

