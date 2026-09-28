"""
Automated Prototype Screenshot Capturer.
Uses headless Chrome to capture crisp, high-resolution screenshots
of all tabs and features for the Hackathon Poster & PDF.
"""

import subprocess
import time
from pathlib import Path

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUTPUT_DIR = Path(r"D:\NASA MODI VIIRS\docs\images")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TABS = [
    {"name": "screenshot_calendar.png", "url": "http://127.0.0.1:8000/?tab=tabCalendar", "size": "1400,920"},
    {"name": "screenshot_diagnostic.png", "url": "http://127.0.0.1:8000/?tab=tabDiagnostic", "size": "1400,950"},
    {"name": "screenshot_map.png", "url": "http://127.0.0.1:8000/?tab=tabMap", "size": "1400,920"},
    {"name": "screenshot_briefing.png", "url": "http://127.0.0.1:8000/?tab=tabBriefing", "size": "1400,920"},
]

def capture_all():
    for item in TABS:
        target = OUTPUT_DIR / item["name"]
        print(f"Capturing {target.name}...")
        args = [
            CHROME_PATH,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--virtual-time-budget=4500",
            f"--screenshot={target}",
            f"--window-size={item['size']}",
            item["url"]
        ]
        res = subprocess.run(args, capture_output=True, text=True)
        if target.exists():
            print(f"  [OK] {target.name} ({target.stat().st_size} bytes)")
        else:
            print(f"  [FAIL] {target.name}: {res.stderr}")

if __name__ == "__main__":
    capture_all()
