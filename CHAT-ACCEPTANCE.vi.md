# Nghiệm thu chatbot Merly: tìm hàng và hội thoại

## Cách chấm
Tách an toàn, hoàn thành nhu cầu và tốc độ. HTTP 200/không có thẻ sai KHÔNG
đồng nghĩa tìm hàng thành công. Chưa xác minh/scan chưa hết: blocked hoặc
inconclusive, không pass thành hết hàng. Một câu đúng không chứng minh lỗi
hết tái diễn. Đáp án lấy từ nguồn mới/chính sách duyệt, không từ lời bot.

## Ca live bắt buộc
A. Chưa cho size: hỏi một lần, không tra tồn/đoán size.
B. Đen/42/5cm: đúng tiêu chí, tối đa 4 SKU tồn dương, chiều cao có nguồn.
C. Đổi 5 -> 7, giữ màu/size: dùng 7/đen/42, không hỏi lại size, không kèm 5/10.
D. Bỏ chiều cao: unspecified, giữ màu/size. Thiếu tham số API khác khách chưa
   cung cấp: ưu tiên dữ kiện hiện tại/lịch sử; không tự điền hay đoán.
E. Đổi riêng size/màu: mới ghi đè cũ, giữ thuộc tính khác theo ý khách. Không
   lấy thẻ cũ làm lựa chọn hiện tại khi khách đang đổi hoặc chưa xác nhận.
F. Phiên mới chưa chọn chiều cao: không mặc định cm hoặc lẫn phiên khác.
G. Tra 1537/đen/42: giá/tồn mới, hoặc nói rõ nguồn chưa đủ; không giữ/tạo đơn.
H. Spec thiếu/mâu thuẫn: không đoán từ ảnh hoặc collection. Tên nhóm không
   chứng minh thuộc tính mọi SKU.
I. Từ xem mẫu sang ưu đãi: tính có điều kiện theo nguồn/giá giả định; không
   tự xác nhận ưu đãi cá nhân đã áp dụng hay cộng dồn.
J. Lỗi source/JSON/validation: không thành hết hàng, không mất kết quả hợp lệ
   vì một lỗi tham số đã sửa cùng lượt. Không sửa JSON cắt bằng regex hoặc
   nhận error payload thành chứng cứ stock/policy.

## Tốc độ và rollout
Mục tiêu nghiệm thu, CHƯA là SLA đạt: mã riêng <=10s, discovery thường <=15s.
Ghi từng lượt/phân bố; không lấy một mẫu tuyên bố p95. Thiếu nguồn/ngân sách
phải dừng đúng trạng thái, không tăng timeout để che lỗi. Lỗi chọn nhầm thuộc
 tính/an toàn chặn rollout. Chạy biến thể không dẫn đáp án, lặp tối thiểu ba
lần độc lập cho ca trọng điểm trong quota/chi phí duyệt. Chủ duyệt production.

## Nhánh này đã chứng minh gì
- SDK nhận đủ history, chưa có chứng cứ API làm rơi size.
- Error kèm full schema dài bị SDK cắt giữa JSON, mất typed status (reproduce
  SDK thật). Wire feedback <=1500 ký tự, không gửi lại schema đã công bố.
  StdIO/MCP thực giữ lỗi typed. Parser vẫn từ chối JSON hỏng/provenance sai.
- Feedback thiếu size yêu cầu phục hồi dữ kiện đã xác nhận trước; hỏi chỉ khi
  thật sự thiếu/xung đột. Đây không phải bằng chứng model đã hết quên size.
- Hint inventory_quantity chỉ đổi thứ tự trong cùng hạng khớp biến thể. Không
  loại zero/unknown, vẫn giữ diversity collection. Mọi thẻ phải đọc nguồn mới.
  Synthetic SKU vị trí 31 được kiểm sớm, giữ cửa sổ 24. Cache dương/live-zero
  không được coi là còn hàng. Không tăng phạm vi/quyền/timeout.
- Giữ câu hỏi về kiểm tra tương lai, chặn khẳng định tồn/giá không nguồn. Không
  định tuyến câu khách bằng regex; model vẫn dùng ngôn ngữ tự nhiên.

## Còn lại
Chưa Docker build/QA live bản này; chưa chốt có mẫu 7cm thực, hết quên size
hoặc đạt thời gian. Review/merge và redeploy hermes-sales + sales-gateway;
giữ Compose/volume/secret. Không cần key/quyền mới, không sửa DB/Coolify, không
bật Cron. Learning-review không đổi schema. Giữ ca live pending tới có chứng cứ.

Kiểm thử bàn giao: 934 tests ứng dụng + 43 tests qa-service đạt; ba warning deprecation thư viện. Offline, không gọi model/Haravan thật.
