# Hermes-led dialogue — bản refactor, chưa nghiệm thu AI thật

## Thay đổi
- Giữ Hermes/framework/provider/model/toolset hiện có. Không thêm classifier hay
  model để viết lại câu trả lời. Mỗi lượt cần AI gửi một request Responses; Hermes
  vẫn tự chạy các vòng công cụ trong giới hạn cấu hình hiện có.
- /api/chat không gọi conversation.prepare/observe, không ép slot bằng regex,
  không dùng request_resolution/direct_stock để tự tra bù sau khi agent kết thúc.
  Hermes nhận nguyên văn câu khách, lịch sử và schema của năm công cụ read-only.
- Chỉ giữ shortcut hoàn chỉnh: FAQ độc lập đã duyệt và một mã+size rõ ràng để tra
  tồn. Câu nối tiếp, tư vấn và tìm theo tiêu chí đi vào Hermes. Không mở rộng bộ
  câu shortcut. Mã có dạng đơn vị đo được chuyển cho Hermes trừ khi ghi rõ SKU/mã.
- Giữ lời trả lời native khi bằng chứng hợp lệ. Thẻ sản phẩm/tồn và link lấy từ
  output công cụ thật, không parse JSON do model viết trong văn bản.
- Kiểm tra tương quan call_id, trạng thái, thời điểm, phạm vi, số lượng, giá và
  nguồn theo contract. Lỗi schema đã được agent sửa trong cùng lượt không bị nhầm
  thành một lượt tra nguồn lỗi. Không giấu lỗi nguồn bằng truy vấn khác ở gateway.
- Kết quả thiếu/không hợp lệ vẫn dùng thông báo bảo vệ trung thực. Một lớp bảo vệ
  đầu ra thận trọng chặn tuyên bố độc quyền/toàn hệ thống và giá tiền không có
  trong báo cáo; đây KHÔNG phải chứng minh ngữ nghĩa mọi câu AI đều chính xác.

## Một nguồn lịch sử
- dialogue_v2 lưu đúng câu đã trả thành công, kể cả FAQ/shortcut/thông báo bảo vệ,
  cộng snapshot thẻ thực sự hiển thị để hiểu thứ tự và tham chiếu sản phẩm.
- Chỉ replay user/assistant và snapshot, không replay reasoning/câu native bị thay.
  Snapshot gắn nhãn dữ liệu lịch sử, không phải giá/tồn mới hay lựa chọn đã chốt.
- Responses dùng conversation_history rõ ràng, store=false, scope thực thi riêng
  từng lượt; không trộn previous_response_id với lịch sử hiển thị. Không phục hồi
  ngầm câu trả lời ẩn từ chuỗi native. cid cũ chỉ còn thông tin tương thích.
- SQLite riêng gateway, TTL logic30 phút, tối đa64 lịch sử,8 cặp/lịch sử,64KB UTF-8;
  bỏ cặp cũ nguyên vẹn. Dọn bản ghi hết hạn khi ghi lượt mới. Logout xóa lịch sử.
  Giới hạn file SQLite tăng từ1024 lên4096 page để chứa lịch sử hữu hạn.
- Không bật memory dùng chung/tự học từ khách. Không thay cấu hình lưu session/log
  nội bộ Hermes; store=false không đồng nghĩa tắt mọi log của Hermes.

## Đánh đổi và nghiệm thu
- Tìm theo tiêu chí/nối tiếp trước đây có thể đi đường regex miễn phí; giờ dùng
  AI và có thể tiêu quota sớm hơn. Hạn mức/concurrency/cờ phê duyệt không tăng.
- Vượt64 lịch sử có thể mất ngữ cảnh cũ; Hermes phải hỏi lại khi không đủ thông tin.
  Bài100 request FAQ không chứng minh100 lượt AI chạy đồng thời.
- Test fake provider kiểm chứng wiring/safety, KHÔNG chứng minh hiểu tiếng Việt.
  Workspace không có endpoint/key và phê duyệt model thử nghiệm. Không chạy trả phí,
  không gọi stock production và không deploy. Cần nghiệm thu trên bản thử đã duyệt.
- Đã thêm3 ca đa lượt có rubric vào acceptance.json. evaluate_live.py mặc định
  NOT_RUN; chỉ dùng --live trong môi trường thử đã cấu hình secret và phê duyệt.
  Đọc câu trả lời thật trước khi merge/deploy, không lấy số test pass thay cho đó.

Nguồn giao thức: tài liệu Hermes API Server chính thức và source pinned848fc0a.
Không đổi pin hoặc cài OpenAI Agents SDK/LangGraph/DSPy. Helper cũ vẫn nằm trong
Git để đối chiếu nhưng không được import ở đường chat hoặc đóng gói vào hai image.

Lưu ý nâng cấp: lịch sử v2 bắt đầu từ bản này, không nhập chuỗi native cũ có thể
chứa lời chưa hiển thị. Khi nghiệm thu hãy reload khung chat để bắt đầu rõ ràng.
Hiểu phủ định, chọn size từ số đo và phân biệt đề xuất/xác nhận phải được thử với
model thật; không còn dùng bộ regex slot cũ làm bằng chứng đã hiểu đúng ngữ nghĩa.
Bài local load và kết quả433 test xem performance/hermes-dialogue-verification.json.
