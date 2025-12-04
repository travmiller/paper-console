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
        GPIOEVENT_REQUEST_BOTH_EDGES,
        GPIOEVENT_EVENT_FALLING_EDGE,
        GPIOEVENT_EVENT_RISING_EDGE
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
    Uses edge detection for both press and release.
    Supports short press and long press (5 seconds) callbacks.
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
        
        # Retry logic for GPIO initialization (handles "device busy" after service restart)
        max_retries = 5
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                self.chip = GpioChip("/dev/gpiochip0")
                
                # Request BOTH edges - falling (press) and rising (release)
                handle_flags = GPIOHANDLE_REQUEST_INPUT | GPIOHANDLE_REQUEST_BIAS_PULL_UP
                event_flags = GPIOEVENT_REQUEST_BOTH_EDGES
                
                self.event_handle = self.chip.request_event(
                    self.pin, 
                    handle_flags, 
                    event_flags, 
                    label="button"
                )
                
                print(f"[BUTTON] Initialized on GPIO {self.pin}")
                
                # Start monitoring thread
                self.monitoring = True
                self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
                self.monitor_thread.start()
                return
                
            except OSError as e:
                if e.errno == 16 and attempt < max_retries - 1:  # EBUSY
                    print(f"[BUTTON] GPIO busy, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(retry_delay)
                    if self.chip:
                        self.chip.close()
                        self.chip = None
                else:
                    print(f"[BUTTON ERROR] Failed to initialize: {e}")
                    self.gpio_available = False
                    self.cleanup()
                    return
            except Exception as e:
                print(f"[BUTTON ERROR] Failed to initialize: {e}")
                self.gpio_available = False
                self.cleanup()
                return

    def _monitor_loop(self):
        """Monitor for button press/release events."""
        press_start_time = None
        last_event_time = 0
        debounce_ms = 50  # 50ms debounce
        
        while self.monitoring and self.event_handle:
            try:
                event_id = self.event_handle.read_event()
                current_time = time.time()
                
                # Debounce: ignore events too close together
                if (current_time - last_event_time) < (debounce_ms / 1000.0):
                    continue
                last_event_time = current_time
                
                if event_id == GPIOEVENT_EVENT_FALLING_EDGE:
                    # Button pressed (pulled LOW)
                    press_start_time = current_time
                    print("[BUTTON] Pressed")
                    
                elif event_id == GPIOEVENT_EVENT_RISING_EDGE:
                    # Button released (pulled HIGH)
                    if press_start_time is not None:
                        duration = current_time - press_start_time
                        press_start_time = None
                        
                        print(f"[BUTTON] Released after {duration:.1f}s")
                        
                        if duration >= self.long_press_duration:
                            print("[BUTTON] Long press detected!")
                            if self.long_press_callback:
                                try:
                                    self.long_press_callback()
                                except Exception as e:
                                    print(f"[BUTTON] Long press callback error: {e}")
                        else:
                            print("[BUTTON] Short press detected!")
                            if self.callback:
                                try:
                                    self.callback()
                                except Exception as e:
                                    print(f"[BUTTON] Short press callback error: {e}")
                            
            except Exception as e:
                if self.monitoring:  # Only log if we're still supposed to be running
                    print(f"[BUTTON] Monitor error: {e}")
                    time.sleep(1)

    def set_callback(self, callback: Callable[[], None]):
        """Register a function to be called on short press."""
        self.callback = callback
    
    def set_long_press_callback(self, callback: Callable[[], None]):
        """Register a function to be called on long press (5+ seconds)."""
        self.long_press_callback = callback

    def cleanup(self):
        self.monitoring = False
        
        if self.event_handle:
            self.event_handle.close()
            self.event_handle = None
            
        if self.chip:
            self.chip.close()
            self.chip = None
            
        print("[BUTTON] Cleaned up")
