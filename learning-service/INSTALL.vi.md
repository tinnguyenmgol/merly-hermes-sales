# Bật vòng học có duyệt trên Coolify

## Trước khi bật
- Không cần cấp SSH/root/sudo/Docker socket, không thêm tool vào hermes-sales.
- Tạo secret MỚI MERLY_LEARNING_INGEST_TOKEN dài 32–128 ký tự chữ/số/_/-.
  Giữ trong Coolify runtime secret, không Telegram/Git/build log; không dùng
  lại key Haravan/model/Coolify/QA. Không dán giá trị secret vào Compose.
- Collector dùng thêm tối đa 128 MiB RAM, 0.25 CPU, volume riêng. Kiểm tra VPS
  còn tài nguyên trước. Không có domain hay cổng host mới cần mở.

## Cấu hình
1. Merge nhánh feature sau review. Compose cũ giữ nguyên, thu thập mặc định TẮT;
   merge code không tự bật thu thập dữ liệu khách.
2. Đối chiếu Compose đang chạy với compose.hermes.json trong repo. Nếu giống,
   chọn Compose Location /compose.hermes-learning.json ở ĐÚNG app bán hàng.
   File mới giữ stack gốc, thêm learning-review và hai biến gateway.
3. Nếu đã chỉnh Compose trực tiếp ở Coolify, KHÔNG ghi đè cấu hình riêng. Chỉ
   ghép service learning-review, volume learning-review-data và hai biến gateway
   từ file mới; giữ nguyên các volume, key, model, port và giới hạn hiện có.
4. Đặt ingest secret vào môi trường phù hợp; kiểm tra nó được truyền vào
   learning-review và sales-gateway. Không đưa secret vào prompt/MCP config,
   không nới môi trường cho công cụ hoặc profile khác.
5. Build/deploy theo phê duyệt của chủ hệ thống. Gateway không phụ thuộc health
   collector để trả khách. Không sửa app QA, reset quota hoặc xóa volume cũ.

## Kiểm tra trạng thái THẬT sau triển khai
Mở Terminal container learning-review bằng quyền quản trị Coolify:

    python learning_cli.py report

Báo cáo phải có retention_days=30, auto_apply=false, model_calls=0. Số ca tùy
lưu lượng; tài liệu không khẳng định service đã cài hoặc đã nhận telemetry.
Health chỉ chứng minh service sống. Có thể mark một mã lỗi THẬT từ log rồi chạy
analyze như README.vi.md; không tạo mã giả rồi coi là một lỗi production thật.

## Duyệt và kiểm thử
- CLI cục bộ cần --owner-confirmed; không duyệt qua HTTP hay lời khách.
- Export chỉ sau duyệt ở /data/approved-exports, không có chat thô/mã hỗ trợ.
  Chỉ đưa bài học và ca test JSON sạch đã xem xét vào nhánh Git.
- Export vẫn ghi verification pending/deployment_authorized=false. Cần thực sự
  sửa, chạy hồi quy, QA live và duyệt rollout. Không báo model đã học chỉ vì
  approve. Nội dung đã duyệt được chụp cố định, không sửa lén theo recipe.
- Bản đầu quản trị qua CLI, chưa có connector để Hermes Telegram đọc queue.
  Không cấp shell production cho trợ lý để bù vào phần đó.

## Tắt/rollback
Đặt MERLY_LEARNING_ENABLED=0 trong gateway hoặc trở lại Compose cũ đã đối chiếu,
rồi redeploy theo quyền quản trị. Không xóa volume để né retention/audit. Khi
collector tắt, janitor chỉ chạy lại lúc khởi động; backup phải quản trị độc lập.
Revoke xóa export cục bộ, không tự revert code đã được merge/deploy.
