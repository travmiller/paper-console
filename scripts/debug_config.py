import os
import json
import sys
from app.config import load_config, settings

def debug_config():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config.json")
    
    print(f"Debugging Config Loading...")
    print(f"Expected Config Path: {config_path}")
    
    if os.path.exists(config_path):
        print(f"File exists: Yes")
        try:
            with open(config_path, 'r') as f:
                content = f.read()
                print(f"File content length: {len(content)} bytes")
                try:
                    json_data = json.loads(content)
                    print("JSON syntax: Valid")
                    print(f"Keys in JSON: {list(json_data.keys())}")
                except json.JSONDecodeError as e:
                    print(f"JSON syntax: INVALID - {e}")
        except Exception as e:
            print(f"Error reading file: {e}")
    else:
        print(f"File exists: No")

    print("-" * 20)
    print("Attempting to load via app.config.load_config()...")
    try:
        loaded_settings = load_config()
        print("Load successful.")
        print(f"Loaded settings modules count: {len(loaded_settings.modules)}")
        print(f"Loaded settings channels count: {len(loaded_settings.channels)}")
    except Exception as e:
        print(f"Load failed: {e}")

    print("-" * 20)
    print("Current Global Settings State:")
    print(f"Modules: {len(settings.modules)}")
    print(f"Channels: {len(settings.channels)}")

if __name__ == "__main__":
    debug_config()

