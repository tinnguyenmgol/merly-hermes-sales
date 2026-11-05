# Chặn vòng lặp từng lượt, không chỉ thêm prompt

## Bằng chứng
Log có nhiều lần search thiếu size và một adapter repair, tổng sát 50s. Typed
error đã đọc được nhưng model vẫn không điền size. Live đối chứng riêng: bot
nhắc đúng 42/đen rồi tìm bốn thẻ trong 15.696s. Không coi đây là bằng chứng
chuỗi 5 -> 7 -> bỏ gót đã sửa. Không quy mọi lỗi/độ chậm về một nguyên nhân.

SDK đang pin coi api_server là attended, mặc định chỉ cảnh báo. Feedback thiếu
tham số cũ bị coi thành công, không tăng bộ đếm lỗi tool.

## Thay đổi
- Dùng tool_loop_guardrails native: explicit hard_stop_enabled và stall_guards;
  dừng sau ba lỗi tool liên tiếp, exact failure có ngưỡng riêng. Không patch
  framework, tăng max_turns/timeout hay quyền.
- Tách lỗi tham số với transport: missing-size trả structuredContent-only,
  marker error ở đầu. SDK nhận lỗi chức năng cho guard per-turn nhưng không
  strike MCP connection như server chết. Không đoán size.
- Tắt warning phụ gắn vào giữa tool JSON. Thông điệp hard-stop không là stock
  evidence; không scrape/chữa JSON để chấp nhận dữ liệu.
- Sau ít nhất hai lỗi tham số và chưa có stock report, adapter không mở model
  run thứ hai. Giữ câu hỏi thiếu thông tin thật, sửa một lỗi đơn lẻ và kết quả
  nguồn hợp lệ. Fallback nhanh không đồng nghĩa tìm hàng thành công.
- Tham chiếu số size từ biến thể tồn dương ĐÃ HIỂN THỊ cùng phiên, chỉ khi có
  một size rõ ràng. Không lấy từ câu khách/tiêu đề SEO; không nâng thành lựa
  chọn/tồn hiện tại, không auto-fill args. Khách đổi ý được ưu tiên. Không chèn
  assistant message giả vào history. Giữ TTL/session/byte caps hiện có; log chỉ
  boolean size_reference_attached.

## Kiểm thử
SDK/controller thật: chính sách + feedback cũ chạy tám lỗi biến đổi không halt;
bản mới dừng ở lỗi thứ ba, MCP transport vẫn healthy. Test sửa lỗi rồi tiến
triển, reset per-turn, isolation, không mở run thứ hai, render MCP, migration
idempotent/private giữ model và caps khác. Từ chối symlink/inline model key
trước tạo backup. Kiểm TTL, phiên khác, size mơ hồ và input thay size không bị
code ghi đè. Unit tests dùng nguồn/model synthetic, không là điểm NLP live.

## Rollout còn lại
Review/merge, redeploy hermes-sales + sales-gateway. Không đổi Compose, volume,
secret; không key mới. Startup chỉ đồng bộ loop settings sở hữu trong dedicated
sales config; không sửa profile Hermes kỹ thuật, Cron, DB hay Coolify.
Log thêm loop_hard_stop_enabled, loop_guardrails_migrated, size_reference_attached
và repair_skipped_reason=repeated_argument_failures để xác minh sau rollout.

Chưa Docker build/QA live bản này. Chặn lặp không có nghĩa model hết quên size,
có mẫu 7cm tồn thật hay đạt SLA. Scan24/nguồn thiếu còn cần xử lý riêng. Giữ
live acceptance pending; không báo đã học xong.
Docs: https://hermes-agent.nousresearch.com/docs/user-guide/configuration

Bàn giao: 949 tests ứng dụng + 43 tests qa-service đạt, ba warning deprecation thư viện; offline, chưa triển khai production.
