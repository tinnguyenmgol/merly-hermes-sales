# Sửa ngân sách vòng xử lý của Merly Hermes

## Thay đổi và giới hạn

- agent.max_turns: 4 → 8. Đây là vòng gọi model trong một agent run, không phải
  số tin nhắn khách. Vẫn giữ agent.run_budget_seconds=40; không tăng concurrency,
  quota AI/Haravan, timeout HTTP hay quyền công cụ. Không đổi model/provider/pin.
- Không nới ngân sách theo từ khóa, size, màu, SKU hoặc từng câu test. Mọi lượt
  dùng cùng chính sách thực thi hữu hạn. Không thêm classifier hoặc framework.
- Startup đồng bộ đúng hai trường agent.max_turns/run_budget_seconds từ template
  vào config.yaml của SALES HOME. Vì volume tồn tại qua các lần deploy, chỉ sửa
  template không đủ để thay giá trị 4 cũ. Các trường khác được giữ nguyên.
- Ghi atomic, đọc lại sau ghi, backup config.before-sales-execution-budget-*.yaml
  với mode 0600, không tạo thêm backup khi cấu hình đã đúng. Không sao chép model
  có inline api_key vào backup mới; trường hợp đó dừng để kiểm tra cấu hình.
- SOUL chỉ được cập nhật khối MERLY_EXECUTION_POLICY và bỏ câu giới hạn ba vòng
  thuộc phiên bản cũ của ứng dụng. Giữ phần tùy chỉnh và FAQ. Không sửa profile
  default của chủ shop. Các kiểm tra symlink/marker/race vẫn fail closed.
- Hướng dẫn model tận dụng báo cáo hợp lệ trong cùng lượt, không tra từng mẫu
  lặp lại vô ích, và dành ngân sách cho câu trả lời cuối. Không làm dữ liệu lượt
  trước thành tồn hiện tại, không bỏ tiêu chí, không làm mất kiểm chứng tồn dương.

## Không che lỗi incomplete

Không đổi status incomplete thành completed; không lấy bản tóm tắt cưỡng bức
làm xác nhận tư vấn/tồn kho. Hermes pinned có thể gọi thêm một lần tóm tắt sau
khi hết iteration; max_turns=8 không có nghĩa tuyệt đối chỉ có 8 HTTP request.
Cơ chế sửa protocol cùng lượt vốn có vẫn hữu hạn theo deadline/quota hiện có;
không tự retry một lượt incomplete vì có thể phát sinh thêm chi phí.

## Xác minh

```sh
python -m pytest -q
python verify_iteration_budget_api.py
```

Bài HTTP dùng gateway thật, Hermes/AIAgent pinned thật, MCP thật và provider HTTP
ở loopback (scripted). Chặn kết nối ngoài loopback, không gọi model trả phí/kho
production. Quan sát max_iterations/run_budget_seconds của AIAgent thực sự được
khởi tạo; không mock kết quả agent hoặc sửa vòng lặp SDK.

Các chế độ: legacy (4 vòng, tái hiện incomplete/503), fixed (migrate volume cũ,
5 tool calls + câu trả lời), boundary (trả lời ở vòng 8), exhausted (vẫn dừng sau
8 vòng và không chấp nhận summary thành công). Model giả lập cố ý điều khiển
chuỗi công cụ; các bài này không chấm khả năng hiểu tiếng Việt của model thật.

## Rollout do owner phê duyệt

Push nhánh không deploy. Khi owner merge/deploy, startup sẽ migrate SALES volume.
Kiểm tra log có sales_execution_policy_ready, max_turns=8, run_budget_seconds=40;
sau đó thử hội thoại trên đúng model đang dùng. Không coi kết quả fixture là đã
nghiệm thu trợ lý bán hàng. Auxiliary PAID lane là cảnh báo riêng, không được
thay đổi trong bản này.

Rollback image không tự khôi phục hai trường đã ghi trong volume. Owner cần
khôi phục đúng hai trường từ backup trong SALES HOME nếu muốn trở lại cấu hình
cũ; không gửi file chứa cấu hình/credential ra Telegram và không sửa profile khác.
