# Rà soát và thiết kế lại — LAB, KHÔNG DEPLOY

## Phát hiện đã tái hiện bằng mã nguồn
1. Model phải chép stock_request_id kỹ thuật. Một lần tra có đủ 20 biến thể
nhưng ID model chép lệch ID gateway thì toàn bộ kết quả bị loại.
2. Cùng mẫu/size: lần trước có dữ liệu đúng, retry thất bại thì bộ gom lấy lần
cuối và làm mất kết quả đã xác minh trước đó.
3. Lỗi tham số và nhiều lỗi đầu ra đều trở thành stock report unverified/rỗng.
Không bịa tồn nhưng không phân biệt được lỗi thao tác với dữ liệu kho chưa đủ.
Đây là các điểm yếu đã tái hiện, KHÔNG khẳng định là nguyên nhân duy nhất của
lượt chat trong ảnh: log không chứa đủ đầu vào/đầu ra thực tế để kết luận đó.

## Thiết kế thay thế
- LLM chỉ hiểu ý định và xác nhận phạm vi mẫu/size/màu. Không quyết định tồn,
  không tự chọn vài màu đại diện toàn mẫu, không chép provenance kỹ thuật.
- Ứng dụng kiểm tra kiểu dữ liệu, tạo metadata nội bộ, đọc nguồn GET-only,
  kiểm tra hợp đồng, gom bằng chứng theo phạm vi/thời điểm và quản lý deadline.
- Lỗi đầu vào/nguồn/hợp đồng khác trạng thái dữ liệu thiếu/đủ. Không dựng bảng
  tồn rỗng thay lỗi. Retry lỗi không xóa bằng chứng cũ, nhưng dữ liệu cũ phải
  ghi rõ thời điểm và KHÔNG được gọi là lần xác minh mới.
- Không ép kiểu, đoán mã/giá/tồn hoặc đổi provider/model tự động.

## Artifact và bằng chứng
engine.py là nguyên mẫu điều phối độc lập, không nối gateway/Docker/MCP runtime.
execute() sinh metadata ở server, dùng lại stock reader/validator để cô lập thay
đổi điều phối. collect() minh họa giữ bằng chứng qua retry, chỉ nhận cặp tool
call/output. Collector lab KHÔNG là production validator: còn cần versioned
validation/auth/replay checks trước tích hợp. Không merge nguyên mẫu để chạy.

153 test cũ vẫn pass, thêm 16 ca lab: tổng 169 pass. Có tái hiện lỗi cũ, nonce
sai, retry, 20 màu với Kem/Chì Bóng sau mục12, nhiều phạm vi, đầu vào sai, tồn
thiếu/0. Chạy qua MCP renderer và native Responses _extract_output_items của
Hermes đang pin; không tự dựng vỏ API rồi gọi đó là end-to-end thật.
Tất cả sản phẩm/tồn/summary trong lab là SYNTHETIC, không gọi inference/Haravan.

## Cổng nghiệm thu trước triển khai
1. Fixture GET-only từ Haravan thật, có timestamp, field types, product/variant
IDs, giá, mọi màu và hàng kho; đối chiếu cùng thời điểm, không chứa token/PII.
2. Model thật đã chọn: hỏi đầu/tiếp, đổi size, mở rộng màu, mã gần giống, nhiều
sản phẩm, dữ liệu thiếu, nguồn chậm, hết credit, timeout. Không bỏ lựa chọn còn.
3. Trạng thái thao tác và coverage rõ ràng; đo số lượt model, độ trễ, chi phí;
không nới budget mù. Tách tác vụ phụ đặt tên khỏi luồng mua hàng.
4. Tích hợp staging riêng + test UI/âm/concurrency; có rollback một commit rõ.

## Giới hạn cần nói thẳng
Workspace không có credential/runtime access để đọc Haravan thật hoặc gọi
OpenRouter của app. Coolify tools chỉ có deployment/build log, không có runtime
trace/raw evidence. Live acceptance CHƯA ĐẠT. Chưa đề nghị merge/deploy, đổi env
hay xin root/SSH VPS/Docker socket. Cần được cấp một đường xuất GET-only và trace
đã che nhạy cảm; không gửi key Telegram, không dùng log rỗng làm fixture.

## Tham chiếu đã đọc
https://hermes-agent.nousresearch.com/docs/integrations/providers
Hermes pin 848fc0ad8be766b9dc10fe42bd80b5fc2d45d95c: api_server_openai_routes.py,
mcp_tool_handlers.py, title_generator.py. Non-stream API giữ tool outputs; trim
1000 ký tự thuộc terminal SSE nên KHÔNG kết luận đây là lỗi gateway non-stream.
Native source có auxiliary.title_generation.enabled; chưa thay cấu hình chạy.
