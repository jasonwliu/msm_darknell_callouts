import os
import json

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "hotkey": "ctrl+shift+u",
    "ocr_region": None,  # [x, y, width, height]
    "audio_device_index": None,
    "listener_device_index": None,
    "audio_mode": "shotcaller",
    "window_position": [100, 100],
    "filled_hp_color": [50, 210, 50]  # Default green HP color for Maplestory M
}

def get_config_path():
    # Store config locally in the script directory
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)

def load_config():
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                # Ensure all default keys exist
                config = DEFAULT_CONFIG.copy()
                config.update(data)
                return config
        except Exception as e:
            print(f"Error loading config: {e}")
            return DEFAULT_CONFIG.copy()
    else:
        return DEFAULT_CONFIG.copy()

def save_config(config):
    path = get_config_path()
    try:
        with open(path, "w") as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False
