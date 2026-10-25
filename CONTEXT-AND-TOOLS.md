# Hội thoại và hợp đồng công cụ Merly

## Lỗi tái hiện qua HTTP thật

Kiểm tra cũ gọi AIAgent trực tiếp hoặc dựng output JSON nên bỏ sót lớp bảo vệ Hermes. Qua gateway HTTP → Responses HTTP → AIAgent → MCP thật, kết quả tool được bọc trong trust envelope. Bộ đọc cũ cố đọc toàn chuỗi như JSON và loại cả dữ liệu hợp lệ. Đã tái hiện get_policy hợp lệ bị rejected_tool_evidence, rồi xác nhận bản sửa nhận đúng dữ liệu ở chế độ native.

`tool_payload.py` đọc chung chính sách, catalog, ảnh/link, quote và stock. Chỉ nhận JSON và envelope của năm tool Merly, đối chiếu đúng tên tool tại từng call. Không tìm JSON trong văn xuôi hay thực thi DSML/XML. Vẫn kiểm tra ID, phạm vi, tồn, giá và thời điểm. Warning/ranh giới/nguồn/JSON sai đều bị chặn.

## Hội thoại, không router câu mẫu

- Câu khách nguyên văn + lịch sử thực sự đã hiển thị + kiến thức đã duyệt → Hermes tự hiểu.
- Phân biệt xác nhận, điều chưa rõ và đề xuất. Khách đổi ý thì cập nhật, không giữ bộ lọc đã bỏ.
- Hỏi đúng phần thiếu, tối đa hai câu; có thể đưa lựa chọn và cho phép trả lời khác. Không tự chốt cm/size/màu hoặc ép chọn.
- TRUSTED_RUNTIME_CONTEXT_JSON cấp đồng hồ Việt Nam UTC+7 mỗi lượt, không lấy ngày hiện tại từ lời khách.
- Corpus eval 20 tình huống nằm riêng, không nạp vào prompt làm đáp án mẫu.

## Sửa phản hồi có giới hạn

Sau phản hồi hoàn tất nhưng không hợp lệ, Hermes có thể sửa đúng một lần trong cùng lượt. Không retry timeout/network hoặc trạng thái chưa hoàn tất. DSML không thành lệnh và không lọt ra chat.

Lần sửa trừ thêm một lượt chạy Hermes trong hạn mức AI hiện có. Mỗi lượt vẫn có vòng model/tool bên trong: không có nghĩa chỉ hai completion tính phí. Adapter có ngân sách chờ 50 giây, chỉ sửa nếu còn ít nhất 10 giây; timeout lần sửa tối đa 25 giây. Không lặp vô hạn.

Giữ nguyên câu khách và lịch sử đã giao. Không lưu câu lỗi nội bộ thành lời bot. Lần sửa nhận mã kiểm chứng, không nhận câu lỗi làm lịch sử giả. Không có chứng cứ tồn thì không được đưa giá/kết luận tồn. Nếu vẫn lỗi, giữ fallback an toàn; thẻ nguồn hợp lệ từng phần được giữ.

MERLY_AGENT_REPAIR_ENABLED=0 tắt bước sửa; default 1. Chỉ nhận 0/1, sai cấu hình dừng trước model. Không thay model/provider/key hiện tại.

## Chẩn đoán an toàn

INFO MERLY_CHAT_COMPLETED ghi mã chẩn đoán, công cụ dùng, số message lịch sử, guard/recovered reasons, lượt sửa và trạng thái decode/tool cố định. Không ghi câu khách, prompt, output, tham số, token hoặc cookie. Lượt chưa hoàn tất hiển thị mã hỗ trợ. Không bật HTTP debug/log Authorization để điều tra.

## Kiểm thử và giới hạn bằng chứng

Pytest kiểm tra envelope từ pin Hermes, sai nguồn/JSON/truncation, ngày Việt Nam, cô lập lịch sử, protocol, quota/deadline, sửa tối đa một lần và bảo mật log. Chromium kiểm tra Enter/IME, link/ảnh/thẻ và nguồn lỗi từng phần.

verify_context_api.py dùng gateway HTTP, Responses HTTP, AIAgent và MCP thật; model là HTTP stub cục bộ. Chạy 20 ca/43 lượt để kiểm tra truyền lịch sử/cô lập phiên; kiểm tra tool call, DSML và lưu câu sửa đã giao. Đây KHÔNG phải đánh giá ngữ nghĩa GLM. Cần model thật và người chấm rubric, không so câu chữ với đáp án mẫu.

## Nghiệm thu model thật sau deploy

Giữ cấu hình model hiện tại, ví dụ MERLY_OPENROUTER_MODEL=z-ai/glm-5.3-flash. Không cần key mới cho script public webchat.

```sh
python evaluate_dialogue.py
python evaluate_dialogue.py --live --case greeting_to_vague_height --out /data/pilot-gateway/eval-vague.json
```

Mặc định dry-run, không network/model call. Chỉ --live gọi chat thật, có thể tính phí. Chọn file mới ở đường dẫn có quyền ghi: mode 0600, không ghi đè/đưa Git; không lưu cookie/CSRF. Mỗi case là phiên riêng, cách ít nhất 25 giây giữa tin nhắn. Lỗi/quota sẽ dừng và ghi kết quả một phần, không báo đạt giả. Bỏ --case sẽ chạy cả 20 ca/43 câu khách, cần tính hạn mức và thời gian. Transcript luôn UNSCORED đến khi người kiểm tra đánh giá.

Không sửa volume, schema DB, pin Hermes, Haravan, kiến thức hoặc cấu hình model. Workspace chỉ code/test offline, không được push main kích hoạt production. Bước merge/deploy do operator thực hiện theo phê duyệt đã có.

## Kết quả kiểm tra bản sửa

- 564 pytest đạt, không bỏ qua (standalone Compose chỉ render config offline, không dùng daemon).
- Full HTTP harness exit 0: 20 case, 43 câu khách; cô lập lịch sử, gọi MCP, giữ phản hồi đã giao và sửa protocol có giới hạn đều đạt với provider cục bộ.
- Chromium: Enter/IME/widget, nguồn lỗi từng phần, ảnh/link/popup và chống XSS đạt.
- Đường truyền kiến thức qua pinned AIAgent tới HTTP provider stub đạt.
- Model GLM thật: chưa chạy/chấm. Không coi các kết quả fixture là tồn/giá thật hoặc bằng chứng bot đã hiểu ngữ cảnh tốt.
