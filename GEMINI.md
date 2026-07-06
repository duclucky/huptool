# Agent Working Rules

## Honesty
- Không được khẳng định điều gì nếu chưa kiểm chứng bằng file, log, command hoặc test.
- Nếu chưa chắc, phải nói "chưa xác minh".
- Không được nói "đã fix" nếu chưa chạy command kiểm tra.

## Workflow
Mọi task phải đi theo flow:
1. Inspect (Khảo sát các file hiện có, log và cấu trúc dự án)
2. Plan (Lập kế hoạch triển khai chi tiết qua implementation_plan.md)
3. Patch (Sửa đổi code cẩn thận, bảo tồn các logic không liên quan)
4. Verify (Chạy các script kiểm tra và test suite để xác minh thực tế)
5. Report (Báo cáo kết quả rõ ràng)

## Patch policy
- Sửa ít nhất có thể.
- Không refactor ngoài phạm vi task.
- Không tạo file mới nếu có thể sửa file cũ.
- Không xóa code nếu chưa giải thích lý do.

## Verification
- Sau khi sửa, phải chạy lệnh check chuẩn của repo (scripts/check.ps1).
- Nếu lệnh check fail, phải báo log thật.
- Nếu không chạy được, phải nói rõ lý do.

## Final report format
Cuối mỗi task phải báo:
- Files changed: (Danh sách file thay đổi)
- Commands run: (Các lệnh đã thực thi kèm kết quả)
- Result: (Mô tả kết quả đạt được kèm bằng chứng thực tế)
- Remaining risks: (Rủi ro còn tồn tại nếu có)
