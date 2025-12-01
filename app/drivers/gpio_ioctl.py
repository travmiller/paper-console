import ctypes
import os
import fcntl
import struct
from typing import List, Optional

# Constants
GPIO_MAX_NAME_SIZE = 32

# Flags for gpiohandle_request.flags
GPIOHANDLE_REQUEST_INPUT = (1 << 0)
GPIOHANDLE_REQUEST_OUTPUT = (1 << 1)
GPIOHANDLE_REQUEST_ACTIVE_LOW = (1 << 2)
GPIOHANDLE_REQUEST_OPEN_DRAIN = (1 << 3)
GPIOHANDLE_REQUEST_OPEN_SOURCE = (1 << 4)
GPIOHANDLE_REQUEST_BIAS_PULL_UP = (1 << 5)
GPIOHANDLE_REQUEST_BIAS_PULL_DOWN = (1 << 6)
GPIOHANDLE_REQUEST_BIAS_DISABLE = (1 << 7)

# Flags for gpioevent_request.eventflags
GPIOEVENT_REQUEST_RISING_EDGE = (1 << 0)
GPIOEVENT_REQUEST_FALLING_EDGE = (1 << 1)
GPIOEVENT_REQUEST_BOTH_EDGES = ((1 << 0) | (1 << 1))

# Event IDs
GPIOEVENT_EVENT_RISING_EDGE = 1
GPIOEVENT_EVENT_FALLING_EDGE = 2

class gpiohandle_request(ctypes.Structure):
    _fields_ = [
        ("lineoffsets", ctypes.c_uint32 * 64),
        ("flags", ctypes.c_uint32),
        ("default_values", ctypes.c_uint8 * 64),
        ("consumer_label", ctypes.c_char * GPIO_MAX_NAME_SIZE),
        ("lines", ctypes.c_uint32),
        ("fd", ctypes.c_int),
    ]

class gpiohandle_data(ctypes.Structure):
    _fields_ = [
        ("values", ctypes.c_uint8 * 64),
    ]

class gpioevent_request(ctypes.Structure):
    _fields_ = [
        ("lineoffset", ctypes.c_uint32),
        ("handleflags", ctypes.c_uint32),
        ("eventflags", ctypes.c_uint32),
        ("consumer_label", ctypes.c_char * GPIO_MAX_NAME_SIZE),
        ("fd", ctypes.c_int),
    ]

class gpioevent_data(ctypes.Structure):
    _fields_ = [
        ("timestamp", ctypes.c_uint64),
        ("id", ctypes.c_uint32),
    ]

# IOCTL Macro helper
# This assumes standard Linux ioctl layout:
# bits 0-7: nr
# bits 8-15: type
# bits 16-29: size
# bits 30-31: dir (11 = Read/Write = 3)
def _IOWR(type_val, nr, size):
    return (3 << 30) | (size << 16) | (type_val << 8) | nr

GPIO_GET_LINEHANDLE_IOCTL = _IOWR(0xB4, 0x03, ctypes.sizeof(gpiohandle_request))
GPIO_GET_LINEEVENT_IOCTL = _IOWR(0xB4, 0x04, ctypes.sizeof(gpioevent_request))
GPIOHANDLE_GET_LINE_VALUES_IOCTL = _IOWR(0xB4, 0x08, ctypes.sizeof(gpiohandle_data))
GPIOHANDLE_SET_LINE_VALUES_IOCTL = _IOWR(0xB4, 0x09, ctypes.sizeof(gpiohandle_data))

class GpioHandle:
    """
    Wraps a GPIO line handle file descriptor.
    """
    def __init__(self, fd: int, lines: int):
        self.fd = fd
        self.lines = lines
        self._data = gpiohandle_data()

    def get_values(self) -> List[int]:
        """Read values from the GPIO lines."""
        if fcntl.ioctl(self.fd, GPIOHANDLE_GET_LINE_VALUES_IOCTL, self._data) < 0:
             raise OSError("Failed to get line values")
        
        # Return the first 'lines' values
        return list(self._data.values)[:self.lines]

    def set_values(self, values: List[int]):
        """Set values for output GPIO lines."""
        if len(values) != self.lines:
            raise ValueError(f"Expected {self.lines} values, got {len(values)}")
        
        for i, val in enumerate(values):
            self._data.values[i] = 1 if val else 0
            
        if fcntl.ioctl(self.fd, GPIOHANDLE_SET_LINE_VALUES_IOCTL, self._data) < 0:
            raise OSError("Failed to set line values")

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
    
    def __del__(self):
        self.close()

class GpioEventHandle:
    """
    Wraps a GPIO event handle file descriptor.
    """
    def __init__(self, fd: int):
        self.fd = fd
        self._data = gpioevent_data()

    def read_event(self) -> Optional[int]:
        """
        Read an event from the file descriptor.
        Returns the event ID (RISING_EDGE or FALLING_EDGE) or None on error.
        This is a blocking call unless the fd was opened non-blocking or select/poll is used.
        """
        try:
            data_bytes = os.read(self.fd, ctypes.sizeof(gpioevent_data))
            if len(data_bytes) != ctypes.sizeof(gpioevent_data):
                return None
            
            # Unpack into struct
            ctypes.memmove(ctypes.addressof(self._data), data_bytes, ctypes.sizeof(gpioevent_data))
            return self._data.id
        except OSError:
            return None

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __del__(self):
        self.close()

class GpioChip:
    """
    Interface to /dev/gpiochipN
    """
    def __init__(self, chip_path: str = "/dev/gpiochip0"):
        self.chip_path = chip_path
        self.fd = None

    def open(self):
        self.fd = os.open(self.chip_path, os.O_RDONLY)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def request_lines(self, offsets: List[int], flags: int, label: str = "gpio_ioctl") -> GpioHandle:
        """
        Request a set of GPIO lines for reading/writing values.
        """
        if self.fd is None:
            self.open()

        req = gpiohandle_request()
        req.lines = len(offsets)
        req.flags = flags
        req.consumer_label = label.encode('utf-8')[:GPIO_MAX_NAME_SIZE-1]
        
        for i, offset in enumerate(offsets):
            req.lineoffsets[i] = offset
        
        # Request the lines
        if fcntl.ioctl(self.fd, GPIO_GET_LINEHANDLE_IOCTL, req) < 0:
            raise OSError(f"Failed to request GPIO lines {offsets}")
            
        return GpioHandle(req.fd, len(offsets))

    def request_event(self, offset: int, handle_flags: int, event_flags: int, label: str = "gpio_event") -> GpioEventHandle:
        """
        Request a single line for event monitoring (interrupts).
        """
        if self.fd is None:
            self.open()
            
        req = gpioevent_request()
        req.lineoffset = offset
        req.handleflags = handle_flags
        req.eventflags = event_flags
        req.consumer_label = label.encode('utf-8')[:GPIO_MAX_NAME_SIZE-1]
        
        if fcntl.ioctl(self.fd, GPIO_GET_LINEEVENT_IOCTL, req) < 0:
            raise OSError(f"Failed to request GPIO event for line {offset}")
            
        return GpioEventHandle(req.fd)
