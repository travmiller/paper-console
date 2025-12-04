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
    Supports both short press and long press (5 seconds) callbacks.
    """
    
    def __init__(self, pin: int = 18):
        self.pin = pin
        self.callback = None
        self.long_press_callback = None
        self.long_press_duration = 5.0  # 5 seconds for long press
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
                label="button_event"
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
        """Waits for button events and detects short vs long press."""
        last_press_time = 0
        debounce_interval = 2.0  # 2s debounce

        while self.monitoring and self.event_handle:
            try:
                # read_event blocks until an event occurs (falling edge = button pressed)
                event_id = self.event_handle.read_event()
                
                if event_id == GPIOEVENT_EVENT_FALLING_EDGE:
                    press_start_time = time.time()
                    
                    # Check debounce
                    if press_start_time - last_press_time < debounce_interval:
                        print(f"[BUTTON] Ignored press (debounce: {press_start_time - last_press_time:.3f}s)")
                        continue
                    
                    print("[BUTTON] Button pressed, waiting for release or long press...")
                    
                    # Wait for button release (or long press timeout)
                    is_long_press = False
                    button_still_pressed = True
                    
                    while time.time() - press_start_time < self.long_press_duration:
                        # Check if button is still pressed (pin is LOW when pressed, HIGH when released)
                        try:
                            # Use event handle's read_value() method
                            pin_value = self.event_handle.read_value()
                            if pin_value == 1:  # Button released (pulled HIGH)
                                button_still_pressed = False
                                break
                        except Exception as e:
                            print(f"[BUTTON] Error reading pin state: {e}")
                            # If we can't read, assume button was released
                            button_still_pressed = False
                            break
                        time.sleep(0.1)
                    
                    # If we exited the loop and button is still pressed, it's a long press
                    if button_still_pressed:
                        is_long_press = True
                        print(f"[BUTTON] Long press detected! (held for {time.time() - press_start_time:.1f}s)")
                    else:
                        press_duration = time.time() - press_start_time
                        print(f"[BUTTON] Short press detected! (held for {press_duration:.1f}s)")
                    
                    last_press_time = time.time()
                    
                    if is_long_press:
                        if self.long_press_callback:
                            try:
                                self.long_press_callback()
                            except Exception as e:
                                print(f"[BUTTON] Long press callback error: {e}")
                    else:
                        if self.callback:
                            try:
                                self.callback()
                            except Exception as e:
                                print(f"[BUTTON] Callback error: {e}")
                            
            except Exception as e:
                print(f"[BUTTON] Monitor error: {e}")
                # Sleep briefly to avoid tight loop on persistent error
                time.sleep(1)

    def set_callback(self, callback: Callable[[], None]):
        """Register a function to be called when the button is pressed (short press)."""
        self.callback = callback
    
    def set_long_press_callback(self, callback: Callable[[], None]):
        """Register a function to be called when the button is held for 5 seconds."""
        self.long_press_callback = callback

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

