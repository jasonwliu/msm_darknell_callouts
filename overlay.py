import sys
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QFrame, QApplication
)
from PyQt6.QtGui import QColor, QPainter, QPen
import sounddevice as sd
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
    phase_override = pyqtSignal(int)
    reset_rotation = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.is_interactive = True
        self.old_pos = None

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

        # Move 1 (Current / Next)
        self.move1_label = QLabel("Waiting...")
        self.move1_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.move1_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #00ffff; margin-bottom: 2px;")
        self.hud_layout.addWidget(self.move1_label)

        # Move 2 (Following)
        self.move2_label = QLabel("")
        self.move2_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.move2_label.setStyleSheet("font-size: 14px; color: rgba(255, 255, 255, 0.7); margin-bottom: 1px;")
        self.hud_layout.addWidget(self.move2_label)

        # Move 3 (Third)
        self.move3_label = QLabel("")
        self.move3_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.move3_label.setStyleSheet("font-size: 11px; color: rgba(255, 255, 255, 0.4);")
        self.hud_layout.addWidget(self.move3_label)

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

        # Audio Selector
        audio_layout = QHBoxLayout()
        audio_label = QLabel("Mic:")
        audio_label.setStyleSheet("color: white; font-size: 11px;")
        audio_layout.addWidget(audio_label)

        self.mic_box = QComboBox()
        self.populate_mics()
        self.mic_box.currentIndexChanged.connect(self.on_mic_changed)
        audio_layout.addWidget(self.mic_box)
        self.control_layout.addLayout(audio_layout)

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

    def populate_mics(self):
        self.mic_box.clear()
        devices = sd.query_devices()
        input_devices = []
        
        # Retrieve all input devices
        for idx, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                input_devices.append((idx, dev['name']))
        
        # Add to box
        self.mics_list = input_devices
        for idx, name in input_devices:
            # truncate name for clean layout
            disp_name = (name[:25] + '...') if len(name) > 28 else name
            self.mic_box.addItem(disp_name)

        # Match loaded config
        cfg = config.load_config()
        saved_idx = cfg.get("audio_device_index")
        if saved_idx is not None:
            for combobox_idx, (real_idx, _) in enumerate(self.mics_list):
                if real_idx == saved_idx:
                    self.mic_box.setCurrentIndex(combobox_idx)
                    break

    def on_mic_changed(self, combobox_idx):
        if combobox_idx >= 0 and combobox_idx < len(self.mics_list):
            real_idx = self.mics_list[combobox_idx][0]
            self.mic_changed.emit(real_idx)

    def set_status(self, text, color="#88ff88"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"font-size: 9px; color: {color};")

    def update_moves(self, phase, next_moves):
        # Update phase label
        self.phase_label.setText(f"PHASE {phase}")
        colors = {1: "#22ff22", 2: "#ff9900", 3: "#ff33aa", 4: "#ff2222"}
        self.phase_label.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {colors.get(phase, '#ffaa00')}; text-transform: uppercase;")

        # Update labels
        if len(next_moves) >= 1:
            self.move1_label.setText(next_moves[0])
        else:
            self.move1_label.setText("Waiting...")
            
        self.move2_label.setText(next_moves[1] if len(next_moves) >= 2 else "")
        self.move3_label.setText(next_moves[2] if len(next_moves) >= 3 else "")

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
