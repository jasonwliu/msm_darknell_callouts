import os
import json
import queue
import sys
import numpy as np
import pyaudiowpatch as pyaudio
from PyQt6.QtCore import QThread, pyqtSignal
from vosk import Model, KaldiRecognizer

def to_mono(data_bytes, channels):
    if channels == 1:
        return data_bytes
    samples = np.frombuffer(data_bytes, dtype=np.int16)
    # Handle possible partial frame at the end of the byte buffer
    num_samples = len(samples)
    remainder = num_samples % channels
    if remainder != 0:
        samples = samples[:-remainder]
    samples = samples.reshape(-1, channels)
    # Average the channels to generate a mono channel to avoid audio distortion
    mono_samples = (samples.astype(np.int32).sum(axis=1) / channels).astype(np.int16)
    return mono_samples.tobytes()

def find_default_loopback_device(p):
    # Find WASAPI host API index
    wasapi_idx = None
    for i in range(p.get_host_api_count()):
        if p.get_host_api_info_by_index(i)['type'] == pyaudio.paWASAPI:
            wasapi_idx = i
            break
            
    if wasapi_idx is None:
        return None
        
    # Get default WASAPI output device
    wasapi_info = p.get_host_api_info_by_index(wasapi_idx)
    default_output = wasapi_info.get("defaultOutputDevice")
    if default_output is None or default_output < 0:
        return None
        
    try:
        speaker_info = p.get_device_info_by_index(default_output)
        speaker_name = speaker_info['name']
    except Exception:
        return None
    
    # Look for the loopback device corresponding to the default output device
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev['hostApi'] == wasapi_idx and dev.get("isLoopbackDevice", False):
            if speaker_name in dev['name']:
                return i
                
    # Fallback to any loopback device
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev['hostApi'] == wasapi_idx and dev.get("isLoopbackDevice", False):
            return i
            
    return None


class VoiceThread(QThread):
    command_recognized = pyqtSignal(str)
    status_message = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, device_index=None, listener_index=None, audio_mode="shotcaller"):
        super().__init__()
        self.device_index = device_index
        self.listener_index = listener_index
        self.audio_mode = audio_mode
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

        p = pyaudio.PyAudio()

        # Check active mode and find devices
        mic_info = None
        loop_info = None

        if self.audio_mode == "shotcaller":
            # Find microphone
            mic_idx = self.device_index
            if mic_idx is None:
                try:
                    mic_idx = p.get_default_input_device_info()["index"]
                except Exception:
                    mic_idx = None

            if mic_idx is not None:
                try:
                    mic_info = p.get_device_info_by_index(mic_idx)
                except Exception:
                    try:
                        mic_idx = p.get_default_input_device_info()["index"]
                        mic_info = p.get_device_info_by_index(mic_idx)
                    except Exception:
                        mic_info = None
        else:
            # Find system loopback device
            loop_idx = self.listener_index
            if loop_idx is None:
                loop_idx = find_default_loopback_device(p)
                
            if loop_idx is not None:
                try:
                    loop_info = p.get_device_info_by_index(loop_idx)
                except Exception:
                    # Fallback to default search
                    loop_idx = find_default_loopback_device(p)
                    if loop_idx is not None:
                        try:
                            loop_info = p.get_device_info_by_index(loop_idx)
                        except Exception:
                            loop_info = None

        if mic_info is None and loop_info is None:
            self.error_occurred.emit("No active input or loopback devices found for chosen mode.")
            p.terminate()
            return

        # Setup strict vocabulary to boost accuracy
        words = [
            "meteor", "push", "buff", "dash", "dive", "charge",
            "shock", "shockwave",
            "phase", "one", "two", "three", "four",
            "reset", "stun", "stunned", "stop", "[unk]"
        ]
        grammar_str = json.dumps(words)

        # Initialize recognizers
        mic_rec = None
        if mic_info is not None:
            try:
                mic_samplerate = int(mic_info["defaultSampleRate"])
                mic_rec = KaldiRecognizer(model, mic_samplerate, grammar_str)
            except Exception as e:
                print(f"Failed to initialize mic recognizer: {e}")
                mic_info = None

        loop_rec = None
        if loop_info is not None:
            try:
                loop_samplerate = int(loop_info["defaultSampleRate"])
                loop_rec = KaldiRecognizer(model, loop_samplerate, grammar_str)
            except Exception as e:
                print(f"Failed to initialize loopback recognizer: {e}")
                loop_info = None

        if mic_info is None and loop_info is None:
            self.error_occurred.emit("Failed to initialize speech recognizers.")
            p.terminate()
            return

        mic_queue = queue.Queue()
        loop_queue = queue.Queue()

        def mic_callback(in_data, frame_count, time_info, status):
            mic_queue.put(in_data)
            return (None, pyaudio.paContinue)

        def loop_callback(in_data, frame_count, time_info, status):
            loop_queue.put(in_data)
            return (None, pyaudio.paContinue)

        # Open streams
        mic_stream = None
        if mic_info is not None:
            try:
                mic_channels = int(mic_info["maxInputChannels"])
                mic_samplerate = int(mic_info["defaultSampleRate"])
                mic_stream = p.open(
                    format=pyaudio.paInt16,
                    channels=mic_channels,
                    rate=mic_samplerate,
                    input=True,
                    input_device_index=mic_idx,
                    stream_callback=mic_callback
                )
            except Exception as e:
                print(f"Failed to open microphone stream: {e}")
                mic_stream = None
                mic_info = None

        loop_stream = None
        if loop_info is not None:
            try:
                loop_channels = int(loop_info["maxInputChannels"])
                loop_samplerate = int(loop_info["defaultSampleRate"])
                loop_stream = p.open(
                    format=pyaudio.paInt16,
                    channels=loop_channels,
                    rate=loop_samplerate,
                    input=True,
                    input_device_index=loop_idx,
                    stream_callback=loop_callback
                )
            except Exception as e:
                print(f"Failed to open loopback stream: {e}")
                loop_stream = None
                loop_info = None

        if mic_info is None and loop_info is None:
            self.error_occurred.emit("Failed to open any audio streams.")
            p.terminate()
            return

        # Emit tiny status message depending on active streams
        if mic_info is not None:
            status_text = f"Listening (Shotcaller - Mic Only)"
        else:
            status_text = f"Listening (Listener - Loopback Only)"

        self.status_message.emit(status_text)

        def handle_text(text):
            text_norm = text.lower()
            if "phase one" in text_norm:
                self.command_recognized.emit("p1")
            elif "phase two" in text_norm:
                self.command_recognized.emit("p2")
            elif "phase three" in text_norm:
                self.command_recognized.emit("p3")
            elif "phase four" in text_norm:
                self.command_recognized.emit("p4")
            else:
                mapping = {
                    "meteor": "meteor",
                    "push": "push",
                    "buff": "buff",
                    "dash": "dash",
                    "fly": "dive",
                    "dive": "dive",
                    "charge": "charge",
                    "shock": "charge",
                    "shockwave": "charge",
                    "reset": "reset",
                    "stun": "stun",
                    "stunned": "stunned"
                }
                for word in text_norm.split():
                    mapped = mapping.get(word)
                    if mapped:
                        self.command_recognized.emit(mapped)

        # Start streams
        if mic_stream is not None:
            mic_stream.start_stream()
        if loop_stream is not None:
            loop_stream.start_stream()

        try:
            while not self.isInterruptionRequested() and not self._stop_requested:
                # Process microphone
                if mic_stream is not None and mic_rec is not None:
                    try:
                        data = mic_queue.get_nowait()
                        mono_data = to_mono(data, int(mic_info["maxInputChannels"]))
                        if mic_rec.AcceptWaveform(mono_data):
                            res = json.loads(mic_rec.Result())
                            text = res.get("text", "").strip()
                            if text:
                                handle_text(text)
                    except queue.Empty:
                        pass

                # Process loopback
                if loop_stream is not None and loop_rec is not None:
                    try:
                        data = loop_queue.get_nowait()
                        mono_data = to_mono(data, int(loop_info["maxInputChannels"]))
                        if loop_rec.AcceptWaveform(mono_data):
                            res = json.loads(loop_rec.Result())
                            text = res.get("text", "").strip()
                            if text:
                                handle_text(text)
                    except queue.Empty:
                        pass

                import time
                time.sleep(0.01)
        finally:
            if mic_stream is not None:
                try:
                    mic_stream.stop_stream()
                    mic_stream.close()
                except Exception:
                    pass
            if loop_stream is not None:
                try:
                    loop_stream.stop_stream()
                    loop_stream.close()
                except Exception:
                    pass
            p.terminate()

        self.status_message.emit("Speech recognition stopped.")

