# Sửa sau đối chiếu log tra sản phẩm

## Bằng chứng và giới hạn
Gateway ghi partial/partial_available, repair_attempts=1, sát 50 giây; lượt lỗi
sau hermes_timeout ở 45.168 giây. Hermes ghi inconsistent_heel_requirement:
heel_mode có nhưng heel_cm thiếu. Hai log không cùng correlation ID: không
khẳng định lỗi tham số là nguyên nhân duy nhất của chính lượt timeout.
Collection source_unavailable, metadata chưa xác minh và phạm vi chưa quét
hết vẫn cần kiểm tra; bản sửa không tạo ra dữ liệu còn thiếu.

## Sửa có giới hạn
- Model khai báo MỘT heel_selection: chuỗi số cm hoặc unspecified. Không còn
  cặp mode/cm mâu thuẫn, không nullable/union. Kiểm literal chặt rồi chuyển
  phạm vi số chuẩn. Không parse câu khách, đoán chiều cao, sửa SKU/ID hay nới
  chứng minh tồn. Lời gọi nội bộ legacy vẫn được kiểm, không hiển thị cặp cũ
  trong schema model. Sai token/khai báo kép bị từ chối trước đọc nguồn.
- Không mở inference thứ hai nếu chỉ còn lỗi khẳng định tồn trên bằng chứng
  nguồn đã validate nhưng partial. Giữ fallback/thẻ tồn dương có nguồn; không
  biến unknown thành zero. Vẫn sửa lỗi tham số/protocol/sai scope/chiều cao.
  Không tăng timeout, vòng lặp hay quyền công cụ.
- Sales config bật auxiliary.free_only, giữ title generation tắt. SDK đã pin
  chặn OpenRouter auxiliary paid fallback trước tra credential. Không đổi
  model chính; không tuyên bố mọi provider/tác vụ đều miễn phí.
- Metadata mới: heel_argument enum (không giá trị), lý do bỏ repair và điểm
  dừng/số lượng quét. Không chat/query/tiêu đề/URL/token. Collector chỉ thêm
  tên trường vào allowlist, không tự apply.
- Audit import constant trước khi bỏ adapter khỏi sys.path, có subprocess
  bootstrap test. Giữ nguyên năm công cụ đọc.

## Kiểm chứng thật
JSON Schema từ main cũ chấp nhận exact thiếu số cm; backend phải từ chối.
Schema mới chấp nhận lựa chọn hoàn chỉnh, từ chối cặp cũ (jsonschema thật).
Test trước sửa, repair BẬT, chứng minh code cũ còn reserve lượt inference trên
partial; code mới không reserve/gọi lại. Test SDK chặn paid fallback trước
credential; migration idempotent giữ config khác. Có hồi quy 5 -> 7, unspecified,
metadata thiếu chiều cao, token sai, quote riêng tư và bootstrap schema.
Số test cuối ở báo cáo bàn giao. Chưa Docker build hoặc QA live bản sửa này;
không tuyên bố SLA/tồn thật từ fixtures.

## Rollout
Chủ hệ thống review/merge rồi redeploy đồng bộ hermes-sales, sales-gateway và
learning-review vì schema/allowlist đổi. Giữ Compose, volume, secret, model;
không cần token mới. Workspace không được deploy. Sau đó kiểm 7cm và 5 -> 7,
log heel_argument/scan_stop_reason/repair_skipped_reason; partial không pass.

## Warning khác
SQLite đã tự chọn DELETE để tránh WAL bug; chưa có bằng chứng gây timeout.
Không tự update runtime/DB production. Prompt-null/cache cần đánh giá riêng,
không bật lưu chat để hết warning. Warning API/local không chứng minh VPS
root đã lộ; audit xác nhận năm công cụ, nhưng firewall/port deployment cần
kiểm riêng. Không cấp Docker socket theo gợi ý chung của framework.

Kết quả cuối: 912 test ứng dụng đạt; 43 test qa-service đạt (3 warning deprecation thư viện). Đây là offline verification, chưa live acceptance.
