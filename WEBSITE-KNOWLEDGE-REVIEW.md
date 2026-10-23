# Rà soát thông tin công khai website Merly

## Phạm vi và cách dùng

- Thời điểm truy xuất UTC và SHA-256 từng HTML nằm trong `vendor/website-source-review.json`.
- Rà 154 URL trong sitemap: 37 trang `/pages/`, 117 bài `/blogs/`; tất cả HTTP 200.
- Sáu trang không có nội dung văn bản trích xuất được: danh sách yêu thích, cửa hàng, kiểm tra đơn hàng, điều khoản dịch vụ, siêu sale 1/1 và giảm giá. Đã kiểm tra HTML bổ sung: hai trang sale là landing catalog có ảnh/sản phẩm, không phải trang chính sách trống; bốn trang còn lại là giao diện động hoặc không có phần văn bản nội dung. Không coi đó là đã đọc nội dung ảnh hoặc kiểm chứng chức năng tra cứu.
- Không crawl tài khoản, giỏ hàng, checkout, quản trị; không gửi form, không dùng token, không thu thập thông tin khách.
- Không chép catalog/giá/tồn từ HTML vào kiến thức tĩnh; vẫn tra Haravan GET-only.
- Chỉ 10 nhóm tham khảo chọn lọc từ 12 nguồn được đưa vào context. Không đưa nguyên 154 trang hoặc blog marketing vào prompt. Đây không phải fine-tune hay tự học.

## Dữ liệu đã bổ sung

Giới thiệu Merly; cách đo chiều dài và vòng bàn chân; hướng dẫn tài khoản/thành viên; cách ghi địa chỉ theo thông báo 01/07/2025; các kênh công khai; chăm sóc giày cơ bản; hướng dẫn thanh toán; liên hệ hỗ trợ đơn; yêu cầu hỗ trợ dữ liệu cá nhân; dịch vụ giày đồng phục doanh nghiệp.

`vendor/knowledge-website-reference.json` có đoạn trích, URL gốc, thời điểm truy xuất và hash HTML. Tất cả mục là `reference_only`, không phải điều khoản thương mại mới. Thời điểm sitemap/crawl KHÔNG dùng để xác định hiệu lực. Chỉ `customer_links` được khuyến nghị bấm; các URL trong `sources` chỉ phục vụ bằng chứng, một số trang chứa phần cũ.

## Xung đột/cần chủ cửa hàng xác nhận hoặc sửa trên Haravan

1. `/pages/chinh-sach-doi-tra`: phí online 35.000đ; loại trừ hàng giảm từ 20%. MD 21/09/2026 đã duyệt: 20.000đ kèm voucher 20.000đ; ngưỡng loại trừ 30%. Giữ MD, không ghi đè.
2. `/pages/cau-hoi-thuong-gap`: freeship trên 250.000đ, đổi 90 ngày, hoàn tiền mọi trường hợp; còn nội dung nhắc JUNO. Không nhập vào bot. MD: freeship từ 300.000đ sau giảm, đổi 30 ngày có điều kiện.
3. `/pages/chinh-sach-giao-nhan`: bảng phí ghi áp dụng từ 01/03/2020, hứa giao 2 giờ; hai trang FAQ đưa thời gian giao khác nhau. Không lấy các bảng này làm cam kết hiện tại.
4. `/pages/chinh-sach-khach-hang-than-thiet` ghi tích 5%, `/pages/lien-he` ghi 2%. Chưa chọn tỷ lệ; giữ quyền lợi từng hạng từ MD và không xác nhận điểm/hạng cá nhân.
5. `/pages/chinh-sach-bao-hanh` có điều khoản loại trừ khuyến mãi rộng, ngưỡng 20%, thiếu thời hạn 365 ngày. Chỉ lấy đoạn chăm sóc không xung đột; không thay chính sách bảo hành đã duyệt.
6. Thanh toán: trang cũ có thông tin tài khoản và liên hệ khác hotline chung, nhắc cửa hàng ngoài hai địa chỉ đã duyệt; VNPAY có mã ưu đãi chưa xác nhận hiệu lực. Không chép tài khoản, QR hoặc mã vào dữ liệu AI. Các phương thức phải kiểm tra ở bước thanh toán chính thức.
7. Email liên hệ không thống nhất giữa trang liên hệ, bảo mật, bài địa chỉ. Trang bảo mật còn link bên thứ ba không liên quan và yêu cầu CMND trong mẫu cũ. Chưa chọn email, không cho bot thu giấy tờ/OTP/mật khẩu; chuyển hỗ trợ qua Zalo OA đã duyệt.
8. Giày đồng phục: bảng giá, chiết khấu, hotline chuyên trách và thời gian sản xuất cần xác nhận trước khi coi là hiện hành. Chỉ thêm mô tả dịch vụ/quy trình tham khảo, không báo giá từ bài cũ.
9. Blog khai trương/khuyến mãi: không chứng minh cửa hàng còn mở, hàng còn tồn, ưu đãi còn hiệu lực. Không nhập thành chính sách. Thông báo địa chỉ 2025 được dùng bổ sung phường cho đúng hai địa chỉ MD, không thêm chi nhánh lịch sử.

## Cập nhật sau này

Sửa nội dung nguồn đã xác nhận trước, cập nhật snapshot chọn lọc cùng bằng chứng và tăng revision. Chạy toàn bộ pytest và kiểm tra đường truyền context/UI. Không tự động crawl vào production; không tự merge/deploy. Giữ nguyên hai file kiến thức cũ ở lượt này.

## Kiểm thử bản source này

- 525 pytest đạt, không có ca bỏ qua (dùng standalone Compose đã có ở Workspace chỉ để render config offline, không kết nối daemon).
- 23 ca mới: provenance, so sánh snapshot, ưu tiên MD, truyền context/link, file thiếu/lỗi/symlink, nguồn sai scope, URL độc hại và giới hạn kích thước.
- Pinned Hermes AIAgent chạy vòng thật tới HTTP model stub cục bộ: kiến thức website đến provider; không gọi model thật, không đánh giá độ hiểu ngữ nghĩa.
- Chromium: 6 link hợp lệ, 8 trường hợp chặn, popup không có opener, XSS không thực thi; hồi quy Enter/IME/widget và ảnh sản phẩm cũng đạt bằng fixture được gắn nhãn. Không coi fixture là tồn/giá thật.
- Không sửa nội dung website Haravan, không thay hai JSON kiến thức gốc, không đổi Compose/pin Hermes, không thêm công cụ hay quyền. Chưa merge main/deploy production.

Các lệnh kiểm thử cốt lõi:
```sh
python -m pytest -q
python verify_policy_transport.py
python verify_website_links_browser.py
python verify_four_issues_browser.py
python verify_catalog_images_browser.py
```
Ở Workspace, dùng venv `hermes-offline-build-validation`; các biến browser path/library/font và standalone Compose là cấu hình môi trường kiểm thử, không phải thay đổi production.
