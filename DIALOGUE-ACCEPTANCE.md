# Nghiệm thu luồng làm rõ nhu cầu — response contract v2

## Phạm vi

- Một lượt Hermes gốc vẫn sở hữu hiểu ý, chọn công cụ và viết lời trả lời.
  Không thêm model phân loại, framework, tool hay bộ regex đọc ý khách.
- DIALOGUE-CONTRACT.md được gửi cùng instructions ở mỗi lượt, không phải FAQ
  mẫu. Model tự chọn understood / partial / unclear và tạo question/options.
- Adapter kiểm tra đúng bốn trường JSON cuối. Partial/unclear bắt buộc có câu
  hỏi không rỗng; options là [] hoặc 2–3 chuỗi ngắn. Không tự sửa kiểu dữ liệu,
  bóc JSON từ văn xuôi, hay đoán trạng thái bằng chữ trong tin khách.
- Reply/question thành lời chat; JSON nội bộ không được đưa ra giao diện.
  Cần làm rõ thì không hiển thị thẻ hàng, kể cả công cụ trước đó có trả tồn.
  Khi hiểu đủ, vẫn giữ kiểm chứng tồn dương/đúng scope và tối đa bốn SKU.
- Lỗi nguồn không tự biến thành chưa hiểu. Câu hỏi an toàn vẫn được giữ nếu
  đồng thời có lỗi nguồn; mã lỗi được giữ ở deferred_tool_reasons để tra soát.
  Không dùng một lỗi nguồn làm lý do bắt khách kể lại từ đầu.
- Lỗi định dạng có tối đa một lượt sửa nội bộ trong budget/deadline hiện có.
  Feedback phân biệt lỗi máy và mơ hồ của khách. Sửa vẫn thất bại thì báo lỗi
  xử lý, không lộ JSON/DSML và không nói giả rằng khách nói không rõ.
- Public và /operator có nút lựa chọn bằng textContent; click mới gửi như một
  lời khách nhắn. Không tự chọn, không chạy mã/URL trong nhãn, không gọi tool
  trực tiếp. Vẫn nhập tự do; operator vẫn cần đồng ý thử và qua các cờ sẵn có.
- Lịch sử giữ câu đã hiển thị và nhãn lựa chọn đã gửi, phân biệt gợi ý của bot
  với xác nhận thực của khách. Không tạo memory dùng chung hoặc fine-tune.

## Chạy kiểm tra

```sh
python -m pytest -q
python verify_dialogue_browser.py
python verify_catalog_images_browser.py
python verify_context_api.py
```

Browser cần Playwright/Chromium. Bài HTTP cần dependency Hermes pinned hiện tại.
Các provider trong những bài này là SCRIPTED, không gọi model trả phí hoặc kho
thật. Kiểm tra transport không phải điểm hiểu tiếng Việt. Bộ hội thoại đa lượt
và rubric có sẵn ở eval/dialogue-cases.json; không nạp vào prompt để trả mẫu.

## Nghiệm thu model thật sau khi owner duyệt rollout

1. Dùng đúng model/secret đã cấu hình trên bản thử được duyệt; không gửi key
   qua Telegram hoặc commit key. Reload chat để nhận JS mới.
2. Thử hội thoại mới: nói chưa rõ, chỉ rõ một phần, đủ thông tin, sửa ý/phủ định,
   chuyển sang chính sách rồi quay lại tìm hàng; chọn nút và nhập ngoài menu.
3. Kiểm tra giữ thông tin đã xác nhận; hỏi đúng phần thiếu; không tự đổi tiêu
   chí; đủ thông tin thì hành động, không hỏi mãi để thu đủ mọi sở thích.
4. Nếu thật sự không hiểu thì đề nghị nói rõ hơn. Nếu chỉ nguồn lỗi thì giải
   thích lỗi dữ liệu, không quy thành lỗi diễn đạt của khách.
5. Đối chiếu câu hỏi, lời trả lời, công cụ/scope và mã hỗ trợ. Đánh giá thủ công
   nội dung; trạng thái understood do model khai báo KHÔNG chứng minh hiểu đúng.

Mặc định MERLY_DIALOGUE_CONTRACT_ENABLED=1. Có thể đặt 0 để trở lại plaintext
legacy khi rollback; khi đó không có enforcement v2. Không đổi model, pin,
quota hay secret. Push nhánh tính năng không deploy; main vẫn cần owner duyệt.
