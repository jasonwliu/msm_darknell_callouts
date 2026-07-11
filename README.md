# MapleStory M - Guard Captain Darknell Helper

A real-time, transparent desktop HUD overlay designed to assist MapleStory M players in tracking Guard Captain Darknell's attack patterns and rotations. The helper runs locally, utilizes offline voice recognition (Vosk) to advance boss moves/handle stun-skips, and automatically tracks HP bar levels to transition boss phases.

---

## ✨ Features

- **🎮 Glassmorphic HUD Overlay**: A floating, stays-on-top, click-through overlay showing the next 3 moves in the boss's rotation. Backed by a semi-transparent panel for legibility against bright skill animations.
- **🎙️ Offline Voice Commands (Vosk)**: Hands-free sequence progression. Say moves out loud to advance, reset, or change phases. Configured with a localized speech vocabulary for sub-200ms latency.
- **⚡ Stun-Skip Lookahead**: When Darknell gets stunned and skips moves, speak his current move out of sequence. The engine immediately scans ahead (up to 3 moves) and advances the HUD.
- **🔍 Active HP Tracking**: Auto-detects boss phases (Phase 1, 2, 3, 4) by sampling the boss's HP bar width.
  - **No-OCR Green Density Scanning**: Runs a vertical pixel-density hue scanner that is immune to centered text overlays ("Guard Captain Darknell"), resolution scaling, or accidental click calibrations.
  - **Lobby/Death Detection**: Detects if you are in a lobby, loading screen, or town, and pauses tracking automatically until the green HP bar appears.
- **⌨️ System-Wide Global Hotkey**: Press `Ctrl+Shift+U` at any time (even while in-game) to toggle between **HUD Mode** (click-through, stays-on-top) and **Setup Mode** (draggable, buttons and audio configurations active).

---

## 🛠️ Prerequisites

- **Operating System**: Windows 10 or 11 (requires Windows GDI for desktop capture).
- **Python**: Python 3.10 to 3.13.

---

## 📦 Installation

1. **Clone or Download** this repository to a folder on your local machine:
   ```bash
   git clone https://github.com/<your-username>/darknell_callouts.git
   cd darknell_callouts
   ```

2. **Install Dependencies**:
   Open a terminal in the folder and run:
   ```bash
   pip install -r requirements.txt
   ```
   *Required packages: `PyQt6`, `sounddevice`, `vosk`, `pillow`, `numpy`, `keyboard`, `winocr`.*

3. **Vosk Speech Model (Automatic)**:
   On first startup, if the Vosk speech recognition model directory is missing, the application will automatically download the lightweight English voice model (`model-en-us-0.22-lgroup` or similar) in the background.

---

## 🚀 Running the App

Double-click the **`run_helper.bat`** file located in the project folder. This opens a terminal window in your active desktop session (Session 1), allowing the screen capture thread to read the HP bar values.

---

## ⚙️ Initial Setup & Calibration

Upon launching the application:
1. The app starts in **Setup Mode** (opaque container box with borders and controls).
2. **Select Microphone**: Choose your input microphone from the audio device dropdown.
3. **Calibrate HP Region**:
   - Open MapleStory M (configured in windowed or borderless windowed mode).
   - In the helper app, click **Calibrate Region**.
   - Your screen will dim. Click and drag a tight box enclosing the **entire boss name and HP bar container** at the top center of your game window.
   - Release the mouse. The coordinates will save persistently to `config.json`.
4. **Lock & Play**:
   - Press `Ctrl+Shift+U` to lock the overlay into **HUD Mode**.
   - The configuration controls will hide, the background will become a translucent dark panel, and clicks will pass straight through the HUD to the game window.

---

## 🗣️ Spoken Commands Reference

| Voice Command | Action | Description |
| :--- | :--- | :--- |
| **"Meteor"** | Advance move | Confirms Darknell completed a Meteor attack. |
| **"Push"** | Advance move | Confirms Darknell completed a Push attack. |
| **"Buff"** | Advance move | Confirms Darknell completed a Buff cast. |
| **"Dash"** | Advance move | Confirms Darknell completed a Dash. |
| **"Fly"** | Advance move | Confirms Darknell completed a Fly. |
| **"Charge"** | Advance move | Confirms Darknell completed a Charge (P2/P3/P4). |
| **[Expected Move]** | Stun skip | If Darknell skips 1–3 moves due to a stun, speak the current move he is performing. The HUD matches the command and skips ahead. |
| **"Phase One"** | Manual Override | Sets the HUD sequence to Phase 1. |
| **"Phase Two"** | Manual Override | Sets the HUD sequence to Phase 2. |
| **"Phase Three"** | Manual Override | Sets the HUD sequence to Phase 3. |
| **"Phase Four"** | Manual Override | Sets the HUD sequence to Phase 4. |
| **"Reset"** | Reset rotation | Restarts the current phase rotation back to move index 0. |

---

## 🗂️ Project Directory Structure

```
darknell_callouts/
│
├── config.py           # Persistent configuration loader/writer (config.json)
├── rotation.py         # Rotation sequence mappings, stun skip, and pattern rules
├── voice.py            # Offline Vosk audio capture loop QThread
├── screen_tracker.py   # Green HP bar pixel-density tracking QThread
├── overlay.py          # PyQt6 Glassmorphic click-through HUD & calibration windows
├── main.py             # System hooks, initialization, and thread connectors
│
├── run_helper.bat      # Windows batch launcher (runs app in Session 1)
├── diagnose.py         # Troubleshooting tool to check OCR and pixel checkpoints
├── test_rotation.py    # Pytest test suite proving skips/transitions (8/8 passing)
├── requirements.txt    # Python library requirements list
└── README.md           # Documentation (this file)
```

---

## 🔧 Troubleshooting

### HP Detection Is Not Updating Phases
- **Run direct, not via remote shell**: Ensure you are starting the app by double-clicking `run_helper.bat` or executing `python main.py` in your terminal directly. If run under service managers or remote shells, Windows blocks Session 0 screenshots.
- **Recalibrate**: If the MapleStory M window is moved or resized, press `Ctrl+Shift+U` to unlock, click **Calibrate Region**, and drag a tight box over the HP bar header again.
- **Run Diagnostics**: Close the helper app, open a command prompt in the directory, and run:
  ```bash
  python diagnose.py
  ```
  Check the generated `debug_hp_bar.png` to confirm that the captured region aligns with the game window's HP bar.

### Voice Commands Not Recognized
- Confirm the correct microphone device is selected in Setup Mode.
- Speak clearly into the microphone. Since the recognizer is offline, it performs best when microphone gain is balanced and background noise is minimal.
