# Thử DeepSeek qua OpenRouter

Model ID giữ nguyên: `deepseek/deepseek-v4.1-flash-1017`.
Đã tìm thấy đúng ID trong catalog công khai OpenRouter, có `tools` và `tool_choice`.
Catalog chỉ chứng minh khả dụng công khai, không chứng minh tài khoản đang chạy đã gọi được hoặc model hiểu tốt hơn.

## Áp dụng với code production hiện tại

Không cần thay API key hay đợi merge code để chọn model: backend hiện có đã hỗ trợ biến sau.
Trong Environment Variables của resource Hermes sales trên Coolify, đặt:

```env
MERLY_SALES_PROVIDER=openrouter
MERLY_OPENROUTER_MODEL=deepseek/deepseek-v4.1-flash-1017
```

Giữ nguyên secret `OPENROUTER_API_KEY` ở backend. Không gửi key lên chat/Git hoặc thêm key vào gateway. Nếu đã đặt `HERMES_SALES_MODEL_ALIAS`, kiểm tra/bỏ override cũ để tránh request vẫn chọn model khác. Lưu cấu hình và redeploy resource theo quyền của chủ cửa hàng. Không xóa volume, DB hoặc tài liệu.

Nhánh này cũng đổi default trong Compose và migration thành model mới, đồng bộ test và verifier. Giá trị `MERLY_OPENROUTER_MODEL` đã đặt trên Coolify luôn ưu tiên hơn default trong code: merge không ghi đè biến cũ tự động.

## Nghiệm thu sau khi áp dụng

Mở phiên chat mới, thử chuyển chủ đề từ hỏi ngày sang cách mua và tìm giày 3cm size 42. Cần kiểm tra model thực tế cùng tool calls; không được trả câu chào thay việc tìm mẫu, không bịa tồn. Đổi model không tự sửa vấn đề đồng hồ, logging hoặc tích hợp hội thoại đang điều tra.

Các kiểm thử offline xác nhận config/migration/provider resolution và hồi quy, không phải chất lượng model thật. Workspace không được deploy production và không chạy paid inference ở lượt chuẩn bị này.

## Quay lại model cũ nếu cần

Đặt `MERLY_OPENROUTER_MODEL=openai/gpt-oss-20b`, lưu và redeploy theo quyền operator. Không đổi provider, key hay xóa dữ liệu.
