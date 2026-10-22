# Tìm tên/loại/nhóm + ảnh nhỏ

## Tìm kiếm
Giữ Hermes điều phối. query tìm từ khóa trong title/product_type; category có
bằng chứng từ tên/loại hoặc metadata đã duyệt. Trả product_type, match_evidence
và tối đa30 loại nguồn, không dùng từ điển câu hỏi/đáp án. Giữ mọi điều kiện
size/màu/gót/nhóm và mã SKU nguyên gốc, không bỏ tiêu chí khó để có kết quả.

Collection khác product_type: GET custom_collections/smart_collections công bố,
chọn duy nhất rồi GET products với collection_id. Không đoán thành viên từ tên
nhóm hay tự chạy rule smart collection. Tên mơ hồ trả lựa chọn để hỏi lại; thiếu
quyền/API lỗi/paging chưa đủ không được tìm toàn shop thay cho nhóm đã yêu cầu.
Chỉ thêm hai resource GET; không thay token, scope hay quyền ghi.

Cache tên nhóm300 giây; tối đa4 page50/type. Đọc thành viên mới, tối đa3000 sản
phẩm, ngân sách8 giây, timeout từng GET không quá3 giây. Không đầy đủ là chưa xác
minh, không phải hết hàng. Size vắng trong cache không loại ứng viên kiểm tồn;
ưu tiên size thấy trong cache rồi kiểm variants paging mới. Đọc gót rõ trong tên,
không suy từ nhóm/SKU/số đo chân/khoảng. Tên/nhóm không chứng minh êm/vừa/tồn.

## Ảnh
Ảnh72x72 từ output công cụ: danh mục, tra tồn và quote. Bấm mở trang sản phẩm nguồn
khi có; không render HTML/Markdown ảnh AI. Ánh xạ image_id/variant_ids cho ảnh biến
thể; ảnh chung có chú thích chưa xác minh đúng màu. Không dùng ánh xạ xung đột.
Tối đa4 ảnh sản phẩm/một phản hồi, không lặp20/100 ảnh theo biến thể, không cắt
bảng tồn. Lazy-load/no-referrer/kích thước cố định; không cam kết file gốc nhỏ.

CSP chỉ mở bốn host Hstatic cho img, không wildcard/script ngoài. Chặn URL nguy
hiểm/SVG/host giả/credential/port lạ. Ảnh lỗi bị bỏ, không mất tồn hợp lệ hay đứng
chat. Báo cáo nhóm rỗng/chưa xác minh có thông báo thay vì hứa bảng rồi trống.
Lịch sử giữ tên/ID/thẻ nhưng bỏ URL ảnh để giảm bộ nhớ/token.

## Xác minh
478 test pass + ba bài Chromium: verify_catalog_images_browser.py,
verify_public_browser.py, verify_four_issues_browser.py. Có ảnh tải được72px,
mobile/desktop/iframe,popup,no-referrer,ảnh xấu,lỗi tải,giới hạn4,quote,nhóm rỗng.
Preview là render local thật, ảnh giày từ storefront Merly công khai. Provider,
product IDs và giá/tồn trong kiểm thử là MÔ PHỎNG, không xác nhận hàng thực tế.
Không gọi API kho thật/model trả phí. Quyền đọc nhóm và chất lượng model cần
nghiệm thu môi trường thử đã duyệt. Không deploy/merge main. Reload chat sau cập nhật.

Nguồn: https://docs.haravan.com/docs/omni-apis/products/ và custom-collections/,
smart-collections/. Giữ pin Hermes và năm công cụ read-only hiện có.
