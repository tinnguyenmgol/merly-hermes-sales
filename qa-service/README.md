# Merly Chat QA — restricted HTTP MCP

**Gói này chưa được triển khai/kết nối với Hermes live.** Nó là service mới,
không phải bản sửa chatbot, không thêm công cụ cho hermes_sales.

## Chức năng

- qa_start_chat(messages, test_data_only=true): mở một phiên mới tại đúng
  https://chat.merlyshoes.com và gửi tuần tự 1–5 tin thử trong cùng phiên.
- qa_get_result(run_id, wait_seconds=20): đọc tiến độ/kết quả, chờ tối đa 20 giây,
  không gửi thêm tin. Kết quả gồm HTTP status, thời gian, reply, mã hỗ trợ, và
  thẻ sản phẩm API báo về (không phải kiểm kho Haravan độc lập).
- Dừng ở lỗi đầu tiên; không retry, không tự gửi tiếp sau lỗi. HTTP API/UI không
  dùng browser, nên chưa kiểm tra được JavaScript, ảnh hoặc iframe production.

## Rào quyền

- Không nhận tham số URL/method/header. Chỉ GET /api/public/session và POST
  /api/public/chat trên host cố định. Không redirect/proxy env; chặn địa chỉ
  private/loopback/link-local và pin IP đã kiểm tra khi kết nối TLS, SNI đúng host.
- MCP cần một secret QA mới. Không cần key model, Haravan hay Coolify.
- Chỉ một phiên đang chạy; tối đa 3 phiên và 15 tin khách/ngày UTC. Quota lưu
  riêng qua restart; đặt trước lượt, không hoàn quota khi lỗi. Lỗi giữ cooldown
  tối đa khoảng 6 phút để tránh gọi lại lượt chưa rõ kết quả.
- Đây là số tin khách, KHÔNG phải số API call model: bot có thể gọi model nhiều
  vòng cho mỗi tin. Test thật có thể tính phí và tạo lịch sử trên ứng dụng đích.
- Cookie/CSRF giữ trong RAM và được xóa tham chiếu khi kết thúc. Reply chỉ ở RAM,
  đọc trong 15 phút, dọn khi truy cập/bắt đầu phiên tiếp hoặc restart. Database
  QA chỉ lưu ngày/quota/lease, không lưu transcript, cookie hoặc secret.
- Không root/sudo/Docker socket, không mount dữ liệu sales. Image chạy UID 10001.
  Compose drop capabilities, read-only rootfs, no-new-privileges và quota tài nguyên.

## Cài đặt

Làm theo **INSTALL.vi.md**. Không pip-install gói này vào Hermes hiện có;
dùng container QA riêng để không thay dependency của các agent. Dùng nhánh qa/restricted-chat-runner cho service QA
mới; **không cần merge nhánh này vào main hoặc redeploy app bán hàng**.

## Kiểm chứng đã có

```sh
cd qa-service
python -m pytest -q
```

Đã chạy HTTP MCP thật và Hermes MCP discovery với secret lấy từ môi trường,
kiểm tra CSRF/cookie với public gateway thật nhưng model/nguồn đều giả lập.
Chặn kết nối ngoài loopback trong test. Chưa chạy lên chat production và chưa
build Docker image qua Coolify; validate Compose không tương đương deploy.

Bộ này không sửa quyền Coolify 401 hoặc tự cấp quyền đọc runtime logs. Các công
cụ Coolify hiện tại chỉ có deployment/build-log; runtime-log cần quyền/công cụ
đọc riêng hoặc chủ hệ thống xuất log, không gửi token qua Telegram.
