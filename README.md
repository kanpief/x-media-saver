# 🚀 X Media Pro Saver (Twitter Media Downloader)

Phần mềm tải **Ảnh gốc (:orig)** và **Video Full HD / 4K (Bitrate cao nhất)** từ nền tảng **X (Twitter)** với giao diện Glassmorphism Dark Mode hiện đại, trực quan, tốc độ xử lý tức thì.

---

## ✨ Tính Năng Nổi Bật

1. **Chất Lượng Tối Đa (Max Quality)**:
   - **Ảnh**: Tự động chuyển đổi và trích xuất độ phân giải gốc cao nhất (`:orig` / `format=jpg&name=orig`) – không bị nén như khi lưu thủ công.
   - **Video / GIF**: Tự động chọn chất lượng tốt nhất (1080p, 60fps, bitrate cao nhất) hoặc tùy chọn các mức phân giải khác nhau.
   - **Multi-photos**: Hỗ trợ bài viết chứa nhiều ảnh (1, 2, 3, 4+ ảnh), tải trọn bộ chỉ với 1 click.

2. **Giao Diện Hiện Đại & Sang Trọng**:
   - Phong cách **Glassmorphism Dark Mode** mượt mà, hiệu ứng ánh sáng Neon Cyberpunk.
   - Hỗ trợ **Xem trước (Live Preview)** trước khi tải: hiển thị Avatar tác giả, nội dung Tweet, thẻ phân loại, và trình phát video trực tiếp.
   - **Xem chi tiết ảnh (Lightbox Preview)** phóng to toàn màn hình sắc nét.

3. **Hai Chế Độ Tải Linh Hoạt**:
   - 📥 **Lưu vào máy tính**: Tải hàng loạt vào thư mục `downloads/` trên máy và mở trực tiếp qua Windows Explorer bằng 1 nút bấm.
   - 🌐 **Tải qua trình duyệt**: Tải trực tiếp thông qua trình quản lý tải xuống của Chrome / Edge / Firefox.

4. **Quản Lý Lịch Sử**:
   - Lưu lại danh sách các tệp đã tải gần nhất để tiện tra cứu lại.

---

## 🛠️ Hướng Dẫn Cài Đặt & Sử Dụng

### Cách 1: Chạy Nhanh Bằng 1-Click (Khuyên Dùng)
Chỉ cần nhấp đúp chuột vào tệp:
```text
run.bat
```
*(Chương trình sẽ tự động kiểm tra thư viện và mở trình duyệt tại `http://127.0.0.1:5000`)*

---

### Cách 2: Chạy Bằng Dòng Lệnh (Terminal / PowerShell)

1. Cài đặt các thư viện cần thiết:
   ```bash
   python -m pip install -r requirements.txt
   ```

2. Khởi chạy máy chủ:
   ```bash
   python app.py
   ```

3. Mở trình duyệt và truy cập:
   ```text
   http://127.0.0.1:5000
   ```

---

## 📁 Cấu Trúc Dự Án

```text
SGX/
├── app.py                  # Server Flask & các API trích xuất, tải file
├── downloader.py           # Module trích xuất đa kênh (Syndication, vxTwitter, yt-dlp)
├── requirements.txt        # Danh sách thư viện Python cần thiết
├── run.bat                 # Script chạy nhanh 1-click trên Windows
├── downloads/              # Thư mục tự động lưu ảnh và video tải về
├── templates/
│   └── index.html          # Giao diện chính người dùng (HTML5 chuẩn SEO)
└── static/
    ├── css/
    │   └── style.css       # Giao diện Glassmorphism Dark Mode
    └── js/
        └── main.js         # Xử lý logic tải, preview và tương tác
```
