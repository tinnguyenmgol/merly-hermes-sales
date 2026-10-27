# Tập sản phẩm và SKU — phạm vi bản sửa

- Không thêm parser câu khách, câu trả lời mẫu hay framework. Hermes tiếp tục
  hiểu hội thoại và gọi search_products với điều kiện cấu trúc đã xác nhận.
- Sửa điểm dừng discovery: mục tiêu là số sản phẩm có tồn dương, không phải số
  SKU của sản phẩm đầu tiên. Giữ nguyên giới hạn sản phẩm/biến thể/thời gian;
  chạm giới hạn thì vẫn là phạm vi chưa kiểm tra đủ, không phải toàn shop hết.
- Projection ưu tiên một SKU hợp lệ của mỗi sản phẩm trước, rồi mới điền các
  biến thể khác nếu còn chỗ. Vẫn tối đa bốn SKU; không sửa báo cáo nguồn gốc.
- selection phân biệt none_verified/single_product/multiple_products trong tập
  đã xác minh, không mang nghĩa chỉ có từng đó sản phẩm trên toàn hệ thống.
- Không bỏ size/màu/gót/kiểu/dịp dùng để kiếm kết quả. Giá trị không khớp vẫn bị
  loại. Dữ liệu thuộc tính thiếu có unverified_criteria riêng; một sản phẩm đã
  sai tiêu chí khác không bị đếm nhầm là ứng viên chỉ còn thiếu metadata.
- Khi query có điều kiện ngoài size/màu, quote chỉ được dùng nếu cặp product_id/
  variant_id nằm trong tập biến thể đã qua truy vấn. Quote cùng size/màu nhưng
  khác mẫu/gót/kiểu không được chen vào. Sửa nội bộ cũng giữ rào này.
- Nếu không có lựa chọn đủ điều kiện, giữ giải thích từ báo cáo đã kiểm chứng
  về metadata, lỗi nguồn, phạm vi chưa đủ hoặc tồn 0; không thay bằng một câu
  chung làm mất nguyên nhân. Không đưa thẻ hàng chưa kiểm chứng ra giao diện.
- MERLY_CHAT_COMPLETED có lookup_diagnostics: trạng thái, tên trường cần tra/
  chưa xác minh và số lượng mẫu/SKU. Không log lời khách, giá trị query, tên
  sản phẩm, SKU, URL hoặc credential. Dữ liệu log hữu hạn và mã trạng thái cố định.

## Kiểm thử

```sh
python -m pytest -q
python verify_product_sets_mcp.py
```

Bài MCP chạy server MCP thật, serializer Responses pinned và adapter thật với
nguồn Haravan giả lập. Bao gồm một mẫu, nhiều mẫu, nhiều SKU cùng mẫu, metadata
thiếu, tồn 0 và loại quote ngoài phạm vi. Không gọi kho/model production; không
coi kết quả này là điểm hiểu ngôn ngữ của model thật.

Đã tái hiện hai lỗi trước khi sửa: dừng sau nhiều SKU cùng một mẫu và mất giải
thích metadata ở projection. Chưa có log chi tiết của lượt 10712cde03ce0d42 nên
không gán lỗi cụ thể của lượt đó cho một nguyên nhân hoặc khẳng định đã chữa nó.

Không thay model, schema tham số công cụ, quyền, quota, budget 8 vòng/40 giây,
secret hoặc dữ liệu kiến thức. Push nhánh không deploy. Owner duyệt merge/main
và nghiệm thu hội thoại thật trước khi coi trợ lý đã bàn giao đạt.
