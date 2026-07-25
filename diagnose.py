import os
import ctypes
import sys

# Enable Windows DPI awareness to align coordinates 1:1
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import asyncio
from PIL import ImageGrab
import winocr
import config
from screen_tracker import ScreenTrackerThread

async def main():
    cfg = config.load_config()
    region = cfg.get("ocr_region")
    filled_color = cfg.get("filled_hp_color")
    
    if not region:
        print("Error: No region calibrated in config.json yet.")
        return
        
    x, y, w, h = region
    print(f"Current Calibrated Region: x={x}, y={y}, width={w}, height={h}")
    print(f"Calibrated HP Color: {filled_color}")
    
    # 1. Capture HP Bar Region
    try:
        hp_img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        hp_img.save("debug_hp_bar.png")
        print("Saved calibrated HP bar region to 'debug_hp_bar.png'")
    except Exception as e:
        import traceback
        print(f"Failed to capture HP bar region: {e}")
        traceback.print_exc()
        return

    # 2. Calculate and capture Timer Region
    tx = max(0, x + int(0.32 * w))
    ty = max(0, y - int(1.3 * h))
    tw = int(0.36 * w)
    th = int(0.95 * h)
    print(f"Computed Timer Region: x={tx}, y={ty}, width={tw}, height={th}")
    
    try:
        timer_img = ImageGrab.grab(bbox=(tx, ty, tx + tw, ty + th))
        timer_img.save("debug_timer.png")
        print("Saved computed Timer region to 'debug_timer.png'")
    except Exception as e:
        print(f"Failed to capture Timer region: {e}")
        return

    # 3. Perform OCR on Timer Region
    print("\n--- Running Windows OCR on Timer Region ---")
    try:
        res = await winocr.recognize_pil(timer_img, 'en')
        print(f"OCR Detected Text: '{res.text}'")
        timer_text_lower = res.text.lower()
        is_active = "time" in timer_text_lower or ":" in timer_text_lower
        print(f"Is Timer Active? {is_active} (looking for 'time' or ':')")
    except Exception as e:
        print(f"OCR failed: {e}")

    # 4. Check Checkpoint Pixels
    print("\n--- Checkpoint Pixel Analysis ---")
    tracker = ScreenTrackerThread(config.load_config)
    
    checkpoints = {
        "Presence check (8%)": int(0.08 * w),
        "Phase 4 check (36%)": int(0.36 * w),
        "Phase 3 check (65%)": int(0.65 * w),
        "Phase 2 check (73%)": int(0.73 * w)
    }
    
    for name, cx in checkpoints.items():
        print(f"\n{name} at x={cx}:")
        green_pixel_count = 0
        samples = []
        for y in range(hp_img.height):
            pixel = hp_img.getpixel((cx, y))[:3]
            is_green = tracker.is_predominantly_green(pixel)
            if is_green:
                green_pixel_count += 1
            if y % max(1, hp_img.height // 4) == 0 or y in [0, hp_img.height - 1]:
                samples.append(f"y={y}: RGB={pixel} (is_green={is_green})")
        
        filled_column = green_pixel_count >= 2
        print(f"  Samples: {', '.join(samples)}")
        print(f"  Green/Calibrated Pixel Count: {green_pixel_count}/{hp_img.height} (Required: 2)")
        print(f"  -> Column Filled? {filled_column}")

if __name__ == "__main__":
    asyncio.run(main())
