# Core - Tool Zalo

Lõi hoạt động của tool gồm các phần sau:

- API:
  - `app/api/excel.py`: nhận Excel hoặc link Google Drive.
  - `app/api/jobs.py`: tạo phiên gửi, nhận ảnh đính kèm, xuất kết quả.
  - `app/api/zalo.py`: mở Zalo và kiểm tra trạng thái đăng nhập.

- Service:
  - `app/services/excel_service.py`: đọc toàn bộ số điện thoại trong file Excel, lọc hợp lệ/trùng/lỗi.
  - `app/services/job_service.py`: quản lý phiên gửi và trạng thái từng số.
  - `app/services/messaging_service.py`: khóa automation và gửi từng số.

- Automation:
  - `app/automation/zalo_client.py`: thao tác Zalo Web.
  - `app/automation/selectors.py`: selector nút, ô nhập, trạng thái Zalo.

Luồng chính:

1. Đọc Excel/link Drive.
2. Chọn số hợp lệ.
3. Tạo phiên gửi với tin nhắn và ảnh.
4. Kiểm tra đăng nhập Zalo.
5. Bấm Thêm bạn.
6. Nhập số điện thoại.
7. Bấm Tìm kiếm.
8. Nếu có Zalo thì bấm Nhắn tin.
9. Gửi ảnh và tin nhắn.
10. Quay lại số tiếp theo.
