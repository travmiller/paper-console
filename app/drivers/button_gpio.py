import threading
import time
import os
import select
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
      - Long press (5-15 seconds) - triggers ON RELEASE
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
        self.last_release_time = 0  # Track last button release for cooldown
        # self.cooldown_period = 0.05  # REMOVED: 50ms cooldown after release to prevent double-triggers
        self.last_callback_time = 0  # Track when callback was last called
        # self.callback_cooldown = 0.15  # REMOVED: 150ms minimum between callbacks to prevent rapid-fire

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
                    # Close existing chip if it exists (but don't call full cleanup)
                    if self.chip:
                        try:
                            self.chip.close()
                        except Exception:
                            pass
                        self.chip = None
                    
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

                # Mark that we've reached the long press threshold (5s)
                # But don't trigger callback yet - wait for release
                if (
                    duration >= self.long_press_duration
                    and "long_press_threshold" not in self.triggered_actions
                ):
                    self.triggered_actions.add("long_press_threshold")

                # Check for Factory Reset (15s) - triggers immediately while holding
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
        # last_event_time = 0 # REMOVED: debounce tracking
        # debounce_ms = 50  # REMOVED: 50ms debounce - minimal but effective

        while self.monitoring and self.event_handle:
            try:
                fd = self.event_handle.fd
                if fd is None:
                    time.sleep(0.01)
                    continue
                
                # Check if data is available (non-blocking with short timeout)
                ready, _, _ = select.select([fd], [], [], 0.01)
                
                if not ready:
                    # No event available, continue loop
                    continue
                
                # Read all available events in a batch to avoid missing any
                # Process up to 10 events per iteration to handle rapid presses
                events_processed = 0
                max_events_per_iteration = 10
                
                while events_processed < max_events_per_iteration:
                    # Check if more data is available
                    ready, _, _ = select.select([fd], [], [], 0)
                    if not ready:
                        break
                    
                    # Read the event
                    event_id = self.event_handle.read_event()
                    if event_id is None:
                        break
                    
                    events_processed += 1
                    current_time = time.time()

                    # Debounce - REMOVED
                    # time_since_last_event = current_time - last_event_time
                    # if time_since_last_event < (debounce_ms / 1000.0):
                    #    continue
                    # last_event_time = current_time

                    if event_id == GPIOEVENT_EVENT_FALLING_EDGE:
                        # Press started
                        # Only check cooldown if we're not already processing a press
                        if not self.is_pressed:
                            # time_since_release = current_time - self.last_release_time
                            # if time_since_release < self.cooldown_period:
                            #    continue
                            pass
                        
                        self.is_pressed = True
                        self.press_start_time = current_time
                        self.triggered_actions = set()

                    elif event_id == GPIOEVENT_EVENT_RISING_EDGE:
                        # Released
                        if self.is_pressed:
                            # Calculate hold duration
                            hold_duration = None
                            if self.press_start_time:
                                hold_duration = current_time - self.press_start_time

                            # Check if we should trigger AP mode (long press)
                            # Only trigger if:
                            # - Hold duration was between 5-15 seconds
                            # - Factory reset was NOT triggered
                            if (
                                hold_duration is not None
                                and hold_duration >= self.long_press_duration
                                and hold_duration < self.factory_reset_duration
                                and "factory_reset" not in self.triggered_actions
                                and self.long_press_callback
                            ):
                                # Check callback cooldown before triggering long press
                                # if (current_time - self.last_callback_time) >= self.callback_cooldown:
                                try:
                                    self.long_press_callback()
                                    self.last_callback_time = current_time
                                except Exception:
                                    pass
                            # Otherwise, trigger short press if no actions were triggered
                            elif not self.triggered_actions and self.callback:
                                # Check callback cooldown before triggering short press
                                # if (current_time - self.last_callback_time) >= self.callback_cooldown:
                                try:
                                    self.callback()
                                    self.last_callback_time = current_time
                                except Exception:
                                    pass

                            self.is_pressed = False
                            self.press_start_time = None
                            self.triggered_actions = set()
                            # self.last_release_time = current_time  # Track release time for cooldown

            except OSError:
                # File descriptor closed or invalid, wait a bit and continue
                if self.monitoring:
                    time.sleep(0.5)
            except Exception:
                # Other errors - log and continue
                if self.monitoring:
                    time.sleep(0.01)

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
            try:
                self.event_handle.close()
            except Exception:
                pass
            self.event_handle = None

        if self.chip:
            try:
                self.chip.close()
            except Exception:
                pass
            self.chip = None
