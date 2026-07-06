import os
import sys
import time
import datetime
import random
import subprocess
from config import get_tool_path

if sys.platform == "win32":
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0

class MetadataManager:
    def __init__(self):
        self.devices = [
            {"make": "Apple", "model": "iPhone 15 Pro Max", "software": "iOS 17.4"},
            {"make": "Apple", "model": "iPhone 14 Pro", "software": "iOS 16.5"},
            {"make": "Apple", "model": "iPhone 13 Pro", "software": "iOS 15.2"},
            {"make": "Apple", "model": "iPad Pro M2", "software": "iPadOS 17.1"},
            {"make": "Samsung", "model": "SM-S918B", "software": "Android 14"},
            {"make": "Samsung", "model": "SM-S928B", "software": "Android 14"},
            {"make": "Samsung", "model": "SM-F946B", "software": "Android 13"},
            {"make": "Google", "model": "Pixel 8 Pro", "software": "Android 14"},
            {"make": "Google", "model": "Pixel 7 Pro", "software": "Android 13"},
            {"make": "Xiaomi", "model": "23116PN5BC", "software": "HyperOS 1.0"},
            {"make": "OnePlus", "model": "CPH2581", "software": "OxygenOS 14"},
            {"make": "Sony", "model": "XQ-DQ72", "software": "Android 14"}
        ]

    def clean_and_fake_metadata(self, input_file, output_file):
        if not os.path.exists(input_file) or os.path.getsize(input_file) == 0:
            print(f"Lỗi: File nguồn tạm '{input_file}' trống hoặc không tồn tại. Bỏ qua fake metadata.")
            return False
            
        device = random.choice(self.devices)
        now = datetime.datetime.now()
        creation_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        
        cmd = [
            get_tool_path('ffmpeg'), '-y', '-i', input_file,
            '-map_metadata', '-1',
            '-c', 'copy',
            '-metadata', f'creation_time={creation_time_str}',
            '-metadata', f'make={device["make"]}',
            '-metadata', f'model={device["model"]}',
            '-metadata', f'software={device["software"]}',
            '-metadata', 'encoder=',
            '-metadata:s:v', 'handler_name=VideoHandler',
            '-metadata:s:a', 'handler_name=SoundHandler',
            output_file
        ]
        
        try:
            print(f"Đang fake metadata thành {device['make']} {device['model']}...")
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, creationflags=CREATE_NO_WINDOW)
            self._change_file_os_timestamps(output_file)
            self._append_binary_padding(output_file)
            return True
        except Exception as e:
            print(f"Lỗi khi xử lý metadata: {e}")
            return False

    def _change_file_os_timestamps(self, filepath):
        try:
            now = time.time()
            os.utime(filepath, (now, now))
        except Exception as e:
            print(f"Lỗi khi đổi timestamp HĐH: {e}")

    def _append_binary_padding(self, filepath):
        if os.path.exists(filepath):
            try:
                # Chèn từ 10 đến 100 bytes ngẫu nhiên vào cuối file để thay đổi MD5/SHA256
                padding_size = random.randint(10, 100)
                random_bytes = bytearray(random.getrandbits(8) for _ in range(padding_size))
                with open(filepath, 'ab') as f:
                    f.write(random_bytes)
                print(f"🔒 Đã chèn {padding_size} bytes ngẫu nhiên vào cuối file (Binary Padding thành công).")
                return True
            except Exception as e:
                print(f"⚠️ Không thể thực hiện Binary Padding: {e}")
        return False
