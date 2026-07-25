import os
import urllib.request
import zipfile
import shutil
import json
import queue
import sys
import sounddevice as sd
from vosk import Model, KaldiRecognizer

MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
MODEL_ZIP = "vosk-model-small-en-us-0.15.zip"
MODEL_DIR = "model"

def download_model():
    if os.path.exists(MODEL_DIR):
        print("Model directory already exists.")
        return
    
    print(f"Downloading model from {MODEL_URL}...")
    def report_hook(block_num, block_size, total_size):
        read_so_far = block_num * block_size
        if total_size > 0:
            percent = read_so_far * 100 / total_size
            sys.stdout.write(f"\rProgress: {percent:.1f}% ({read_so_far/(1024*1024):.1f}MB / {total_size/(1024*1024):.1f}MB)")
            sys.stdout.flush()
        else:
            sys.stdout.write(f"\rDownloaded {read_so_far/(1024*1024):.1f}MB")
            sys.stdout.flush()
            
    urllib.request.urlretrieve(MODEL_URL, MODEL_ZIP, reporthook=report_hook)
    print("\nExtracting model...")
    with zipfile.ZipFile(MODEL_ZIP, 'r') as zip_ref:
        zip_ref.extractall(".")
    
    # Locate the extracted folder (e.g. vosk-model-small-en-us-0.15)
    extracted_folder = "vosk-model-small-en-us-0.15"
    if os.path.exists(extracted_folder):
        shutil.move(extracted_folder, MODEL_DIR)
        print(f"Moved {extracted_folder} to {MODEL_DIR}")
    else:
        print("Error: Extracted folder not found.")
        
    if os.path.exists(MODEL_ZIP):
        os.remove(MODEL_ZIP)
    print("Model downloaded and extracted successfully.")

def test_microphone():
    print("Initializing sounddevice and listening...")
    device_info = sd.query_devices(None, 'input')
    samplerate = int(device_info['default_samplerate'])
    print(f"Using default input device: {device_info['name']} (Sample Rate: {samplerate})")
    
    model = Model(MODEL_DIR)
    
    # We define a grammar containing our MapleStory Darknell moves to make it highly accurate
    # Valid words: meteor, push, buff, dash, fly, ultimate, charge, phase, one, two, three, four, stun, stop, reset
    words = ["meteor", "push", "buff", "dash", "fly", "ultimate", "charge", "phase", "one", "two", "three", "four", "stun", "stop", "reset", "[unk]"]
    grammar_str = json.dumps(words)
    
    rec = KaldiRecognizer(model, samplerate, grammar_str)
    
    q = queue.Queue()
    
    def callback(indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        q.put(bytes(indata))
        
    print("Listening... Speak some commands (e.g., 'meteor', 'push', 'buff', 'dash', 'fly', 'ultimate')")
    print("We will listen for 15 seconds, then stop.")
    
    stream = sd.RawInputStream(samplerate=samplerate, blocksize=8000, device=None,
                               dtype='int16', channels=1, callback=callback)
    
    import time
    start_time = time.time()
    
    with stream:
        while time.time() - start_time < 15:
            try:
                data = q.get(timeout=0.1)
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    text = res.get("text", "")
                    if text:
                        print(f"Recognized (AcceptWaveform): {text}")
                else:
                    partial = json.loads(rec.PartialResult())
                    partial_text = partial.get("partial", "")
                    if partial_text:
                        print(f"Partial: {partial_text}")
            except queue.Empty:
                pass
            except Exception as e:
                print("Error in loop:", e)
                break
                
    # Print final result
    final_res = json.loads(rec.FinalResult())
    text = final_res.get("text", "")
    if text:
        print(f"Final Recognized: {text}")
    print("Listening finished.")

if __name__ == "__main__":
    download_model()
    test_microphone()
