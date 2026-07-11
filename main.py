import os
import sys
import ctypes

# Enable Windows DPI awareness to align PyQt logical coordinates with Pillow physical pixels (1:1)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # 2 = PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import urllib.request
import zipfile
import shutil
import keyboard
import config
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QThread
from PyQt6.QtWidgets import QApplication
from rotation import RotationEngine
from overlay import OverlayWindow, CalibrationWindow
from voice import VoiceThread
from screen_tracker import ScreenTrackerThread

# Thread-safe helper to receive global hotkey events in PyQt main thread
class HotkeyReceiver(QObject):
    hotkey_pressed = pyqtSignal()

# Thread to download the Vosk speech model asynchronously to prevent GUI freezing
class ModelDownloaderThread(QThread):
    status_message = pyqtSignal(str, str)  # Emits (message, color)
    download_finished = pyqtSignal()

    def run(self):
        model_dir = "model"
        if os.path.exists(model_dir):
            self.download_finished.emit()
            return

        url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
        zip_path = "vosk-model-small-en-us-0.15.zip"
        
        self.status_message.emit("Downloading voice model (40MB)...", "#00ffff")
        try:
            def report_hook(block_num, block_size, total_size):
                read_so_far = block_num * block_size
                if total_size > 0:
                    percent = min(100.0, read_so_far * 100.0 / total_size)
                    self.status_message.emit(f"Downloading model: {percent:.1f}%", "#00ffff")
                else:
                    self.status_message.emit(f"Downloaded {read_so_far/(1024*1024):.1f}MB", "#00ffff")
            
            urllib.request.urlretrieve(url, zip_path, reporthook=report_hook)
            self.status_message.emit("Extracting model files...", "#ffff00")
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(".")
                
            extracted_folder = "vosk-model-small-en-us-0.15"
            if os.path.exists(extracted_folder):
                shutil.move(extracted_folder, model_dir)
            
            if os.path.exists(zip_path):
                os.remove(zip_path)
                
            self.status_message.emit("Speech model ready!", "#88ff88")
            self.download_finished.emit()
            
        except Exception as e:
            self.status_message.emit(f"Download failed: {e}", "#ff5555")


class MainApp:
    def __init__(self):
        self.config_data = config.load_config()
        self.rotation = RotationEngine()
        
        # Instantiate GUI
        self.overlay = OverlayWindow()
        self.overlay.update_moves(self.rotation.phase, self.rotation.get_next_moves())
        
        # Load window geometry
        pos = self.config_data.get("window_position")
        if pos:
            self.overlay.move(pos[0], pos[1])
        self.overlay.show()

        # Connect GUI controls
        self.overlay.calibrate_requested.connect(self.start_calibration)
        self.overlay.mic_changed.connect(self.update_microphone)
        self.overlay.phase_override.connect(self.manual_phase)
        self.overlay.reset_rotation.connect(self.reset_moves)

        # Setup background threads
        self.voice_thread = None
        self.tracker_thread = None
        self.downloader_thread = None

        # Setup global hotkey (via thread-safe receiver)
        self.hotkey_receiver = HotkeyReceiver()
        self.hotkey_receiver.hotkey_pressed.connect(self.toggle_overlay_interaction)
        self.setup_hotkey()

        # Begin voice model download/startup
        self.start_speech_startup()
        
        # Start HP Screen Tracker
        self.start_screen_tracker()

    def setup_hotkey(self):
        hotkey_str = self.config_data.get("hotkey", "ctrl+shift+u")
        try:
            # Unhook existing first to prevent double bindings
            keyboard.remove_hotkey(self.toggle_overlay_interaction)
        except Exception:
            pass

        def callback():
            self.hotkey_receiver.hotkey_pressed.emit()

        try:
            keyboard.add_hotkey(hotkey_str, callback)
        except Exception as e:
            self.overlay.set_status(f"Hotkey register failed: {e}", "#ff5555")

    def toggle_overlay_interaction(self):
        new_mode = not self.overlay.is_interactive
        self.overlay.set_interactive_mode(new_mode)
        if new_mode:
            self.overlay.set_status("Setup Mode (Move/Configure)", "#00ffff")
        else:
            self.overlay.set_status("HUD Active (Click-through)", "#88ff88")

    def start_speech_startup(self):
        # If model is already downloaded, start voice thread immediately
        if os.path.exists("model"):
            self.start_voice_thread()
        else:
            self.downloader_thread = ModelDownloaderThread()
            self.downloader_thread.status_message.connect(self.overlay.set_status)
            self.downloader_thread.download_finished.connect(self.start_voice_thread)
            self.downloader_thread.start()

    def start_voice_thread(self):
        if self.voice_thread:
            self.voice_thread.stop()
            self.voice_thread.wait()

        mic_idx = self.config_data.get("audio_device_index")
        self.voice_thread = VoiceThread(mic_idx)
        self.voice_thread.command_recognized.connect(self.handle_voice_command)
        self.voice_thread.status_message.connect(lambda msg: self.overlay.set_status(msg, "#88ff88"))
        self.voice_thread.error_occurred.connect(lambda err: self.overlay.set_status(err, "#ff5555"))
        self.voice_thread.start()

    def start_screen_tracker(self):
        if self.tracker_thread:
            self.tracker_thread.stop()
            self.tracker_thread.wait()

        self.tracker_thread = ScreenTrackerThread(config.load_config)
        self.tracker_thread.phase_changed.connect(self.auto_phase_transition)
        self.tracker_thread.status_message.connect(lambda msg: print(f"[Tracker] {msg}"))
        self.tracker_thread.start()

    def update_microphone(self, mic_idx):
        self.config_data["audio_device_index"] = mic_idx
        config.save_config(self.config_data)
        # Restart voice thread with new microphone selection
        self.start_voice_thread()

    def handle_voice_command(self, cmd):
        # Feed into RotationEngine
        changed, msg = self.rotation.process_voice_command(cmd)
        if changed:
            self.overlay.update_moves(self.rotation.phase, self.rotation.get_next_moves())
            self.overlay.set_status(msg, "#88ff88")

    def auto_phase_transition(self, new_phase):
        if self.rotation.set_phase(new_phase):
            self.overlay.update_moves(self.rotation.phase, self.rotation.get_next_moves())
            self.overlay.set_status(f"HP Boundary: Switched to Phase {new_phase}!", "#ffaa00")

    def manual_phase(self, phase_num):
        if self.rotation.set_phase(phase_num):
            self.overlay.update_moves(self.rotation.phase, self.rotation.get_next_moves())
            self.overlay.set_status(f"Set to Phase {phase_num} manually", "#ffff00")

    def reset_moves(self):
        self.rotation.reset()
        self.overlay.update_moves(self.rotation.phase, self.rotation.get_next_moves())
        self.overlay.set_status("Rotation reset", "#00ffff")

    def start_calibration(self):
        # Open calibration full screen selector
        self.cal_win = CalibrationWindow()
        self.cal_win.calibration_complete.connect(self.complete_calibration)

    def complete_calibration(self, region, color):
        self.config_data["ocr_region"] = region
        self.config_data["filled_hp_color"] = color
        config.save_config(self.config_data)
        self.overlay.set_status(f"Calibrated HP Bar: color={color}", "#88ff88")

    def clean_up(self):
        # Clean up listeners and exit threads gracefully
        try:
            keyboard.unhook_all()
        except Exception:
            pass
            
        if self.voice_thread:
            self.voice_thread.stop()
            self.voice_thread.wait()
            
        if self.tracker_thread:
            self.tracker_thread.stop()
            self.tracker_thread.wait()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    
    main_app = MainApp()
    
    # Hook clean up on exit
    app.aboutToQuit.connect(main_app.clean_up)
    
    sys.exit(app.exec())
