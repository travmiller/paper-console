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
                
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"ButtonDriver initialized successfully on GPIO {self.pin}")
                return

            except OSError as e:
                import logging
                logger = logging.getLogger(__name__)
                if e.errno == 16 and attempt < max_retries - 1:  # EBUSY
                    logger.warning(f"GPIO {self.pin} busy, retrying (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    if self.chip:
                        self.chip.close()
                        self.chip = None
                else:
                    logger.error(f"Failed to initialize GPIO {self.pin}: {e}")
                    self._initialization_failed = True
                    self.gpio_available = False
                    self.cleanup()
                    self._schedule_background_reinit()
                    return
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Exception initializing GPIO {self.pin}: {e}", exc_info=True)
                self._initialization_failed = True
                self.gpio_available = False
                self.cleanup()
                self._schedule_background_reinit()
                return

    def _schedule_background_reinit(self):
        """Schedule a background thread to retry GPIO initialization."""

        def retry_init():
            import logging
            logger = logging.getLogger(__name__)
            # Start with shorter retry interval, then increase
            retry_intervals = [5, 10, 30, 60]  # 5s, 10s, 30s, then 60s
            max_bg_retries = 20  # More retries

            for attempt in range(max_bg_retries):
                # Use increasing retry intervals
                retry_interval = retry_intervals[min(attempt // 3, len(retry_intervals) - 1)]
                time.sleep(retry_interval)
                
                logger.info(f"Background reinit attempt {attempt + 1}/{max_bg_retries} for GPIO {self.pin}")

                try:
                    # Cleanup first to ensure GPIO is released
                    self.cleanup()
                    # Wait longer for GPIO to be released by kernel
                    # GPIO lines can take time to be fully released
                    wait_time = 2.0 if attempt < 3 else 1.0
                    time.sleep(wait_time)
                    
                    self.chip = GpioChip("/dev/gpiochip0")
                    handle_flags = (
                        GPIOHANDLE_REQUEST_INPUT | GPIOHANDLE_REQUEST_BIAS_PULL_UP
                    )
                    event_flags = GPIOEVENT_REQUEST_BOTH_EDGES

                    self.event_handle = self.chip.request_event(
                        self.pin, handle_flags, event_flags, label=f"button-gpio{self.pin}"
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
                    
                    logger.info(f"Successfully reinitialized GPIO {self.pin} in background")
                    return

                except OSError as e:
                    if e.errno == 16:  # EBUSY
                        logger.warning(f"GPIO {self.pin} still busy (attempt {attempt + 1}) - will retry")
                    else:
                        logger.warning(f"Background reinit failed for GPIO {self.pin}: {e}")
                    if self.chip:
                        try:
                            self.chip.close()
                        except Exception:
                            pass
                        self.chip = None
                except Exception as e:
                    logger.warning(f"Background reinit failed for GPIO {self.pin}: {e}")
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
        consecutive_errors = 0
        max_consecutive_errors = 10

        while self.monitoring:
            if not self.event_handle:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Event handle lost for GPIO {self.pin} - monitor loop exiting")
                self.monitoring = False
                self._initialization_failed = True
                # Try to properly cleanup before scheduling reinit
                # Close chip handle to ensure GPIO is released
                if self.chip:
                    try:
                        self.chip.close()
                    except Exception:
                        pass
                    self.chip = None
                # Schedule reinit after a delay to let kernel release GPIO
                self._schedule_background_reinit()
                break
                
            try:
                event_id = self.event_handle.read_event()
                if event_id is None:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Too many None events from GPIO {self.pin} - handle may be invalid")
                        self.monitoring = False
                        self._initialization_failed = True
                        if self.event_handle:
                            try:
                                self.event_handle.close()
                            except Exception:
                                pass
                            self.event_handle = None
                        self._schedule_background_reinit()
                        break
                    time.sleep(0.1)
                    continue
                
                consecutive_errors = 0  # Reset on successful read
                current_time = time.time()

                # Debounce
                if (current_time - last_event_time) < (debounce_ms / 1000.0):
                    continue
                last_event_time = current_time

                if event_id == GPIOEVENT_EVENT_FALLING_EDGE:
                    # Press started
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Button on GPIO {self.pin} pressed")
                    self.is_pressed = True
                    self.press_start_time = current_time
                    self.triggered_actions = set()

                elif event_id == GPIOEVENT_EVENT_RISING_EDGE:
                    # Released
                    if self.is_pressed:
                        # Only trigger short press if no long action was triggered
                        if not self.triggered_actions and self.callback:
                            try:
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.info(f"Button on GPIO {self.pin} released - triggering short press callback")
                                self.callback()
                            except Exception as e:
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.error(f"Error in button callback: {e}", exc_info=True)

                        self.is_pressed = False
                        self.press_start_time = None
                        self.triggered_actions = set()

            except OSError as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"OSError in monitor loop for GPIO {self.pin}: {e}")
                if e.errno == 9:  # EBADF - Bad file descriptor
                    logger.error(f"Event handle file descriptor is invalid for GPIO {self.pin}")
                    self.monitoring = False
                    self._initialization_failed = True
                    # Properly cleanup to release GPIO
                    if self.event_handle:
                        try:
                            self.event_handle.close()
                        except Exception:
                            pass
                        self.event_handle = None
                    # Close chip handle to ensure GPIO is fully released
                    if self.chip:
                        try:
                            self.chip.close()
                        except Exception:
                            pass
                        self.chip = None
                    # Schedule reinit after delay
                    self._schedule_background_reinit()
                    break
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Too many OSErrors in monitor loop for GPIO {self.pin} - stopping")
                    self.monitoring = False
                    self._initialization_failed = True
                    # Cleanup
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
                    self._schedule_background_reinit()
                    break
                time.sleep(1)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Unexpected error in monitor loop for GPIO {self.pin}: {e}", exc_info=True)
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Too many errors in monitor loop for GPIO {self.pin} - stopping")
                    self.monitoring = False
                    self._initialization_failed = True
                    break
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
        import logging
        logger = logging.getLogger(__name__)
        
        logger.debug(f"Cleaning up button driver on GPIO {self.pin}")
        self.monitoring = False

        # Wait for threads to finish
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)

        if self.hold_check_thread and self.hold_check_thread.is_alive():
            self.hold_check_thread.join(timeout=2)

        # Close event handle first (this releases the GPIO line)
        if self.event_handle:
            try:
                logger.debug(f"Closing event handle for GPIO {self.pin}")
                self.event_handle.close()
            except Exception as e:
                logger.warning(f"Error closing event handle: {e}")
            finally:
                self.event_handle = None

        # Then close chip handle
        if self.chip:
            try:
                logger.debug(f"Closing chip handle for GPIO {self.pin}")
                self.chip.close()
            except Exception as e:
                logger.warning(f"Error closing chip handle: {e}")
            finally:
                self.chip = None
        
        logger.debug(f"Cleanup complete for GPIO {self.pin}")
    
    def reinitialize(self):
        """
        Manually reinitialize the GPIO button driver.
        Useful if initialization failed and background retry didn't work.
        """
        import logging
        import time
        logger = logging.getLogger(__name__)
        
        logger.info(f"Attempting to reinitialize button driver on GPIO {self.pin}")
        
        # Cleanup existing resources first - this is critical
        # We need to ensure GPIO 3 is fully released
        self.cleanup()
        
        # Wait longer to ensure GPIO is fully released by kernel
        # GPIO lines can take a moment to be released after closing handles
        time.sleep(1.0)
        
        # Reset state
        self._initialization_failed = False
        self.gpio_available = GPIO_AVAILABLE
        
        if not self.gpio_available:
            logger.warning("GPIO not available - cannot reinitialize")
            return False
        
        # Try to initialize again with retries
        max_retries = 5
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Ensure everything is cleaned up first
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
                
                # Wait a bit longer for GPIO to be released
                if attempt > 0:
                    time.sleep(retry_delay)
                
                # Try to open chip and request event handle
                self.chip = GpioChip("/dev/gpiochip0")
                
                handle_flags = (
                    GPIOHANDLE_REQUEST_INPUT | GPIOHANDLE_REQUEST_BIAS_PULL_UP
                )
                event_flags = GPIOEVENT_REQUEST_BOTH_EDGES
                
                # Try requesting the event handle
                # This will fail if GPIO 3 is still in use
                self.event_handle = self.chip.request_event(
                    self.pin, handle_flags, event_flags, label=f"button-gpio{self.pin}"
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
                
                logger.info(f"Successfully reinitialized button driver on GPIO {self.pin}")
                return True
                
            except OSError as e:
                if e.errno == 16:  # EBUSY - Device or resource busy
                    if attempt < max_retries - 1:
                        logger.warning(f"GPIO {self.pin} busy, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        retry_delay *= 1.5  # Exponential backoff
                        continue
                    else:
                        logger.error(f"GPIO {self.pin} still busy after {max_retries} attempts")
                        logger.error("GPIO 3 may be in use by I2C. Check /boot/config.txt for dtparam=i2c_arm=on")
                logger.error(f"Failed to reinitialize button driver: {e}", exc_info=True)
                self._initialization_failed = True
                self.gpio_available = False
                return False
            except Exception as e:
                logger.error(f"Failed to reinitialize button driver: {e}", exc_info=True)
                self._initialization_failed = True
                self.gpio_available = False
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return False
        
        return False
