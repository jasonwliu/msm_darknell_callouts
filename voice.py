import os
import json
import queue
import sys
from PyQt6.QtCore import QThread, pyqtSignal
import sounddevice as sd
from vosk import Model, KaldiRecognizer

class VoiceThread(QThread):
    command_recognized = pyqtSignal(str)
    status_message = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, device_index=None):
        super().__init__()
        self.device_index = device_index
        self.model_dir = "model"
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True
        self.requestInterruption()

    def run(self):
        self._stop_requested = False
        
        # Check if model exists
        if not os.path.exists(self.model_dir):
            self.error_occurred.emit("Vosk model not found! Download it from settings.")
            return

        self.status_message.emit("Loading speech model...")
        try:
            model = Model(self.model_dir)
        except Exception as e:
            self.error_occurred.emit(f"Failed to load Vosk model: {e}")
            return

        # Query audio devices
        try:
            device_info = sd.query_devices(self.device_index, 'input')
            samplerate = int(device_info['default_samplerate'])
            device_name = device_info['name']
        except Exception as e:
            self.error_occurred.emit(f"Failed to query microphone: {e}")
            return

        self.status_message.emit(f"Listening on: {device_name}")

        # Setup strict vocabulary to boost accuracy
        # Valid words that the recognizer is limited to
        words = [
            "meteor", "push", "buff", "dash", "fly", "charge",
            "phase", "one", "two", "three", "four",
            "reset", "stun", "stop", "[unk]"
        ]
        grammar_str = json.dumps(words)
        
        try:
            rec = KaldiRecognizer(model, samplerate, grammar_str)
        except Exception as e:
            self.error_occurred.emit(f"Failed to initialize recognizer: {e}")
            return

        audio_queue = queue.Queue()

        def callback(indata, frames, time_info, status):
            if status:
                # We can log status, but we avoid printing to console directly from threads
                pass
            audio_queue.put(bytes(indata))

        # Start input stream
        try:
            stream = sd.RawInputStream(
                samplerate=samplerate,
                blocksize=8000,
                device=self.device_index,
                dtype='int16',
                channels=1,
                callback=callback
            )
        except Exception as e:
            self.error_occurred.emit(f"Failed to open microphone stream: {e}")
            return

        with stream:
            while not self.isInterruptionRequested() and not self._stop_requested:
                try:
                    data = audio_queue.get(timeout=0.1)
                    if rec.AcceptWaveform(data):
                        res = json.loads(rec.Result())
                        text = res.get("text", "").strip()
                        if text:
                            text_norm = text.lower()
                            # Only accept full 'phase X' commands for manual phase changes
                            if "phase one" in text_norm:
                                self.command_recognized.emit("p1")
                            elif "phase two" in text_norm:
                                self.command_recognized.emit("p2")
                            elif "phase three" in text_norm:
                                self.command_recognized.emit("p3")
                            elif "phase four" in text_norm:
                                self.command_recognized.emit("p4")
                            else:
                                # For normal moves, split by words and emit individually
                                for word in text_norm.split():
                                    if word in ["meteor", "push", "buff", "dash", "fly", "charge", "reset", "stun"]:
                                        self.command_recognized.emit(word)
                except queue.Empty:
                    pass
                except Exception as e:
                    self.error_occurred.emit(f"Voice thread loop error: {e}")
                    break

        self.status_message.emit("Speech recognition stopped.")
