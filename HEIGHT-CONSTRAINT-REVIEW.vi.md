# Bảo toàn chiều cao: hợp đồng model và kiểm chứng thẻ

## Phạm vi bản sửa
- Không định tuyến lời khách bằng regex, không đổi framework, không tăng quyền
  công cụ. Vẫn đúng năm công cụ đọc; không tạo đơn/giữ hàng/sửa nguồn.
- Schema model buộc khai báo heel_mode=exact hoặc unspecified. exact đi cùng
  heel_cm; unspecified không có heel_cm. Backend từ chối khai báo mâu thuẫn
  trước khi đọc nguồn. Không dùng nullable có thể bị provider loại bỏ.
- Audit kiểm tra schema THẬT sau chuyển đổi bằng SDK Hermes đã pin. Schema cũ
  thiếu khai báo chiều cao phải bị startup audit từ chối.
- Lời gọi legacy không có heel_mode vẫn được backend chấp nhận để tương thích;
  điều này không biến legacy thành bằng chứng đã giữ đủ điều kiện khách.
- Parser số đo nguồn được dùng chung, không thay logic suy luận thuộc tính.
  Khi dùng trên lời AI, nó chỉ lấy MỆNH ĐỀ cần kiểm chứng, không tạo bằng chứng.
- Nếu lời AI khẳng định một chiều cao rõ ràng nhưng thẻ tồn dương khác chiều
  cao hoặc chưa xác minh thông số: chặn toàn bộ thẻ/link sản phẩm của câu trả
  lời lỗi. Dùng tối đa một lần sửa đã có, cùng input và lịch sử đã giao khách.
  Không bỏ bộ lọc rồi âm thầm đưa mẫu khác; không yêu cầu nhập lại dữ kiện cũ.
- Quote gửi thêm duy nhất chiều cao số có nguồn, không lộ trường enrichment
  khác. Thông số tiêu đề mâu thuẫn metadata không được coi là đã xác minh.
- Metadata guard unsupported_spec_claim đi vào collector hiện có, được đề xuất
  constraint_preservation thay vì native_guidance; vẫn draft/hypothesis, không
  tự duyệt/xuất/apply. Đánh dấu thủ công chỉ bằng diagnostic_id chưa tự cung cấp
  nguyên nhân: không được đoán nguyên nhân chỉ từ mã đó.

## Kiểm chứng thật, không phải điểm chất lượng AI
- Chạy lại test thẻ trộn chiều cao với agent_answer.py từ main trước sửa:
  thất bại; trả lời nói gót 7cm nhưng chưa có guard phát hiện tập thẻ rộng.
- Với code mới, các ca nguồn giả lập 5/7/10, không chọn chiều cao, quote có
  metadata riêng, thiếu/mâu thuẫn thông số và câu hỏi không dữ liệu đều đạt.
- Pipeline client thật nhận nguyên văn yêu cầu đổi 5 -> 7 và giữ lịch sử đã giao;
  công cụ trả đúng tập 7 trong kịch bản model có lời gọi đúng. Test khác kiểm
  tra tối đa một lần sửa khi lần đầu truy vấn rộng nhưng tuyên bố 7cm.
- 883 kiểm thử tests/ đạt; 43 kiểm thử qa-service/tests đạt (ba cảnh báo
  deprecation thư viện, không phải lỗi). Kiểm tra đóng gói hiện có chạy trong
  bộ tests/. Không Docker build hoặc gọi model/Haravan thật trong đợt này.

## Giới hạn và nghiệm thu live
Không tuyên bố model đã fine-tune hoặc luôn hiểu đúng mọi cách diễn đạt. Nó vẫn
phải khai báo đúng ý định. Guard hiện đối chiếu mệnh đề một chiều cao rõ ràng;
không coi câu nhiều chiều cao/đơn vị mơ hồ là một chiều cao đã được chọn. QA live
cần kiểm cả trả lời không nhắc chiều cao, so sánh nhiều mẫu, phân/cm, đổi tiêu
chí và câu chân dài; unit test kịch bản không chứng minh năng lực NLP.

## Rollout do chủ hệ thống thực hiện
Review/merge nhánh riêng rồi redeploy cả hermes-sales, sales-gateway và
learning-review, vì schema, parser, guard và enum collector cần đồng bộ. Giữ
nguyên Compose Location, volume và secret hiện có; không cần token mới. Không
push main hay triển khai production từ Workspace. Sau deploy mới chạy QA live
và đọc report/case từ service thật; không đánh dấu live acceptance chỉ vì test
offline đã đạt. Bản nháp ca cũ không tự đổi thành approved hoặc verified.
