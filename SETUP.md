# Hướng dẫn Thiết lập Môi trường (AI Video Processor)

Dự án này chạy trên Windows và xử lý video tự động bằng Python và FFmpeg.

## Yêu cầu Hệ thống
- Hệ điều hành: Windows 10/11
- Python: Phiên bản >= 3.8 (Khuyên dùng Python 3.10 hoặc 3.11)
- FFmpeg & FFprobe: Được nhúng sẵn tại thư mục gốc của nguồn (`ffmpeg.exe`, `ffprobe.exe`) hoặc có trong PATH hệ thống.

## Các Bước Thiết lập

1. **Cài đặt thư viện Python phụ thuộc:**
   Mở PowerShell tại thư mục nguồn và chạy:
   ```powershell
   pip install -r requirements.txt
   ```

2. **Cấu hình biến môi trường:**
   Sao chép `.env.example` thành `.env` và điền khóa API của bạn nếu cần:
   ```powershell
   copy .env.example .env
   ```

3. **Kiểm tra môi trường:**
   Chạy script kiểm tra tích hợp để đảm bảo mọi thứ đã sẵn sàng:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/check.ps1
   ```

## Hướng dẫn Chạy Ứng dụng
- Chạy qua giao diện đồ họa GUI:
  ```powershell
  python gui.py
  ```
- Chạy batch xử lý qua dòng lệnh CLI:
  ```powershell
  python main.py --mode auto
  ```
