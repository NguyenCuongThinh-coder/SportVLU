# SPORTVLU

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

Repository có `render.yaml` để tạo Render Web Service trên gói Free, chạy Gunicorn một worker và SQLite tại `/tmp/sportslot.db`. Cấu hình này dành cho demo, không cần dịch vụ trả phí và không tạo dịch vụ chỉ bằng việc thêm file vào Git.

1. Đẩy source lên nhánh `main` rồi kết nối repository với Render bằng Blueprint (`render.yaml`). Không thêm `sportslot.db`, file `.bak`, `.env`, mật khẩu hay khóa SMTP vào Git.
2. Render sinh `SPORTSLOT_SECRET_KEY`; cookie phiên tự bật `Secure`. `SPORTSLOT_ALLOW_EMPTY_DB=1` cho phép ứng dụng tạo database mới và `SPORTSLOT_SEED_DEMO=1` thêm 40 sân mẫu khi database trống. Tài khoản khách/chủ sân có thể đăng ký trên website.
3. Trong form tạo service, xác nhận instance là **Free ($0/month)**. Nếu tạo service thủ công thay vì Blueprint, dùng build command `pip install -r requirements.txt`, start command `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 60`, và đặt các biến `SPORTSLOT_ENV=production`, `SPORTSLOT_SECRET_KEY` (secret ngẫu nhiên), `SPORTSLOT_DB_PATH=/tmp/sportslot.db`, `SPORTSLOT_ALLOW_EMPTY_DB=1`, `SPORTSLOT_SEED_DEMO=1`.
4. Sau deploy, kiểm tra đăng ký/đăng nhập, trang chủ, đặt sân và quyền chủ sân trên URL HTTPS của Render. Dữ liệu SQLite trên Free là tạm thời: có thể mất khi service ngủ, khởi động lại hoặc deploy lại. Khi filesystem được làm mới, database và 40 sân demo được tạo lại; tài khoản và đơn đặt do người dùng tạo trước đó không được khôi phục. Không dùng bản demo này cho dữ liệu thật.

Free web service có thể ngủ sau thời gian không hoạt động và lần truy cập kế tiếp sẽ mất thời gian khởi động. SMTP outbound ở các cổng 25/465/587 bị chặn trên Render Free, nên tính năng gửi email có thể không hoạt động từ service này. Render Free phù hợp để trình diễn/thử nghiệm, không phải dịch vụ production cần lưu dữ liệu ổn định.

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

- Migration thêm cột `courts.is_active`, `courts.image_path` và bảng token đặt lại mật khẩu theo cách tương thích với dữ liệu cũ. Ứng dụng tạo bản sao riêng trước migration; các bản sao cũ không bị ghi đè.
- Ảnh sân tải lên là JPG, PNG hoặc WebP, tối đa 5 MB, được lưu trong `static/uploads/`. Ảnh lưu trên Render Free có thể mất khi service được deploy lại hoặc filesystem được làm mới; muốn lưu lâu dài cần dùng object storage.
- Ngừng kinh doanh là thao tác ẩn sân khỏi tìm kiếm; lịch sử đặt vẫn được giữ. Sân có lịch chờ/đã xác nhận phải xử lý trước khi ngừng.
- Khung giờ hiện có độ dài cố định một tiếng. Chưa tích hợp cổng thanh toán hoặc SMS; email yêu cầu SMTP hoạt động. Nếu email không gửi được, thao tác đặt/trạng thái vẫn được lưu nhưng hiện chưa có hàng đợi gửi lại.
- Các đơn `cancelled` cũ được giữ nguyên; hệ thống không thể xác định ngược chúng là chủ sân từ chối hay khách hủy trước khi có trạng thái `rejected` riêng.
- Bản đồ và ảnh minh họa cần Internet. Sân mẫu và tọa độ hiện tại là dữ liệu demo, không xác minh địa chỉ thực tế.
- Khi triển khai, cần dùng `SPORTSLOT_SECRET_KEY` ổn định, HTTPS, tắt debug, sao lưu database định kỳ và cấu hình cookie `Secure` theo HTTPS.
