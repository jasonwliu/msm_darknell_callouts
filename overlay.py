import sys
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QFrame, QApplication
)
from PyQt6.QtGui import QColor, QPainter, QPen
import pyaudiowpatch as pyaudio
from PIL import ImageGrab
import config

class CalibrationWindow(QWidget):
    calibration_complete = pyqtSignal(list, list)  # Emits (region, color)

    def __init__(self):
        super().__init__()
        # Full screen, borderless, transparent
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.showFullScreen()

        self.start_pos = None
        self.end_pos = None
        self.is_dragging = False

    def paintEvent(self, event):
        painter = QPainter(self)
        # Draw transparent grey mask over full screen
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if self.start_pos and self.end_pos:
            # Draw red selection box
            pen = QPen(QColor(255, 0, 0, 255), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            x = min(self.start_pos.x(), self.end_pos.x())
            y = min(self.start_pos.y(), self.end_pos.y())
            w = abs(self.start_pos.x() - self.end_pos.x())
            h = abs(self.start_pos.y() - self.end_pos.y())
            
            # Clear mask inside selection box
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(x, y, w, h, QColor(0, 0, 0, 0))
            
            # Draw box border
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.drawRect(x, y, w, h)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.position().toPoint()
            self.end_pos = self.start_pos
            self.is_dragging = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.end_pos = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False
            self.end_pos = event.position().toPoint()
            
            x = min(self.start_pos.x(), self.end_pos.x())
            y = min(self.start_pos.y(), self.end_pos.y())
            w = abs(self.start_pos.x() - self.end_pos.x())
            h = abs(self.start_pos.y() - self.end_pos.y())
            
            if w > 10 and h > 10:
                region = [x, y, w, h]
                
                # Sample active HP color at 3% width, 50% height
                sample_x = x + int(0.03 * w)
                sample_y = y + int(0.5 * h)
                
                try:
                    img = ImageGrab.grab(bbox=(sample_x, sample_y, sample_x + 1, sample_y + 1))
                    pixel_color = list(img.getpixel((0, 0))[:3])
                except Exception as e:
                    # Fallback default red/orange color
                    pixel_color = [180, 20, 20]
                
                self.calibration_complete.emit(region, pixel_color)
            
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()


class OverlayWindow(QWidget):
    toggle_interaction_signal = pyqtSignal()
    calibrate_requested = pyqtSignal()
    mic_changed = pyqtSignal(int)
    listener_changed = pyqtSignal(int)
    audio_mode_changed = pyqtSignal(str)
    phase_override = pyqtSignal(int)
    reset_rotation = pyqtSignal()
    hotkey_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.is_interactive = True
        self.old_pos = None
        self.is_recording_hotkey = False

        self.init_ui()

    def init_ui(self):
        # Frame and styling
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Main Layout
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(self.main_layout)

        # Container Frame (for background styling)
        self.container = QFrame()
        self.container.setObjectName("Container")
        self.container_layout = QVBoxLayout()
        self.container_layout.setContentsMargins(12, 12, 12, 12)
        self.container.setLayout(self.container_layout)
        self.main_layout.addWidget(self.container)

        # ------------------ HUD Move Display Section ------------------
        self.hud_layout = QVBoxLayout()
        
        # Phase Indicator Label
        self.phase_label = QLabel("PHASE 1")
        self.phase_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.phase_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #ff9900; text-transform: uppercase;")
        self.hud_layout.addWidget(self.phase_label)

        self.container_layout.addLayout(self.hud_layout)

        # ------------------ Config / Interactive Controls Section ------------------
        self.control_widget = QWidget()
        self.control_layout = QVBoxLayout()
        self.control_layout.setContentsMargins(0, 8, 0, 0)
        self.control_widget.setLayout(self.control_layout)

        # Horizontal separator
        sep = QFrame()
        sep.setStyleSheet("background-color: rgba(255,255,255,0.15); min-height: 1px; max-height: 1px; border: none;")
        self.control_layout.addWidget(sep)

        # Calibration & Reset buttons
        btn_layout1 = QHBoxLayout()
        self.calibrate_btn = QPushButton("Calibrate Region")
        self.calibrate_btn.clicked.connect(self.calibrate_requested.emit)
        btn_layout1.addWidget(self.calibrate_btn)

        self.reset_btn = QPushButton("Reset Rotation")
        self.reset_btn.clicked.connect(self.reset_rotation.emit)
        btn_layout1.addWidget(self.reset_btn)
        self.control_layout.addLayout(btn_layout1)

        # Manual Phase Overrides
        phase_layout = QHBoxLayout()
        phase_layout.setContentsMargins(0, 4, 0, 4)
        for p in range(1, 5):
            btn = QPushButton(f"P{p}")
            btn.setFixedWidth(32)
            btn.clicked.connect(lambda checked, x=p: self.phase_override.emit(x))
            phase_layout.addWidget(btn)
        self.control_layout.addLayout(phase_layout)

        # Audio Mode & Selector Layout
        audio_layout = QVBoxLayout()
        audio_layout.setSpacing(4)

        # 1. Mode selection
        mode_row = QHBoxLayout()
        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet("color: white; font-size: 11px;")
        mode_row.addWidget(mode_label)
        self.mode_box = QComboBox()
        self.mode_box.addItems(["Shotcaller (Mic)", "Listener (Loopback)"])
        self.mode_box.currentIndexChanged.connect(self.on_mode_changed)
        mode_row.addWidget(self.mode_box)
        audio_layout.addLayout(mode_row)

        # 2. Mic selection (visible in shotcaller mode)
        self.mic_row_layout = QHBoxLayout()
        self.mic_label = QLabel("Mic:")
        self.mic_label.setStyleSheet("color: white; font-size: 11px;")
        self.mic_row_layout.addWidget(self.mic_label)
        self.mic_box = QComboBox()
        self.mic_box.currentIndexChanged.connect(self.on_mic_changed)
        self.mic_row_layout.addWidget(self.mic_box)
        audio_layout.addLayout(self.mic_row_layout)

        # 3. Listener loopback selection (visible in listener mode)
        self.listener_row_layout = QHBoxLayout()
        self.listener_label = QLabel("Speaker:")
        self.listener_label.setStyleSheet("color: white; font-size: 11px;")
        self.listener_row_layout.addWidget(self.listener_label)
        self.listener_box = QComboBox()
        self.listener_box.currentIndexChanged.connect(self.on_listener_changed)
        self.listener_row_layout.addWidget(self.listener_box)
        audio_layout.addLayout(self.listener_row_layout)

        self.control_layout.addLayout(audio_layout)

        # Change Hotkey button
        self.hotkey_btn = QPushButton("Hotkey: ctrl+shift+u")
        self.hotkey_btn.clicked.connect(self.start_hotkey_recording)
        self.control_layout.addWidget(self.hotkey_btn)

        self.populate_devices()

        # Hotkey / Lock Guide
        self.info_label = QLabel("Press HOTKEY to Lock/Unlock")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: #aaaaaa; font-size: 9px; margin-top: 4px;")
        self.control_layout.addWidget(self.info_label)

        # Close / Quit Button
        self.quit_btn = QPushButton("Quit App")
        self.quit_btn.setStyleSheet("background-color: rgba(200, 50, 50, 0.4); border: 1px solid red; font-size: 10px;")
        self.quit_btn.clicked.connect(QApplication.instance().quit)
        self.control_layout.addWidget(self.quit_btn)

        self.container_layout.addWidget(self.control_widget)

        # Status strip (always visible but tiny)
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 9px; color: #88ff88; margin-top: 4px;")
        self.container_layout.addWidget(self.status_label)

        # Initialize to Interactive Mode
        self.set_interactive_mode(True)

    def toggle_device_dropdowns(self, mode):
        is_shotcaller = (mode == "shotcaller")
        self.mic_label.setVisible(is_shotcaller)
        self.mic_box.setVisible(is_shotcaller)
        self.listener_label.setVisible(not is_shotcaller)
        self.listener_box.setVisible(not is_shotcaller)

    def on_mode_changed(self, index):
        mode = "shotcaller" if index == 0 else "listener"
        self.toggle_device_dropdowns(mode)
        self.audio_mode_changed.emit(mode)

    def populate_devices(self):
        self.mic_box.clear()
        self.listener_box.clear()
        
        p = pyaudio.PyAudio()
        try:
            mics = []
            listeners = []
            
            for i in range(p.get_device_count()):
                try:
                    dev = p.get_device_info_by_index(i)
                except Exception:
                    continue
                    
                if dev.get("maxInputChannels", 0) <= 0:
                    continue
                    
                name = dev.get("name", "")
                is_loopback = dev.get("isLoopbackDevice", False)
                
                if is_loopback:
                    listeners.append((i, name))
                else:
                    mics.append((i, name))
                    
            self.mics_list = mics
            self.listeners_list = listeners
            
            # Populate mic box
            for idx, name in mics:
                disp_name = (name[:25] + '...') if len(name) > 28 else name
                self.mic_box.addItem(disp_name)
                
            # Populate listener box
            for idx, name in listeners:
                disp_name = (name[:25] + '...') if len(name) > 28 else name
                self.listener_box.addItem(disp_name)
                
            # Load config to select active indices
            cfg = config.load_config()
            
            # Select active mode
            saved_mode = cfg.get("audio_mode", "shotcaller")
            if saved_mode == "shotcaller":
                self.mode_box.setCurrentIndex(0)
            else:
                self.mode_box.setCurrentIndex(1)
            self.toggle_device_dropdowns(saved_mode)
            
            # Select active mic
            saved_mic_idx = cfg.get("audio_device_index")
            if saved_mic_idx is not None:
                for combobox_idx, (real_idx, _) in enumerate(self.mics_list):
                    if real_idx == saved_mic_idx:
                        self.mic_box.setCurrentIndex(combobox_idx)
                        break
                        
            # Select active listener
            saved_listener_idx = cfg.get("listener_device_index")
            if saved_listener_idx is not None:
                for combobox_idx, (real_idx, _) in enumerate(self.listeners_list):
                    if real_idx == saved_listener_idx:
                        self.listener_box.setCurrentIndex(combobox_idx)
                        break
            
            # Select active hotkey
            saved_hotkey = cfg.get("hotkey", "ctrl+shift+u")
            self.hotkey_btn.setText(f"Hotkey: {saved_hotkey}")
        finally:
            p.terminate()

    def on_mic_changed(self, combobox_idx):
        if combobox_idx >= 0 and combobox_idx < len(self.mics_list):
            real_idx = self.mics_list[combobox_idx][0]
            self.mic_changed.emit(real_idx)

    def on_listener_changed(self, combobox_idx):
        if combobox_idx >= 0 and combobox_idx < len(self.listeners_list):
            real_idx = self.listeners_list[combobox_idx][0]
            self.listener_changed.emit(real_idx)

    def set_status(self, text, color="#88ff88"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"font-size: 9px; color: {color};")

    def start_hotkey_recording(self):
        if self.is_recording_hotkey:
            # Cancel recording if clicked again
            self.is_recording_hotkey = False
            self.hotkey_btn.setStyleSheet("")
            cfg = config.load_config()
            saved_hotkey = cfg.get("hotkey", "ctrl+shift+u")
            self.hotkey_btn.setText(f"Hotkey: {saved_hotkey}")
            self.set_status("Hotkey change cancelled", "#ffff00")
        else:
            self.is_recording_hotkey = True
            self.hotkey_btn.setText("Press key combo... (Click to Cancel)")
            self.hotkey_btn.setStyleSheet("background-color: rgba(0, 255, 255, 0.3); border: 1px solid #00ffff; font-size: 10px;")

    def keyPressEvent(self, event):
        if self.is_recording_hotkey:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.is_recording_hotkey = False
                self.hotkey_btn.setStyleSheet("")
                cfg = config.load_config()
                saved_hotkey = cfg.get("hotkey", "ctrl+shift+u")
                self.hotkey_btn.setText(f"Hotkey: {saved_hotkey}")
                event.accept()
                return

            mods = event.modifiers()
            keys = []
            
            if mods & Qt.KeyboardModifier.ControlModifier:
                keys.append("ctrl")
            if mods & Qt.KeyboardModifier.ShiftModifier:
                keys.append("shift")
            if mods & Qt.KeyboardModifier.AltModifier:
                keys.append("alt")
            if mods & Qt.KeyboardModifier.MetaModifier:
                keys.append("win")
                
            if key in [
                Qt.Key.Key_Control, Qt.Key.Key_Shift, 
                Qt.Key.Key_Alt, Qt.Key.Key_Meta
            ]:
                return
                
            key_str = self.map_key_to_keyboard(key)
            if key_str:
                keys.append(key_str)
                
            if keys:
                hotkey_str = "+".join(keys)
                self.is_recording_hotkey = False
                self.hotkey_btn.setStyleSheet("")
                self.hotkey_btn.setText(f"Hotkey: {hotkey_str}")
                self.hotkey_changed.emit(hotkey_str)
                event.accept()
        else:
            super().keyPressEvent(event)

    def map_key_to_keyboard(self, key):
        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            return chr(key).lower()
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            return chr(key)
            
        if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F12:
            return f"f{key - Qt.Key.Key_F1 + 1}"
            
        key_map = {
            Qt.Key.Key_Space: "space",
            Qt.Key.Key_Return: "enter",
            Qt.Key.Key_Enter: "enter",
            Qt.Key.Key_Tab: "tab",
            Qt.Key.Key_Backspace: "backspace",
            Qt.Key.Key_Delete: "delete",
            Qt.Key.Key_Insert: "insert",
            Qt.Key.Key_Home: "home",
            Qt.Key.Key_End: "end",
            Qt.Key.Key_PageUp: "page up",
            Qt.Key.Key_PageDown: "page down",
            Qt.Key.Key_Left: "left",
            Qt.Key.Key_Right: "right",
            Qt.Key.Key_Up: "up",
            Qt.Key.Key_Down: "down",
            Qt.Key.Key_CapsLock: "caps lock",
            Qt.Key.Key_ScrollLock: "scroll lock",
            Qt.Key.Key_NumLock: "num lock",
            Qt.Key.Key_Print: "print screen",
            Qt.Key.Key_Pause: "pause",
        }
        return key_map.get(key, None)

    def update_moves(self, phase, all_moves, current_index):
        # Update phase label
        self.phase_label.setText(f"PHASE {phase}")
        colors = {1: "#22ff22", 2: "#ff9900", 3: "#ff33aa", 4: "#ff2222"}
        self.phase_label.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {colors.get(phase, '#ffaa00')}; text-transform: uppercase;")

        # Clear existing labels in self.hud_layout (excluding phase_label which is at index 0)
        while self.hud_layout.count() > 1:
            item = self.hud_layout.takeAt(1)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        # Add all moves starting from current_index (scrolling full list layout)
        n = len(all_moves)
        for offset in range(n):
            idx = (current_index + offset) % n
            move = all_moves[idx]
            is_current = (offset == 0)
            
            lbl = QLabel(move)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if is_current:
                # Highlighted next move: large, bold, bright color, prefix with arrow
                lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #00ffff; margin-bottom: 2px;")
                lbl.setText(f"➔ {move}")
            else:
                # Upcoming moves: normal white/grey, uniform opacity
                lbl.setStyleSheet("font-size: 14px; color: rgba(255, 255, 255, 0.65);")
            
            self.hud_layout.addWidget(lbl)

    def set_interactive_mode(self, interactive):
        self.is_interactive = interactive
        
        if interactive:
            # Show configuration panel
            self.control_widget.show()
            self.status_label.show()
            
            # Setup interactive window flags (can receive mouse events, draggable)
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint | 
                Qt.WindowType.WindowStaysOnTopHint | 
                Qt.WindowType.Tool
            )
            # Styling for Setup Mode
            self.setStyleSheet("""
                #Container {
                    background-color: rgba(20, 20, 28, 0.9);
                    border: 1px solid rgba(0, 255, 255, 0.4);
                    border-radius: 8px;
                }
                QLabel {
                    font-family: 'Segoe UI', Arial, sans-serif;
                }
                QPushButton {
                    background-color: rgba(60, 60, 80, 0.6);
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    color: white;
                    border-radius: 4px;
                    padding: 4px 6px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: rgba(0, 255, 255, 0.25);
                    border: 1px solid #00ffff;
                }
                QComboBox {
                    background-color: rgba(40, 40, 50, 0.8);
                    border: 1px solid rgba(255,255,255,0.2);
                    color: white;
                    border-radius: 3px;
                    padding: 2px;
                    font-size: 11px;
                }
            """)
        else:
            # Hide configuration panel completely, leaving only transparent HUD
            self.control_widget.hide()
            self.status_label.hide()
            
            # Setup click-through window flags (clicks pass through)
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint | 
                Qt.WindowType.WindowStaysOnTopHint | 
                Qt.WindowType.WindowTransparentForInput | 
                Qt.WindowType.Tool
            )
            # Styling for HUD mode (slight dark background for contrast, rounded corners, still click-through)
            self.setStyleSheet("""
                #Container {
                    background-color: rgba(10, 10, 15, 0.45);
                    border: 1px solid rgba(255, 255, 255, 0.05);
                    border-radius: 6px;
                }
                QLabel {
                    font-family: 'Segoe UI', Arial, sans-serif;
                    background-color: transparent;
                }
            """)
        
        # Crucial: Must call show() again after changing window flags, otherwise window disappears
        self.show()

    # ------------------ Drag Handlers (Interactive Mode Only) ------------------
    def mousePressEvent(self, event):
        if self.is_interactive and event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.is_interactive and self.old_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if self.is_interactive and event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = None
            # Save final window position
            cfg = config.load_config()
            cfg["window_position"] = [self.pos().x(), self.pos().y()]
            config.save_config(cfg)
