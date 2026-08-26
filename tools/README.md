# Cấu trúc đóng gói tool

Mỗi tool trong dự án đặt trong một thư mục riêng dưới `tools/`.

Mỗi thư mục tool có 2 phần chính:

1. `frontend/`
   - Giao diện riêng của tool.
   - HTML/JS/CSS hoặc ghi chú vị trí giao diện nếu tool đang dùng chung shell.

2. `core/`
   - Lõi hoạt động bên trong tool.
   - API, service, automation, xử lý dữ liệu, selector, luồng chạy nền.

Quy ước:

- Không trộn logic của tool mới vào file tool khác.
- Tool mới phải có `tool.json` để ghi rõ tên, route, file giao diện và file lõi.
- Nếu tool đang dùng chung dashboard chính, `frontend/README.md` phải chỉ rõ hàm giao diện nằm ở đâu.
- Nếu tool dùng lõi chung, `core/README.md` phải chỉ rõ các service/API đang phụ trách.
