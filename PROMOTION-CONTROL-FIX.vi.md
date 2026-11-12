# Khuyến mãi: no-data control bị hiểu nhầm là lỗi thực thi

## Phạm vi xác minh
Người dùng cung cấp fallback với diagnostic_id b399ac6975b9039f. Chưa có runtime
log của ID này; không khẳng định đã đọc log production hoặc xác nhận nguyên
nhân duy nhất của lượt đó. QA live chưa được phê duyệt, không chạy lại công cụ.

Đã tái hiện đúng câu fallback bằng callback MCP thật, producer mặc định của
repository và renderer pinned Hermes SDK, không gọi Haravan hay model trả phí:
- get_promotions trả publication_not_configured, offers=[],
  shop_has_no_offers=false, isError=false: chưa có danh sách chiến dịch được duyệt,
  KHÔNG có nghĩa shop không ưu đãi hoặc FAQ tài khoản mất hiệu lực.
- Consumer usable chỉ nhận reference_only nên đánh dấu rejected_tool_evidence,
  thay cả câu tư vấn native bằng lỗi chung dù approved FAQ vẫn sẵn có.
- Prompt vốn đã phân biệt chiến dịch với FAQ; lỗi nằm ở contract consumer.

## Sửa
Nhận đúng no-data control ba trường của chính tool get_promotions, args phải
rỗng, offers phải rỗng và shop_has_no_offers phải boolean false. Đây là kết quả
thực thi hợp lệ, không là chứng cứ có/không chiến dịch hay đã đủ điều kiện.
Không chặn câu native dựa trên nguồn FAQ đã duyệt chỉ vì catalog chưa công bố.
Không route theo câu khách, không câu trả lời mẫu mới, không sửa prompt.

Không chấp nhận control có offer, giá, stock report, quyền áp dụng/cộng dồn,
status lỗi, sai tool hoặc sai args. JSON hỏng/SDK error/incomplete trace vẫn
fail closed. Không đổi publication allowlist, secret, Haravan, max_turns,
timeout, cấu hình native guard, hay chính sách giảm giá.

## Bằng chứng và rollout
Đối chứng mã main cũ + pinned renderer: guard rejected_tool_evidence, mất câu
native. Bản mới cùng trace: guard rỗng, giữ câu native. Đây là scripted provider,
không phải điểm NLP live. Có test callback, mixed FAQ, không mở repair run,
WSGI HTTP thật nội bộ và log không chứa câu khách; test các shape giả/malformed.

978 tests ứng dụng và 43 tests qa-service đạt; ba warning deprecation thư viện.
Chưa Docker build/deploy/live bản sửa. Thay đổi runtime chỉ tool_evidence.py
phía sales-gateway; review/merge rồi rebuild/redeploy gateway, không cần token
hoặc quyền mới. Không cần đổi service Hermes để nhận patch consumer này.

Trước khi kết luận chính ca b399ac6975b9039f, cần dòng MERLY_CHAT_COMPLETED hoặc
MERLY_CHAT_FAILED tương ứng trong log sales-gateway (metadata, không transcript).
Sau rollout test hỏi ưu đãi chung, khách mới/cũ, chiến dịch riêng, có cộng dồn
không, và nguồn chiến dịch lỗi. Không chốt mọi câu CSKH đã đạt từ unit tests.
