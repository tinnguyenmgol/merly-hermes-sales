# Chỉ liệt kê SKU có tồn khả dụng dương

- Bằng chứng thô được kiểm tra đầy đủ trước; `customer_listing.project` chỉ tạo bản hiển thị, không sửa báo cáo gốc dùng kiểm chứng.
- Chỉ `known_available` kiểu số nguyên > 0 với ID biến thể/sản phẩm hợp lệ được đưa ra khách. Tồn 0, âm, chưa biết và ứng viên mới có trong catalog đều ẩn.
- Tối đa 4 SKU mỗi lượt, khử trùng giữa tra kho và quote; ưu tiên biến thể đã được quote. Màu/size quote phải khớp phạm vi tra hiện có, không tự coi kem là trắng.
- Phạm vi tra chưa đầy đủ vẫn có thể giới thiệu SKU đã xác minh có tồn; không suy các mẫu khác hết hàng. Thiếu số lượng khách muốn mua không có nghĩa tồn bằng 0; quote vẫn nói rõ chưa đủ số lượng khi cần.
- `view_mode=verified_positive_subset` đánh dấu bảng chỉ là phần hiển thị, không phải dữ liệu đầy đủ. Coverage/complete giữ ý nghĩa của lượt kiểm tra gốc; metadata listing cho biết đã hiển thị bao nhiêu, còn bao nhiêu SKU dương đã xác minh.
- Không có lựa chọn dương thì không vẽ bảng rỗng và không nhồi nhiều thông báo chưa xác minh. Chỉ fallback vận hành được rút gọn; không viết lại lời tư vấn native hợp lệ.
- Ảnh/link của catalog chưa tra tồn không được đưa thành thẻ. Link sản phẩm trong lời model phải có bằng chứng SKU dương; nếu không sẽ vào bước sửa có giới hạn.
- Lịch sử lưu đúng phần đã hiển thị để không tham chiếu SKU ẩn. Frontend cũng lọc dương và giới hạn 4 thẻ để phòng dữ liệu từ phiên bản cũ.
- Đây là quy tắc dữ liệu/hiển thị, không phải router câu hỏi hay bảng đáp án. Không thay API key, provider/model, quyền công cụ hoặc dữ liệu Haravan.

Kiểm tra: pytest, Chromium với nguồn giả lập có nhãn (không phải tồn thực tế). Chưa chạy đánh giá ngữ nghĩa model thật. Workspace không deploy production; cần operator merge nhánh vào main.

Kết quả offline: 579 pytest đạt; Chromium xác nhận ẩn catalog chưa tra, tồn 0/chưa biết và bảng rỗng, chỉ hiện tối đa 4 SKU dương, ảnh/link vẫn hoạt động. Dữ liệu browser là fixture, không phải kết quả kho thật.
