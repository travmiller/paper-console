#!/usr/bin/env python3
"""
Validate all icon references in the codebase against available icons in icons/regular/icons.txt
"""

import os
import re
import sys
from pathlib import Path

# Get project root
project_root = Path(__file__).parent.parent
icons_file = project_root / "icons" / "regular" / "icons.txt"

# Load available icons (without .png extension)
available_icons = set()
if icons_file.exists():
    with open(icons_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and line.endswith(".png"):
                icon_name = line[:-4]  # Remove .png
                available_icons.add(icon_name)
else:
    print(f"ERROR: {icons_file} not found!")
    sys.exit(1)

print(f"Loaded {len(available_icons)} available icons from icons.txt\n")

# Extract icon_map from printer_serial.py
printer_serial_file = project_root / "app" / "drivers" / "printer_serial.py"
icon_map = {}
direct_references = set()

if printer_serial_file.exists():
    with open(printer_serial_file, "r", encoding="utf-8") as f:
        content = f.read()
        
        # Extract icon_map dictionary
        icon_map_match = re.search(r'icon_map\s*=\s*\{([^}]+)\}', content, re.DOTALL)
        if icon_map_match:
            icon_map_content = icon_map_match.group(1)
            # Extract key-value pairs
            pairs = re.findall(r'["\']([^"\']+)["\']\s*:\s*["\']([^"\']+)["\']', icon_map_content)
            for key, value in pairs:
                icon_map[key.lower()] = value.lower()

# Find all icon references in codebase
# 1. From icon_map keys (aliases)
icon_aliases = set(icon_map.keys())

# 2. From icon_map values (actual icon names)
icon_map_targets = set(icon_map.values())

# 3. Direct references from code (search for icon="..." or icon='...')
code_files = [
    project_root / "app" / "main.py",
    project_root / "app" / "modules" / "weather.py",
    project_root / "app" / "modules" / "astronomy.py",
    project_root / "app" / "modules" / "news.py",
    project_root / "app" / "modules" / "rss.py",
    project_root / "app" / "modules" / "email_client.py",
    project_root / "app" / "modules" / "calendar.py",
    project_root / "app" / "modules" / "text.py",
    project_root / "app" / "modules" / "webhook.py",
    project_root / "app" / "modules" / "quotes.py",
    project_root / "app" / "modules" / "system_monitor.py",
    project_root / "app" / "modules" / "checklist.py",
    project_root / "app" / "modules" / "history.py",
    project_root / "app" / "modules" / "sudoku.py",
    project_root / "app" / "modules" / "maze.py",
]

for code_file in code_files:
    if code_file.exists():
        with open(code_file, "r", encoding="utf-8") as f:
            content = f.read()
            # Find icon="..." or icon='...'
            icon_refs = re.findall(r'icon\s*=\s*["\']([^"\']+)["\']', content)
            direct_references.update(icon_refs)
            # Find print_icon("...")
            icon_refs2 = re.findall(r'print_icon\s*\(\s*["\']([^"\']+)["\']', content)
            direct_references.update(icon_refs2)
            # Find _get_icon_type return values
            icon_refs3 = re.findall(r'return\s+["\']([^"\']+)["\']', content)
            # Filter for likely icon names (simple heuristic)
            for ref in icon_refs3:
                if ref in ["sun", "cloud", "cloud-sun", "cloud-rain", "cloud-snow", 
                          "cloud-lightning", "cloud-fog", "storm", "rain", "snow"]:
                    direct_references.add(ref)

# Normalize all references to lowercase
direct_references = {ref.lower() for ref in direct_references}

# Validate: Check that all icon_map target values exist
invalid_mappings = []
for alias, target in icon_map.items():
    if target not in available_icons:
        invalid_mappings.append(f"icon_map['{alias}'] -> '{target}' (target not found)")

# Validate: Check that all direct references either exist or are mapped
missing_icons = []
unmapped_direct_refs = []

for ref in direct_references:
    ref_lower = ref.lower()
    # Check if it exists directly
    if ref_lower in available_icons:
        continue
    # Check if it's mapped
    if ref_lower in icon_map:
        mapped_to = icon_map[ref_lower]
        if mapped_to not in available_icons:
            invalid_mappings.append(f"Direct ref '{ref}' -> icon_map['{ref_lower}'] -> '{mapped_to}' (target not found)")
        continue
    # Not found and not mapped
    missing_icons.append(ref)

# Special case: arrow_right should probably be arrow-right
if "arrow_right" in direct_references or "arrow-right" in direct_references:
    if "arrow-right" in available_icons and "arrow_right" not in icon_map:
        invalid_mappings.append("'arrow_right' used in code but not mapped (should map to 'arrow-right')")

# Report results
print("=" * 70)
print("ICON VALIDATION REPORT")
print("=" * 70)

if invalid_mappings:
    print(f"\n[WARNING] INVALID MAPPINGS ({len(invalid_mappings)}):")
    print("-" * 70)
    for mapping in invalid_mappings:
        print(f"  - {mapping}")

if missing_icons:
    print(f"\n[ERROR] MISSING ICONS ({len(missing_icons)}):")
    print("-" * 70)
    print("These icons are referenced directly in code but don't exist and aren't mapped:")
    for icon in sorted(missing_icons):
        print(f"  - {icon}")
        # Suggest mapping if similar icon exists
        if icon.replace("_", "-") in available_icons:
            print(f"    -> Suggestion: map to '{icon.replace('_', '-')}'")
else:
    print("\n[OK] All direct icon references are valid")

# Summary
print(f"\nSUMMARY:")
print(f"  - Available icons: {len(available_icons)}")
print(f"  - Icon aliases (mapped): {len(icon_map)}")
print(f"  - Direct references: {len(direct_references)}")
print(f"  - Missing icons: {len(missing_icons)}")
print(f"  - Invalid mappings: {len(invalid_mappings)}")

if missing_icons or invalid_mappings:
    print("\n[FAILED] VALIDATION FAILED")
    sys.exit(1)
else:
    print("\n[PASSED] VALIDATION PASSED")
    sys.exit(0)
