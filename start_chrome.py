import os
import sys
import subprocess
from ai_analyzer import AIAnalyzer

analyzer = AIAnalyzer()
chrome_path = analyzer.find_chrome_path()
if chrome_path:
    print(f"Found chrome at {chrome_path}")
    profile_abs = os.path.abspath(analyzer.profile_dir)
    subprocess.Popen([
        chrome_path,
        "--remote-debugging-port=9222",
        f"--user-data-dir={profile_abs}",
        "--start-maximized",
        "https://gemini.google.com/app"
    ])
    print("Started Chrome on port 9222")
else:
    print("Chrome not found")
