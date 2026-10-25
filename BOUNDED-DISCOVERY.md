# Tìm tồn qua nhiều ứng viên, không chốt ở bốn mẫu đầu

- Tách giới hạn tra nội bộ khỏi giới hạn hiển thị. Mỗi lượt lookup có thể xét tối đa 24 sản phẩm và chọn tối đa 40 biến thể để tra; khách vẫn chỉ nhận tối đa 4 SKU dương đã xác minh.
- Ưu tiên ứng viên có đúng size + màu trong cùng biến thể của cache, xét cả biến thể sau vị trí 12. Đây chỉ là gợi ý sắp xếp, không dùng làm chứng cứ tồn và không loại hẳn sản phẩm có cache cũ.
- Đọc lại sản phẩm/biến thể và kiểm tra kho xen kẽ theo từng sản phẩm. Bốn mẫu đầu không có tồn thì tiếp tục xét ứng viên kế tiếp trong ngân sách. Không lấy mẫu gần màu hoặc đổi size để làm đủ danh sách.
- Dừng khi đạt số SKU dương cần thiết (tối đa 4), hết ứng viên, chạm giới hạn sản phẩm/biến thể hoặc thời gian. Không cố tra toàn website mỗi tin nhắn.
- Ngân sách lookup 15 giây được truyền bằng ContextVar tới các GET Haravan; request mới không khởi động khi hết ngân sách và timeout bị chặn bởi thời gian còn lại. Context được reset kể cả lỗi/nested call, không rò qua worker tái sử dụng. Socket timeout không phải một cam kết tuyệt đối về mọi chậm trễ mạng/OS.
- Gặp 401/403/429 thì dừng tra tiếp cùng nguồn, không retry hàng loạt. Dữ liệu dương đã xác minh trước đó vẫn giữ.
- Coverage ghi đủ sản phẩm/biến thể chưa xét. Scan metadata được kiểm tra theo số sản phẩm/biến thể/dương thực tế. Với collection, proof chỉ liệt kê các thành viên thực sự đã xét.
- Không có kết quả nhưng còn phạm vi chưa xét là partial_no_match, không phải no_match/verified_zero toàn phạm vi. Hết ngân sách không đồng nghĩa hết hàng.
- Tuổi cache được cộng thời gian scan; giữ dữ liệu dương riêng lẻ nhưng không tự nâng thành tra đủ khi cache đã quá ngưỡng.
- Tên sản phẩm lấy từ parent đã xác minh, không lặp tên SEO trong từng dòng biến thể ở payload thô; validator ghép lại cho UI/lịch sử.

## Hợp đồng số

Validator nhận JSON number ở dạng số nguyên hoặc thập phân cho số đo, vẫn từ chối chuỗi/bool/NaN/Infinity và ngoài phạm vi. Dispatcher không còn cần ép riêng int sang float. ID/size vẫn theo kiểu integer đã khai báo, không sửa ID hay chuỗi sai định dạng. Đây là đồng bộ đường gọi trực tiếp và MCP, không phải kết luận rằng số nguyên là nguyên nhân lỗi chat cũ.

## Kiểm chứng

Nguồn Haravan trong kiểm thử là fixture, không phải tồn thật. Ca mới bao gồm: mẫu thứ 5–8 có tồn sau bốn mẫu 0; mẫu cache khác màu nhưng dữ liệu mới đổi màu; biến thể sau vị trí 12; limit hiển thị 1 không cắt quá trình tìm; cap 24/40; hết thời gian; 401/403/429; metadata bị sửa; collection và Responses serialization. Chưa đánh giá ngữ nghĩa GLM hoặc kho production trong Workspace. Không đổi model, secret, quyền tool hoặc schema DB.
