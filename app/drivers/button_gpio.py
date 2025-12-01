import threading
import time
import os
from typing import Callable, Optional

# Try to import our ioctl driver
GPIO_AVAILABLE = False
try:
    from app.drivers.gpio_ioctl import (
        GpioChip, 
        GPIOHANDLE_REQUEST_INPUT, 
        GPIOHANDLE_REQUEST_BIAS_PULL_UP,
        GPIOEVENT_REQUEST_FALLING_EDGE,
        GPIOEVENT_EVENT_FALLING_EDGE
    )
    if os.path.exists("/dev/gpiochip0"):
        GPIO_AVAILABLE = True
    else:
        print("[BUTTON] /dev/gpiochip0 not found")
except ImportError:
    print("[BUTTON] ioctl GPIO driver not available")
except Exception as e:
    print(f"[BUTTON] Error importing GPIO driver: {e}")

class ButtonDriver:
    """
    Driver for a momentary push button connected to GPIO.
    Uses ioctl interrupts to detect presses (falling edge).
    """
    
    def __init__(self, pin: int = 18):
        self.pin = pin
        self.callback = None
        self.monitoring = False
        self.monitor_thread = None
        self.gpio_available = GPIO_AVAILABLE
        
        self.chip = None
        self.event_handle = None
        
        if not self.gpio_available:
            print("[BUTTON] Running in fallback mode (GPIO not available)")
            return
            
        try:
            self.chip = GpioChip("/dev/gpiochip0")
            
            # Request event monitoring for the button pin
            # Input + Pull Up + Falling Edge detection (assuming button connects to GND)
            handle_flags = GPIOHANDLE_REQUEST_INPUT | GPIOHANDLE_REQUEST_BIAS_PULL_UP
            event_flags = GPIOEVENT_REQUEST_FALLING_EDGE
            
            self.event_handle = self.chip.request_event(
                self.pin, 
                handle_flags, 
                event_flags, 
                label="button_input"
            )
            
            print(f"[BUTTON] Initialized on GPIO {self.pin}")
            
            # Start monitoring thread
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            
        except Exception as e:
            print(f"[BUTTON ERROR] Failed to initialize: {e}")
            self.gpio_available = False
            self.cleanup()

    def _monitor_loop(self):
        """Waits for button events."""
        while self.monitoring and self.event_handle:
            try:
                # read_event blocks until an event occurs
                event_id = self.event_handle.read_event()
                
                if event_id == GPIOEVENT_EVENT_FALLING_EDGE:
                    print("[BUTTON] Button pressed!")
                    if self.callback:
                        try:
                            # Run callback in a separate thread or async task if needed, 
                            # but here we just call it directly. 
                            # If the callback is async, it needs to be scheduled.
                            self.callback() 
                        except Exception as e:
                            print(f"[BUTTON] Callback error: {e}")
                            
            except Exception as e:
                print(f"[BUTTON] Monitor error: {e}")
                # Sleep briefly to avoid tight loop on persistent error
                time.sleep(1)

    def set_callback(self, callback: Callable[[], None]):
        """Register a function to be called when the button is pressed."""
        self.callback = callback

    def cleanup(self):
        self.monitoring = False
        # The read_event call is blocking, so the thread might not exit immediately 
        # unless we interrupt it or close the fd.
        
        if self.event_handle:
            self.event_handle.close()
            self.event_handle = None
            
        if self.chip:
            self.chip.close()
            self.chip = None
            
        print("[BUTTON] Cleaned up")

