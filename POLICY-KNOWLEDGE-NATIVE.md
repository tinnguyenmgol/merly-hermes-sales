# Chính sách từ kiến thức, không từ danh sách câu mẫu

Loại bảng câu hỏi FAQ/hàm policy khỏi fast_replies.py. Gateway không import và
hai image không đóng gói helper đó. Câu chính sách đi nguyên văn vào Hermes,
không thêm alias ko/k/không hay router đoán topic từ chuỗi.

policy_knowledge.py dùng chung cho get_policy và context agent: dữ kiện đã duyệt,
scope customer_only, nguồn/ngày theo từng chủ đề; không phải cặp Q/A. Hợp nhất
phần khách hàng từ01_MERLY_CHINH_SACH_BAN_HANG.md và07_MERLY_FAQ.md v1.1:
- Địa chỉ876 Trường Sa/561 Lũy Bán Bích,09:30–21:30, freeship300k sau giảm.
- Đổi30 ngày/thông thường01 lần, phí/voucher/điều kiện; bảo hành365; khách mới.
- Member+/Silver+/Gold+/Diamond+/Platinum+ và các mục FAQ khách hàng đã duyệt.
Giữ approved=false của bản nháp cũ, sizing duyệt riêng không đổi. Không nạp MD
nhân viên/lương/giá vốn. Không tự thêm voucher, hạng thực tế, cộng dồn hay quận/phường.
Nguồn/ngày sai hoặc xung đột cùng ngày =>cần xác minh, không chọn bừa.

## Luồng và trace
Gateway gửi câu gốc + lịch sử hiển thị + context chính sách khoảng8KB/giới hạn32KB.
Hermes tự diễn đạt từ dữ kiện đủ hoặc gọi get_policy. Không thêm classifier hay
model viết lại, không tự học từ khách. Chỉ shortcut tra mã/size tồn hoàn chỉnh còn
riêng. Không thay model/provider/pin/toolset/quyền công cụ.
Phản hồi có diagnostic_id, knowledge_revision, approved_policy_topics. Log
MERLY_CHAT_COMPLETED ở INFO chứa route/tools/topics/hash/thời gian, không chứa
câu khách/nội dung tool/key. Bật logger INFO nếu cần xem log thành công; metadata
JSON có sẵn để đối chiếu. Guard dữ liệu không chứng minh ngữ nghĩa mọi câu AI đúng.

## Xác minh
502 test pass:dữ kiện/nguồn, loại nội bộ, routing nhiều cách viết, budget/lịch sử,
trace không lộ dữ liệu và hồi quy. verify_policy_transport.py chạy AIAgent Hermes
pinned thật với HTTP stub local, xác nhận câu nguyên văn và context tới provider.
ACK được script cố định, KHÔNG là model suy luận hoặc bằng chứng hiểu tiếng Việt.
Chromium public/iframe/ảnh:pass. Tải100 request stock mô phỏng xác minh backpressure
200/429; KHÔNG phải100 lượt AI hay100 câu chính sách trả lời thành công.

Workspace không có endpoint/key test/cờ duyệt chi phí. Chưa chạy semantic test
model thật, không suy đoán nguyên nhân greeting ngoài lỗi nguồn/routing đã biết.
acceptance.json thêm policy-natural-questions/policy-rules-followup; evaluate_live.py
mặc định NOT_RUN, chỉ dùng --live trong môi trường thử đã duyệt và xem đáp án thật.
Không gọi stock production/deploy. Không kết luận bot hết lỗi từ số test pass.

## Chi phí
Câu chính sách giờ tiêu quota agent thay vì shortcut miễn phí. Giữ hạn mức và
concurrency, không tự tăng ngân sách. AI hết quota thì chính sách cũng bị giới hạn;
UI không hứa FAQ miễn phí nữa. Kiến thức sẵn giúp không bắt buộc vòng tool cho câu
thông tin chung. Không cam kết latency/chi phí trước khi đo model thật.
