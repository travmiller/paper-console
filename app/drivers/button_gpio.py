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
        GPIOEVENT_EVENT_RISING_EDGE,
    )

    if os.path.exists("/dev/gpiochip0"):
        GPIO_AVAILABLE = True
except Exception:
    pass


class ButtonDriver:
    """
    Driver for a momentary push button connected to GPIO.
    Uses edge detection for press and release.
    Supports:
      - Short press (< 5 seconds)
      - Long press (5-15 seconds) - triggers WHILE HOLDING
      - Factory reset (15+ seconds) - triggers WHILE HOLDING
    """

    def __init__(self, pin: int = 18):
        self.pin = pin
        self.callback = None
        self.long_press_callback = None
        self.factory_reset_callback = None
        self.long_press_duration = 5.0  # 5 seconds for long press (AP mode)
        self.factory_reset_duration = 15.0  # 15 seconds for factory reset
        self.monitoring = False
        self.monitor_thread = None
        self.hold_check_thread = None
        self.gpio_available = GPIO_AVAILABLE
        self._initialization_failed = False
        self.is_pressed = False
        self.press_start_time = None
        self.triggered_actions = (
            set()
        )  # Track which hold actions have fired for this press

        self.chip = None
        self.event_handle = None

        if not self.gpio_available:
            return

        # Retry logic for GPIO initialization (handles "device busy" after service restart)
        max_retries = 10
        retry_delay = 2.0

        for attempt in range(max_retries):
            try:
                self.chip = GpioChip("/dev/gpiochip0")

                handle_flags = (
                    GPIOHANDLE_REQUEST_INPUT | GPIOHANDLE_REQUEST_BIAS_PULL_UP
                )
                event_flags = GPIOEVENT_REQUEST_BOTH_EDGES

                self.event_handle = self.chip.request_event(
                    self.pin, handle_flags, event_flags, label="button"
                )

                # Start monitoring thread
                self.monitoring = True
                self.monitor_thread = threading.Thread(
                    target=self._monitor_loop, daemon=True
                )
                self.monitor_thread.start()

                # Start hold checker thread
                self.hold_check_thread = threading.Thread(
                    target=self._hold_check_loop, daemon=True
                )
                self.hold_check_thread.start()
                return

            except OSError as e:
                if e.errno == 16 and attempt < max_retries - 1:  # EBUSY
                    time.sleep(retry_delay)
                    if self.chip:
                        self.chip.close()
                        self.chip = None
                else:
                    self._initialization_failed = True
                    self.gpio_available = False
                    self.cleanup()
                    self._schedule_background_reinit()
                    return
            except Exception:
                self._initialization_failed = True
                self.gpio_available = False
                self.cleanup()
                self._schedule_background_reinit()
                return

    def _schedule_background_reinit(self):
        """Schedule a background thread to retry GPIO initialization."""

        def retry_init():
            retry_interval = 30
            max_bg_retries = 10

            for attempt in range(max_bg_retries):
                time.sleep(retry_interval)

                try:
                    self.chip = GpioChip("/dev/gpiochip0")
                    handle_flags = (
                        GPIOHANDLE_REQUEST_INPUT | GPIOHANDLE_REQUEST_BIAS_PULL_UP
                    )
                    event_flags = GPIOEVENT_REQUEST_BOTH_EDGES

                    self.event_handle = self.chip.request_event(
                        self.pin, handle_flags, event_flags, label="button"
                    )

                    self.gpio_available = True
                    self._initialization_failed = False
                    self.monitoring = True
                    self.monitor_thread = threading.Thread(
                        target=self._monitor_loop, daemon=True
                    )
                    self.monitor_thread.start()

                    self.hold_check_thread = threading.Thread(
                        target=self._hold_check_loop, daemon=True
                    )
                    self.hold_check_thread.start()
                    return

                except Exception:
                    if self.chip:
                        try:
                            self.chip.close()
                        except Exception:
                            pass
                        self.chip = None

        bg_thread = threading.Thread(target=retry_init, daemon=True)
        bg_thread.start()

    def _hold_check_loop(self):
        """Periodically check if button is held down long enough to trigger actions."""
        while self.monitoring:
            time.sleep(0.1)  # Check every 100ms

            if self.is_pressed and self.press_start_time:
                duration = time.time() - self.press_start_time

                # Check for Long Press (5s)
                if (
                    duration >= self.long_press_duration
                    and "long_press" not in self.triggered_actions
                ):
                    if self.long_press_callback:
                        self.triggered_actions.add("long_press")
                        try:
                            self.long_press_callback()
                        except Exception:
                            pass

                # Check for Factory Reset (15s)
                if (
                    duration >= self.factory_reset_duration
                    and "factory_reset" not in self.triggered_actions
                ):
                    if self.factory_reset_callback:
                        self.triggered_actions.add("factory_reset")
                        try:
                            self.factory_reset_callback()
                        except Exception:
                            pass

    def _monitor_loop(self):
        """Monitor for button press/release events."""
        last_event_time = 0
        debounce_ms = 50

        while self.monitoring and self.event_handle:
            try:
                event_id = self.event_handle.read_event()
                current_time = time.time()

                # Debounce
                if (current_time - last_event_time) < (debounce_ms / 1000.0):
                    continue
                last_event_time = current_time

                if event_id == GPIOEVENT_EVENT_FALLING_EDGE:
                    # Press started
                    self.is_pressed = True
                    self.press_start_time = current_time
                    self.triggered_actions = set()

                elif event_id == GPIOEVENT_EVENT_RISING_EDGE:
                    # Released
                    if self.is_pressed:
                        # Only trigger short press if no long action was triggered
                        if not self.triggered_actions and self.callback:
                            try:
                                self.callback()
                            except Exception:
                                pass

                        self.is_pressed = False
                        self.press_start_time = None
                        self.triggered_actions = set()

            except Exception:
                if self.monitoring:
                    time.sleep(1)

    def set_callback(self, callback: Callable[[], None]):
        """Register a function to be called on short press."""
        self.callback = callback

    def set_long_press_callback(self, callback: Callable[[], None]):
        """Register a function to be called on long press (5-15 seconds)."""
        self.long_press_callback = callback

    def set_factory_reset_callback(self, callback: Callable[[], None]):
        """Register a function to be called on factory reset press (15+ seconds)."""
        self.factory_reset_callback = callback

    def cleanup(self):
        self.monitoring = False

        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)

        if self.hold_check_thread:
            self.hold_check_thread.join(timeout=1)

        if self.event_handle:
            self.event_handle.close()
            self.event_handle = None

        if self.chip:
            self.chip.close()
            self.chip = None
