# Hai phần chủ hệ thống phải thực hiện

Assistant hiện chỉ có Workspace offline và công cụ Coolify đang lỗi 401, không
có quyền tạo service hay sửa profile Hermes. Vì vậy các bước dưới chưa được làm.
Không gửi key/token hoặc ảnh lộ secret vào Telegram.

## 1. Tạo app QA MỚI trong Coolify

Không clone nguyên app sales vì có thể mang theo secret/volume không cần thiết.

- Repository: tinnguyenmgol/merly-hermes-sales.
- Branch: qa/restricted-chat-runner. KHÔNG dùng main cho app QA này.
- Chọn Docker Compose, thư mục gốc build là /qa-service; dùng compose.qa.yaml
  trong thư mục đó. Dockerfile đi kèm chỉ đóng gói ba module QA và requirements.
- Cấp domain HTTPS cho service merly_chat_qa, container port 8080. Hostname phải
  có DNS/routing hợp lệ; tài liệu này không tạo sẵn bất kỳ domain nào.
- Dùng volume qa_limits RIÊNG. Không mount config, database, deploy key, Docker
  socket hoặc thư mục /data/hermes-sales của bất kỳ app nào khác.
- Đặt biến runtime trong Coolify (không phải build arguments):
  - MERLY_QA_AUTH_TOKEN: secret mới, URL-safe 32–128 ký tự. Có thể tạo riêng bằng
    secrets.token_urlsafe(48) trong terminal quản trị tin cậy; không in vào chat.
  - MERLY_QA_PUBLIC_HOST: hostname QA vừa gán, chữ thường, không https://,
    không /mcp và không port.
  - MERLY_QA_LIVE_TESTS_APPROVED: mặc định 0. Đặt 1 khi owner đồng ý phí model
    và lưu lượng thử bằng dữ liệu giả; phạm vi tối đa 10 phiên/50 tin khách/ngày.
- Deploy app QA. Health check /health chỉ xác nhận service sống, không chứng
  minh đã được duyệt gọi live hoặc bot đích hoạt động.

Không cần cung cấp OPENROUTER_API_KEY, HARAVAN_ACCESS_TOKEN hay token Coolify
cho service này. Không nới quyền hoặc thêm công cụ vào hermes_sales.

## 2. Kết nối vào Hermes KỸ THUẬT đang nhắn Telegram

- Ở môi trường secret của đúng Hermes kỹ thuật, đặt:
  - MERLY_QA_MCP_URL = URL HTTPS của service QA, kết thúc bằng /mcp.
  - MERLY_QA_AUTH_TOKEN = cùng secret QA đã đặt ở service mới.
- Merge entry từ hermes-mcp.example.yaml vào mcp_servers hiện có, không ghi đè
  các server Workspace/Coolify hay toàn bộ config. Không dán token thật vào YAML.
- Cho phép đúng group merly_chat_qa và hai tool của nó ở nền tảng Telegram theo
  cấu hình tools của runtime; không bật tất cả toolsets. Không chỉnh profile khác.
- Reload/restart gateway Hermes kỹ thuật theo cách quản trị đang dùng.
- Kiểm tra Hermes nhìn thấy:
  - mcp__merly_chat_qa__qa_start_chat
  - mcp__merly_chat_qa__qa_get_result

Nếu báo 401: kiểm tra secret/header của app QA, không phải key model.
Nếu báo 421: kiểm tra Host/routing domain, không tắt kiểm tra Host hoặc TLS.
Nếu tool báo live_testing_not_approved: owner chưa bật cờ ở app QA; chỉnh cờ
rồi redeploy app QA nếu cần, không redeploy app bán hàng.

## Chốt nghiệm thu

Sau khi công cụ thật xuất hiện, mới chạy một phiên gồm các tin giả lập ngắn,
đọc qa_get_result tới khi completed/failed, đối chiếu reply/card/HTTP/mã hỗ trợ.
Không gửi lại tự động nếu lỗi, timeout hoặc mất kết nối. Tool không bỏ qua rate
limit của bot, nên 429 cũng là kết quả cần ghi nhận, không phải lý do lặp vô hạn.
HTTP tool không sửa backend, đọc DB, đặt đơn hay biết tồn kho ngoài dữ liệu API
chat trả về. Browser và runtime-log reader không nằm trong gói cài này.

Tham khảo cấu hình MCP chính thức:
https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference
