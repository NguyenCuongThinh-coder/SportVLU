# SportSlot — Flask + SQLite

Website tìm và đặt sân cầu lông, pickleball. Giao diện được dựng từ Jinja templates và CSS hiện có; dữ liệu tài khoản, sân và lịch đặt lưu trong `sportslot.db`.

## Chức năng

- Đăng ký và đăng nhập vai trò người chơi/chủ sân; mật khẩu được hash bằng Werkzeug.
- Cập nhật tên/số điện thoại, đổi mật khẩu bằng mật khẩu hiện tại và yêu cầu đặt lại mật khẩu qua email.
- Tìm kiếm, lọc sân và xem vị trí trên bản đồ Leaflet/OpenStreetMap.
- Người chơi xem giờ còn trống, gửi yêu cầu theo khung một tiếng, xem lịch của mình và hủy đơn chưa bắt đầu.
- Chủ sân chỉ xem đơn và sửa sân thuộc tài khoản của họ; có thể thêm, sửa, xác nhận, từ chối, đánh dấu hoàn thành, ngừng kinh doanh hoặc mở lại sân.
- Trạng thái đơn được phân biệt: `pending`, `confirmed`, `rejected`, `cancelled`, `completed`. Chủ sân chỉ từ chối đơn đang chờ và chỉ hoàn thành đơn đã xác nhận khi giờ chơi kết thúc.
- Email thông báo gửi khi có yêu cầu mới và khi trạng thái đơn thay đổi; liên kết đặt lại mật khẩu có hạn 30 phút và chỉ dùng một lần.
- POST được bảo vệ bằng CSRF token; kiểm tra trùng lịch được tuần tự hóa ở SQLite để tránh hai yêu cầu cùng chiếm một khung giờ.

## Chạy ứng dụng

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export SPORTSLOT_SECRET_KEY="chuoi-bi-mat-ngau-nhien-va-on-dinh"
python app.py
```

Mở `http://127.0.0.1:5000`. Để chạy trong môi trường phát triển có debug, đặt `SPORTSLOT_DEBUG=1` (debug mặc định tắt).

Để bật email, cấu hình `SPORTSLOT_SMTP_HOST`, `SPORTSLOT_SMTP_PORT` (mặc định `587`), `SPORTSLOT_SMTP_FROM`; nếu máy chủ yêu cầu đăng nhập, đặt thêm `SPORTSLOT_SMTP_USER` và `SPORTSLOT_SMTP_PASSWORD`. Với SMTP SSL trực tiếp, đặt `SPORTSLOT_SMTP_SSL=1`; mặc định ứng dụng dùng STARTTLS. Đặt `SPORTSLOT_PUBLIC_URL` thành URL gốc của website để tạo liên kết đặt lại mật khẩu. Không commit thông tin SMTP vào mã nguồn.

Có thể chọn database riêng bằng `SPORTSLOT_DB_PATH`; mặc định ứng dụng dùng `sportslot.db` cạnh `app.py`. Lần khởi tạo database rỗng sẽ thêm 40 sân mẫu (20 cầu lông, 20 pickleball) để demo. Tên, giá và tọa độ sân mẫu không đại diện cho địa điểm đã xác minh.

## Chuẩn bị deploy lên Render

Repository có `render.yaml` để tạo một Render Web Service chạy Gunicorn, một worker và SQLite trên persistent disk tại `/var/data/sportslot.db`. Cấu hình persistent disk yêu cầu compute plan trả phí trên Render. Chỉ tạo service sau khi đã xem và chấp thuận chi phí trong Render Dashboard; không có service nào được tạo tự động khi chỉ thêm file này vào Git.

1. Tạo repository GitHub riêng tư hoặc công khai theo nhu cầu, đẩy source lên nhánh `main` rồi kết nối repository đó với Render bằng Blueprint (`render.yaml`). Không thêm `sportslot.db`, file `.bak`, `.env`, mật khẩu hay khóa SMTP vào Git.
2. Render tạo secret ổn định từ cấu hình Blueprint. Ứng dụng production từ chối khởi động nếu thiếu `SPORTSLOT_SECRET_KEY`, `SPORTSLOT_DB_PATH` hoặc database hiện hữu; cookie phiên tự bật `Secure`. Production không tự tạo 40 sân demo.
3. Database local hiện không được đẩy lên Git. Để nhập dữ liệu hiện tại, đặt tạm `SPORTSLOT_ALLOW_EMPTY_DB=1` trong Environment của service để khởi động lần đầu trên disk rỗng; chưa chia sẻ URL cho người dùng. Sao lưu database local, chuyển file vào `/var/data/sportslot.db` bằng SCP/SFTP theo hướng dẫn trong Render Dashboard, rồi gỡ biến tạm này và khởi động lại. Kiểm tra số users/courts/bookings trước khi mở website. Giữ nguyên database local và các file `.bak` làm bản dự phòng. Nếu muốn một database mới hoàn toàn, chỉ bật biến tạm này khi đã quyết định không cần nhập dữ liệu local.
4. Sau khi chuyển database, kiểm tra đăng nhập, trang chủ, đặt sân và quyền chủ sân trên URL HTTPS của Render. Nếu bật email, bổ sung các biến `SPORTSLOT_SMTP_*` trong Dashboard; SMTP outbound ở các cổng 25/465/587 bị chặn trên free web service của Render.

SQLite trên persistent disk chỉ dùng được với một service instance; Blueprint đặt một Gunicorn worker. Disk giữ dữ liệu qua deploy/restart nhưng mỗi deploy có một khoảng ngừng ngắn. Nếu cần scale nhiều instance, hãy chuyển dữ liệu sang database quản lý như PostgreSQL trước.

Các biến email tùy chọn có trong `.env.example`. Không điền thông tin bí mật vào file mẫu; đặt secret trực tiếp trong Render Environment.

## Kiểm thử

```bash
python -m unittest discover -s tests -v
```

Các bài kiểm thử dùng database tạm, không sửa dữ liệu trong `sportslot.db`.

## Cập nhật website sau khi deploy

```bash
git status
python -m unittest discover -s tests -v
git add <các-file-code-và-cấu-hình>
git commit -m "Mô tả thay đổi"
git push origin main
```

Render tự deploy commit mới trên `main`. Thay đổi code thông thường không cần thao tác lên database. Khi thay schema, cần viết migration tương thích dữ liệu cũ, sao lưu database trước deploy và kiểm tra migration trên bản sao trước; không xóa file SQLite để “reset”. Có thể tạo bản sao SQLite nhất quán trên máy local bằng `sqlite3 sportslot.db ".backup 'sportslot.manual.bak'"`.

## Database và giới hạn hiện tại

- Migration thêm cột `courts.is_active` và bảng token đặt lại mật khẩu theo cách tương thích với dữ liệu cũ. Ứng dụng tạo bản sao riêng trước migration; các bản sao cũ không bị ghi đè.
- Ngừng kinh doanh là thao tác ẩn sân khỏi tìm kiếm; lịch sử đặt vẫn được giữ. Sân có lịch chờ/đã xác nhận phải xử lý trước khi ngừng.
- Khung giờ hiện có độ dài cố định một tiếng. Chưa tích hợp cổng thanh toán hoặc SMS; email yêu cầu SMTP hoạt động. Nếu email không gửi được, thao tác đặt/trạng thái vẫn được lưu nhưng hiện chưa có hàng đợi gửi lại.
- Các đơn `cancelled` cũ được giữ nguyên; hệ thống không thể xác định ngược chúng là chủ sân từ chối hay khách hủy trước khi có trạng thái `rejected` riêng.
- Bản đồ và ảnh minh họa cần Internet. Sân mẫu và tọa độ hiện tại là dữ liệu demo, không xác minh địa chỉ thực tế.
- Khi triển khai, cần dùng `SPORTSLOT_SECRET_KEY` ổn định, HTTPS, tắt debug, sao lưu database định kỳ và cấu hình cookie `Secure` theo HTTPS.
