import sys
import os
import time
import platform

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.drivers.printer_serial import PrinterDriver
from app.drivers.dial_gpio import DialDriver

def test_hardware():
    print("--- PC-1 Hardware Test ---")
    
    # 1. Test Printer
    print("\n[1/2] Testing Printer connection...")
    try:
        # Initialize printer (auto-detects USB/Serial ports)
        printer = PrinterDriver(width=32)
        
        if printer.ser:
            print("      Success! Printer found.")
            print("      Printing test message...")
            printer.print_line()
            printer.print_header("HARDWARE TEST")
            printer.print_text("If you can read this,")
            printer.print_text("the printer is working!")
            printer.print_text(f"Time: {time.strftime('%H:%M:%S')}")
            printer.print_line()
            printer.feed(3)
        else:
            print("      FAILED. Printer not found.")
            print("      Check USB connection and permissions.")
            print("      Try: ls -l /dev/tty*")
            
    except Exception as e:
        print(f"      Error: {e}")

    # 2. Test Dial
    print("\n[2/2] Testing Dial (Rotary Switch)...")
    try:
        # Initialize dial
        dial = DialDriver()
        
        current_pos = dial.read_position()
        print(f"      Current Position: {current_pos}")
        print("      Please turn the dial now (Press Ctrl+C to stop)...")
        
        # Simple monitoring loop
        last_pos = current_pos
        try:
            for _ in range(20): # Monitor for 2 seconds (100ms * 20)
                pos = dial.read_position()
                if pos != last_pos:
                    print(f"      > Dial moved to: {pos}")
                    last_pos = pos
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
            
    except Exception as e:
        print(f"      Error: {e}")

    print("\n--- Test Complete ---")

if __name__ == "__main__":
    test_hardware()

