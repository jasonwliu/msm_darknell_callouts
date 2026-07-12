import time
import asyncio
from PyQt6.QtCore import QThread, pyqtSignal
from PIL import ImageGrab
import numpy as np

class ScreenTrackerThread(QThread):
    phase_changed = pyqtSignal(int)
    status_message = pyqtSignal(str)

    def __init__(self, config_loader_func):
        super().__init__()
        self.config_loader = config_loader_func
        self._stop_requested = False
        self.current_phase = 1

    def stop(self):
        self._stop_requested = True
        self.requestInterruption()

    def is_color_match(self, color1, color2, threshold=65):
        """Calculate Euclidean distance in RGB space to determine color match."""
        if color1 is None or color2 is None:
            return False
        r1, g1, b1 = color1
        r2, g2, b2 = color2
        dist = np.sqrt((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2)
        return dist < threshold

    def is_predominantly_green(self, pixel):
        """Check if a pixel has a predominantly green hue (for Maplestory M HP bar)."""
        r, g, b = pixel[:3]
        return g > 90 and g > r + 30 and g > b + 30

    def check_column_filled(self, img, x, h, filled_color):
        """
        Check if a column is filled by scanning the entire vertical column of pixels at x.
        Relying exclusively on the green hue check ensures that we never match the dark
        purple background even if the user incorrectly calibrates the color box.
        """
        if x < 0 or x >= img.width:
            return False
        
        green_pixel_count = 0
        for y in range(img.height):
            pixel = img.getpixel((x, y))[:3]
            if self.is_predominantly_green(pixel):
                green_pixel_count += 1
                
        # If we find at least 2 green pixels in the column, it is filled.
        # This is extremely robust and works whether the user's calibration box is thin (12px)
        # or tall (40px+), as the background and text contain no green hues.
        return green_pixel_count >= 2

    def detect_nameplate_bounds(self, img):
        """
        Detect the left and right boundaries of the purple boss nameplate box.
        This provides leniency if the user includes extra pixels on either side.
        """
        w, h = img.size
        left = 0
        right = w - 1
        
        # Scan from left to find first column containing nameplate pixels
        # Nameplate border and background contain blue/purple tones (B channel > 45, B > R + 10)
        for x in range(w):
            has_blue = False
            for y in range(h):
                r, g, b = img.getpixel((x, y))[:3]
                if b > 45 and b > r + 10:
                    has_blue = True
                    break
            if has_blue:
                left = x
                break
                
        # Scan from right to find last column containing nameplate pixels
        for x in range(w - 1, -1, -1):
            has_blue = False
            for y in range(h):
                r, g, b = img.getpixel((x, y))[:3]
                if b > 45 and b > r + 10:
                    has_blue = True
                    break
            if has_blue:
                right = x
                break
                
        if right <= left:
            return 0, w - 1
        return left, right

    def run(self):
        self._stop_requested = False
        self.status_message.emit("Screen tracker started.")
        
        # Debouncing history: we require 3 consecutive identical reads to switch phase
        read_history = []
        history_len = 3

        while not self.isInterruptionRequested() and not self._stop_requested:
            # Sleep 500ms
            self.msleep(500)
            
            config = self.config_loader()
            region = config.get("ocr_region")
            filled_color = config.get("filled_hp_color")
            
            if not region:
                # Screen tracker is running but not calibrated yet
                continue
            
            x, y, w, h = region
            if w <= 0 or h <= 0:
                continue

            try:
                # Capture the calibrated HP bar region
                img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
                
                # Detect the actual nameplate boundaries inside the captured image (add calibration leniency)
                left, right = self.detect_nameplate_bounds(img)
                actual_w = right - left + 1
                
                # Verify that the HP bar is active/visible by checking the left edge (8% width of nameplate)
                hp_bar_active = self.check_column_filled(img, left + int(0.08 * actual_w), h, filled_color)
                
                if not hp_bar_active:
                    # In lobby or boss is dead: clear history and skip phase detection
                    read_history.clear()
                    continue
                
                # Check column fill status at character-aligned landmarks relative to actual nameplate
                # Phase 2: near the "n" in "Darknell" (~73% of nameplate width)
                # Phase 3: between "ar" in "Darknell" (~65% of nameplate width)
                # Phase 4: in the "d" in "Guard" (~35% of nameplate width)
                filled_p4 = self.check_column_filled(img, left + int(0.35 * actual_w), h, filled_color)
                filled_p3 = self.check_column_filled(img, left + int(0.65 * actual_w), h, filled_color)
                filled_p2 = self.check_column_filled(img, left + int(0.73 * actual_w), h, filled_color)
                
                # Log debug info to console (will appear in task logs)
                print(f"[Tracker] Active={hp_bar_active} | p4(35%)={filled_p4} | p3(65%)={filled_p3} | p2(73%)={filled_p2}")
                
                # Determine detected phase
                if not filled_p4:
                    detected = 4
                elif not filled_p3:
                    detected = 3
                elif not filled_p2:
                    detected = 2
                else:
                    detected = 1
                
                # Add to debounce history
                read_history.append(detected)
                if len(read_history) > history_len:
                    read_history.pop(0)
                
                # If history is full and all reads are identical, check if it differs from current phase
                if len(read_history) == history_len and len(set(read_history)) == 1:
                    stable_phase = read_history[0]
                    if stable_phase != self.current_phase:
                        self.current_phase = stable_phase
                        self.phase_changed.emit(stable_phase)
                        self.status_message.emit(f"Auto-detected Phase {stable_phase} from HP bar boundary.")
                        
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.status_message.emit(f"Tracker Error: {str(e)}")

        self.status_message.emit("Screen tracker stopped.")
