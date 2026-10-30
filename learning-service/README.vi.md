# Vòng học từ lỗi có duyệt — bản đầu

Đây là hàng đợi bằng chứng + đề xuất + duyệt + xuất ca test. KHÔNG phải fine-tune,
không tự học lời khách thành sự thật và không tự thay prompt/chính sách/code.
Bản đầu phân tích theo quy tắc/thư viện bài học, chưa gọi thêm model phân tích.

## Dữ liệu và giới hạn
- Gateway tự ghi nhận metadata của phản hồi bị guard/lỗi xử lý. Thành công bình
  thường, kể cả kết quả tìm kiếm chưa toàn bộ, không tự coi là một lỗi cần học.
- Nhân viên có thể đánh dấu một mã hỗ trợ qua CLI. Không lưu đoạn chat: mọi
  trường message/reply/transcript/phone/email/address/token/URL/ID khách bị cấm.
- Chỉ mã hỗ trợ theo lượt, enum loại lỗi, tên trường và trạng thái công cụ được
  chấp nhận. Không nối session/khách với nhau. Metadata không chứng minh nguyên
  nhân; đề xuất luôn là giả thuyết cần người xem bằng chứng xác nhận.
- Kho riêng learning-review-data; 10.000 ca tối đa, SQLite giới hạn 32 MiB.
  Quyền thư mục 0700, DB/export 0600; journal DELETE, secure_delete ON. Không mã
  hóa ổ đĩa ở tầng ứng dụng; bảo vệ volume/backup thuộc cấu hình quản trị.
- Ca hết hạn sau 30 ngày, không gia hạn khi nhận trùng. Xóa liên đới đề xuất,
  audit và export cục bộ: khi đọc/khởi động và janitor mỗi 60 giây đang chạy.
  Tắt service thì việc xóa vật lý chờ lần khởi động kế tiếp. Backup phải có hạn
  lưu phù hợp. Hạn này KHÔNG tự thay retention log Coolify/DB Hermes đang có.
- Collector lỗi/đầy: bỏ lượt gửi, không retry, không chặn khách hay gọi lại AI.
  Đây là thu thập best-effort; dòng MERLY_LEARNING_* báo mất dữ liệu/thiếu config,
  không in payload, token hoặc exception thô. Hàng đợi gửi tối đa 64 phần tử.

## Phân quyền
HTTP chỉ có health và POST /v1/cases bằng ingest secret. Không có HTTP đọc hàng
đợi/duyệt/xuất hay chạy lệnh. Secret này không cho phép duyệt bài học.
Duyệt bằng CLI cục bộ trong container qua quyền quản trị Coolify của chủ shop.
Không thêm công cụ vào bot bán hàng, không bật bộ nhớ chung hay cấp root/socket.

## Luồng on-demand
Mở Terminal của container learning-review, không dùng terminal host VPS:

    python learning_cli.py report
    python learning_cli.py list
    python learning_cli.py mark MA_HO_TRO_16_HEX
    python learning_cli.py analyze
    python learning_cli.py show CASE_ID_32_HEX
    python learning_cli.py propose CASE_ID_32_HEX --recipe constraint_preservation
    python learning_cli.py review LESSON_ID_32_HEX --decision approve --owner-confirmed
    python learning_cli.py export LESSON_ID_32_HEX

Các chữ MA_*/CASE_*/LESSON_* là chỗ điền ID thật được hệ thống trả về, không
phải lệnh chạy nguyên văn. list hiển thị 100 ca mới nhất; report có tổng số.
analyze xử lý tối đa 100 ca chưa có đề xuất mỗi lần, không gọi model. Có thể đổi
recipe khi còn draft; sau duyệt nội dung được chụp cố định, sửa thư viện không
thay lén bài học đã duyệt. reject từ chối draft; revoke thu hồi approved và
xóa export cục bộ. Không thể tự thu hồi bản đã được người dùng đưa vào Git.

Export là JSON: bài học ứng viên + ca chính/đối chứng giả lập, không có mã hỗ
trợ/hội thoại thật. verification_status vẫn pending, deployment_authorized=false.
Chủ shop kiểm tra rồi mới đưa bài học/test sạch vào nhánh Git, sửa đúng lớp,
chạy hồi quy + QA live và duyệt triển khai như bình thường. JSON không tự chạy
code, tự nạp vào bot hoặc tự push Git. Không gọi kết quả giả lập là nghiệm thu AI.

Bản đầu quản trị bằng CLI; chưa có dashboard hoặc MCP đọc hàng đợi cho phiên
Telegram hiện tại. Có thể xuất báo cáo metadata để trợ lý phân tích khi cần.

## Kiểm thử bản giao
868 kiểm thử toàn repo đạt, gồm HTTP loopback thật, CLI mark/analyze/duyệt/xuất
bằng subprocess, TTL/janitor, snapshot nội dung đã duyệt, riêng tư dữ liệu,
case hồi quy schema đã sửa và đối chứng hỏng, cùng kiểm tra file đóng gói.
Gunicorn --check-config khởi tạo được factory; Compose CLI config hợp lệ,
không dùng daemon. Chưa build image Docker, chưa bật collector trên production
và chưa có nghiệm thu dữ liệu khách thật. Xem verification.json để phân biệt.
