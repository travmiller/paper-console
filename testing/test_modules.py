#!/usr/bin/env python3
"""
PC-1 Module Testing Script
Tests all modules and prints their output to console (using mock printer).
"""

import sys
from datetime import datetime

# Test imports
print("=" * 60)
print("PC-1 MODULE TEST")
print("=" * 60)
print()

print("[1/8] Testing imports...")
try:
    from app.drivers.printer_mock import PrinterDriver
    from app.modules import (
        astronomy,
        sudoku,
        weather,
        maze,
        quotes,
        history,
        checklist,
        text,
    )
    from app.config import settings, TextConfig, ChecklistConfig, ChecklistItem
    print("✓ All imports successful")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

print()
print("[2/8] Creating mock printer...")
printer = PrinterDriver(width=32)
print("✓ Mock printer created")
print()

# Test each module
modules_to_test = [
    ("History", lambda: history.format_history_receipt(printer, {"count": 1}, "On This Day")),
    ("Quotes", lambda: quotes.format_quotes_receipt(printer, {}, "Daily Quote")),
    ("Astronomy", lambda: astronomy.format_astronomy_receipt(printer, "Astronomy")),
    ("Sudoku", lambda: sudoku.format_sudoku_receipt(printer, {"difficulty": "medium"}, "Sudoku Puzzle")),
    ("Maze", lambda: maze.format_maze_receipt(printer, {"difficulty": "medium"}, "Maze")),
    ("Weather", lambda: weather.format_weather_receipt(printer, {}, "Weather")),
    ("Text/Note", lambda: text.format_text_receipt(printer, TextConfig(content="This is a test note."), "Test Note")),
    ("Checklist", lambda: checklist.format_checklist_receipt(printer, {"items": [{"text": "Item 1"}, {"text": "Item 2"}]}, "Test Checklist")),
]

for i, (name, test_func) in enumerate(modules_to_test, start=3):
    print(f"[{i}/10] Testing {name} module...")
    print("-" * 60)
    
    try:
        # Reset printer buffer
        if hasattr(printer, 'reset_buffer'):
            printer.reset_buffer()
        
        # Run the module
        test_func()
        
        # Flush to console (mock printer prints to console)
        if hasattr(printer, 'flush_buffer'):
            printer.flush_buffer()
        
        print()
        print(f"✓ {name} module passed")
    except Exception as e:
        print(f"✗ {name} module failed: {e}")
        import traceback
        traceback.print_exc()
    
    print()

print()
print("=" * 60)
print("TEST COMPLETE")
print("=" * 60)
print()
print("All modules tested. Check output above for any errors.")
print()
print("To start the server:")
print("  ./run.sh")
print()
print("Or manually:")
print("  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
print()
