# Frontend - Tool Zalo

Tool này hiện đang chạy trong dashboard chung.

Các phần giao diện chính nằm tại:

- `frontend/app.js`
  - `renderZaloPage()`: bố cục trang gửi Zalo.
  - `bindZaloEvents()`: gắn sự kiện nút bấm.
  - `uploadExcel()`: tải và xem trước danh sách số.
  - `startJob()`: tạo phiên gửi hàng loạt.
  - `renderBulkImages()`: hiển thị ảnh đã chọn.

- `frontend/style.css`
  - `.zalo-command-bar`: banner tool.
  - `.recipients-panel`: khung danh sách người nhận.
  - `.send-panel`: khung nội dung gửi.
  - `.image-import-box`: khung chọn/kéo thả ảnh.

Khi tách mạnh hơn, chuyển các phần trên vào thư mục này.
