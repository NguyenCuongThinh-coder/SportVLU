from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify
import sqlite3, os, re, secrets, hmac, hashlib, smtplib
from email.message import EmailMessage
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import date, datetime, time, timezone, timedelta
from zoneinfo import ZoneInfo

app = Flask(__name__)
IS_PRODUCTION = os.environ.get('SPORTSLOT_ENV', '').lower() == 'production'
SECRET_KEY = os.environ.get('SPORTSLOT_SECRET_KEY')
if IS_PRODUCTION and not SECRET_KEY:
    raise RuntimeError('SPORTSLOT_SECRET_KEY must be set in production.')
app.secret_key = SECRET_KEY or secrets.token_hex(32)
cookie_secure = os.environ.get('SPORTSLOT_COOKIE_SECURE')
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=(cookie_secure == '1') if cookie_secure is not None else IS_PRODUCTION,
)
if IS_PRODUCTION and not os.environ.get('SPORTSLOT_DB_PATH'):
    raise RuntimeError('SPORTSLOT_DB_PATH must be set in production.')
DB_PATH = os.environ.get('SPORTSLOT_DB_PATH', os.path.join(os.path.dirname(__file__), 'sportslot.db'))
if IS_PRODUCTION and not os.path.isfile(DB_PATH) and os.environ.get('SPORTSLOT_ALLOW_EMPTY_DB') != '1':
    raise RuntimeError(
        'Production database is missing. Restore it to SPORTSLOT_DB_PATH, '
        'or explicitly set SPORTSLOT_ALLOW_EMPTY_DB=1 for a new deployment.'
    )
APP_TIMEZONE = ZoneInfo('Asia/Ho_Chi_Minh')
TIME_SLOTS = ('06:00–07:00', '07:00–08:00', '08:00–09:00', '09:00–10:00', '10:00–11:00', '11:00–12:00', '13:00–14:00', '14:00–15:00', '15:00–16:00', '16:00–17:00', '17:00–18:00', '18:00–19:00', '19:00–20:00', '20:00–21:00', '21:00–22:00')

SEED_COURTS = [
('Sân Cầu Lông Bình Minh','Cầu lông','Bình Thạnh','90.000',10.8105,106.7091,'Không gian thoáng, phù hợp chơi cùng bạn bè.'),
('Pickleball Riverside','Pickleball','Thủ Đức','150.000',10.8260,106.7460,'Sân pickleball demo, có khu vực chờ.'),
('Cầu Lông Phú Nhuận','Cầu lông','Phú Nhuận','110.000',10.7990,106.6780,'Sân trong nhà, phù hợp luyện tập.'),
('Pickleball Central','Pickleball','Quận 1','180.000',10.7769,106.7009,'Địa điểm demo ở khu vực trung tâm.'),
('Sân Cầu Lông Tân Bình','Cầu lông','Tân Bình','80.000',10.8010,106.6520,'Sân cầu lông demo tại Tân Bình.'),
('Pickleball Green Park','Pickleball','Bình Thạnh','130.000',10.8150,106.7210,'Sân pickleball demo.'),
('Cầu Lông Tân Phú Sport','Cầu lông','Tân Phú','85.000',10.7900,106.6270,'Không gian tập luyện thân thiện.'),
('Pickleball Phú Mỹ Hưng','Pickleball','Quận 7','170.000',10.7290,106.7210,'Sân demo tại khu Nam thành phố.'),
('Cầu Lông Gò Vấp','Cầu lông','Gò Vấp','95.000',10.8380,106.6650,'Sân cầu lông demo.'),
('Pickleball Thảo Điền','Pickleball','Thủ Đức','160.000',10.8030,106.7310,'Sân pickleball demo khu vực Thảo Điền.'),
('Cầu Lông Bình Tân','Cầu lông','Bình Tân','80.000',10.7650,106.6040,'Sân cầu lông demo.'),
('Pickleball Nhà Bè','Pickleball','Nhà Bè','120.000',10.6950,106.7040,'Sân pickleball demo khu vực Nhà Bè.'),
('Cầu Lông Sài Gòn Xanh','Cầu lông','Quận 3','100.000',10.7815,106.6860,'Sân mẫu tại Quận 3; địa chỉ và giá cần xác nhận.'),
('Pickleball Phú Nhuận','Pickleball','Phú Nhuận','140.000',10.7980,106.6750,'Sân mẫu tại Phú Nhuận; địa chỉ và giá cần xác nhận.'),
('Cầu Lông Hiệp Bình','Cầu lông','Thủ Đức','90.000',10.8490,106.7350,'Sân mẫu tại Thủ Đức; địa chỉ và giá cần xác nhận.'),
('Pickleball Tân Bình Arena','Pickleball','Tân Bình','150.000',10.8060,106.6610,'Sân mẫu tại Tân Bình; địa chỉ và giá cần xác nhận.'),
('Cầu Lông Quận 10','Cầu lông','Quận 10','105.000',10.7730,106.6670,'Sân mẫu tại Quận 10; địa chỉ và giá cần xác nhận.'),
('Pickleball Bình Tân Club','Pickleball','Bình Tân','125.000',10.7550,106.6060,'Sân mẫu tại Bình Tân; địa chỉ và giá cần xác nhận.'),
('Cầu Lông Quận 8','Cầu lông','Quận 8','85.000',10.7380,106.6350,'Sân mẫu tại Quận 8; địa chỉ và giá cần xác nhận.'),
('Pickleball Gò Vấp','Pickleball','Gò Vấp','135.000',10.8410,106.6740,'Sân mẫu tại Gò Vấp; địa chỉ và giá cần xác nhận.'),
('Cầu Lông Tân Thới Hiệp','Cầu lông','Quận 12','80.000',10.8670,106.6540,'Sân mẫu tại Quận 12; địa chỉ và giá cần xác nhận.'),
('Pickleball Quận 10','Pickleball','Quận 10','155.000',10.7700,106.6750,'Sân mẫu tại Quận 10; địa chỉ và giá cần xác nhận.'),
('Cầu Lông Phú Mỹ','Cầu lông','Quận 7','120.000',10.7310,106.7180,'Sân mẫu tại Quận 7; địa chỉ và giá cần xác nhận.'),
('Pickleball Tân Phú','Pickleball','Tân Phú','130.000',10.7880,106.6180,'Sân mẫu tại Tân Phú; địa chỉ và giá cần xác nhận.'),
('Cầu Lông Linh Trung','Cầu lông','Thủ Đức','95.000',10.8700,106.7720,'Sân mẫu tại Thủ Đức; địa chỉ và giá cần xác nhận.'),
('Pickleball Quận 8 Riverside','Pickleball','Quận 8','120.000',10.7350,106.6480,'Sân mẫu tại Quận 8; địa chỉ và giá cần xác nhận.'),
('Cầu Lông Bà Điểm','Cầu lông','Hóc Môn','75.000',10.8610,106.5930,'Sân mẫu tại Hóc Môn; địa chỉ và giá cần xác nhận.'),
('Pickleball Bình Chánh','Pickleball','Bình Chánh','110.000',10.6950,106.5900,'Sân mẫu tại Bình Chánh; địa chỉ và giá cần xác nhận.'),
('Cầu Lông Nhà Bè','Cầu lông','Nhà Bè','90.000',10.6900,106.7100,'Sân mẫu tại Nhà Bè; địa chỉ và giá cần xác nhận.'),
('Pickleball Quận 3 Central','Pickleball','Quận 3','165.000',10.7790,106.6900,'Sân mẫu tại Quận 3; địa chỉ và giá cần xác nhận.'),
('Cầu Lông An Phú','Cầu lông','Thủ Đức','115.000',10.8010,106.7440,'Sân mẫu tại Thủ Đức; địa chỉ và giá cần xác nhận.'),
('Pickleball Bình Chánh Garden','Pickleball','Bình Chánh','115.000',10.6870,106.5860,'Sân mẫu tại Bình Chánh; địa chỉ và giá cần xác nhận.'),
('Cầu Lông Hóc Môn Sport','Cầu lông','Hóc Môn','75.000',10.8840,106.5940,'Sân mẫu tại Hóc Môn; địa chỉ và giá cần xác nhận.'),
('Pickleball Quận 12','Pickleball','Quận 12','125.000',10.8680,106.6520,'Sân mẫu tại Quận 12; địa chỉ và giá cần xác nhận.'),
('Cầu Lông Bình Chánh','Cầu lông','Bình Chánh','80.000',10.7000,106.6000,'Sân mẫu tại Bình Chánh; địa chỉ và giá cần xác nhận.'),
('Pickleball Củ Chi','Pickleball','Củ Chi','100.000',10.9730,106.4930,'Sân mẫu tại Củ Chi; địa chỉ và giá cần xác nhận.'),
('Cầu Lông Củ Chi','Cầu lông','Củ Chi','70.000',10.9760,106.4920,'Sân mẫu tại Củ Chi; địa chỉ và giá cần xác nhận.'),
('Pickleball Long Trường','Pickleball','Thủ Đức','130.000',10.7930,106.8240,'Sân mẫu tại Thủ Đức; địa chỉ và giá cần xác nhận.'),
('Cầu Lông Bình Chánh Central','Cầu lông','Bình Chánh','85.000',10.6840,106.6070,'Sân mẫu tại Bình Chánh; địa chỉ và giá cần xác nhận.'),
('Pickleball Tân Bình Park','Pickleball','Tân Bình','145.000',10.7970,106.6440,'Sân mẫu tại Tân Bình; địa chỉ và giá cần xác nhận.')]

def db():
    parent=os.path.dirname(os.path.abspath(DB_PATH))
    os.makedirs(parent,exist_ok=True)
    conn=sqlite3.connect(DB_PATH,timeout=10); conn.row_factory=sqlite3.Row; conn.execute('PRAGMA foreign_keys=ON'); return conn

def backup_database(path,label='pre-migration'):
    backup_path=f'{path}.{label}.bak'
    if os.path.exists(path) and not os.path.exists(backup_path):
        source=sqlite3.connect(path); target=sqlite3.connect(backup_path)
        try: source.backup(target)
        finally: target.close(); source.close()

def init_db():
    with db() as c:
        existing_tables={r['name'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'courts' in existing_tables:
            columns={r['name'] for r in c.execute('PRAGMA table_info(courts)')}
            indexes={r['name'] for r in c.execute('PRAGMA index_list(bookings)')} if 'bookings' in existing_tables else set()
            if 'is_active' not in columns or 'idx_bookings_court_date_slot' not in indexes or 'idx_bookings_user_created' not in indexes:
                backup_database(DB_PATH)
        if 'users' in existing_tables and 'password_reset_tokens' not in existing_tables:
            backup_database(DB_PATH,'pre-account-migration')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, phone TEXT, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'player', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS courts(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, sport TEXT NOT NULL, area TEXT NOT NULL, price TEXT NOT NULL, lat REAL, lng REAL, description TEXT, owner_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP, is_active INTEGER NOT NULL DEFAULT 1, FOREIGN KEY(owner_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY AUTOINCREMENT, court_id INTEGER NOT NULL, user_id INTEGER NOT NULL, play_date TEXT NOT NULL, time_slot TEXT NOT NULL, customer_name TEXT NOT NULL, phone TEXT NOT NULL, note TEXT, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(court_id) REFERENCES courts(id), FOREIGN KEY(user_id) REFERENCES users(id));
        ''')
        court_columns={r['name'] for r in c.execute('PRAGMA table_info(courts)')}
        if 'is_active' not in court_columns:
            c.execute('ALTER TABLE courts ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1')
        c.execute('CREATE INDEX IF NOT EXISTS idx_bookings_court_date_slot ON bookings(court_id,play_date,time_slot,status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_bookings_user_created ON bookings(user_id,created_at)')
        c.execute('''CREATE TABLE IF NOT EXISTS password_reset_tokens(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_password_reset_user ON password_reset_tokens(user_id,expires_at)')
        count=c.execute('SELECT COUNT(*) FROM courts').fetchone()[0]
        seed_demo_courts = not IS_PRODUCTION or os.environ.get('SPORTSLOT_SEED_DEMO') == '1'
        if count==0 and seed_demo_courts:
            c.executemany('INSERT INTO courts(name,sport,area,price,lat,lng,description) VALUES(?,?,?,?,?,?,?)',SEED_COURTS)

def current_user():
    if 'user_id' not in session: return None
    with db() as c: return c.execute('SELECT id,name,email,phone,role FROM users WHERE id=?',(session['user_id'],)).fetchone()

def login_required(fn):
    @wraps(fn)
    def wrapper(*a,**kw):
        if not current_user(): flash('Vui lòng đăng nhập để sử dụng chức năng này.','warning'); return redirect(url_for('login',next=request.path))
        return fn(*a,**kw)
    return wrapper

def role_required(role):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a,**kw):
            u=current_user()
            if not u: flash('Vui lòng đăng nhập.','warning'); return redirect(url_for('login'))
            if u['role'] != role: abort(403)
            return fn(*a,**kw)
        return wrapper
    return deco

def court_form_values():
    name=request.form.get('name','').strip(); sport=request.form.get('sport',''); area=request.form.get('area','').strip()
    raw_price=request.form.get('price','').strip(); digits=raw_price.replace('.','').replace(',','')
    if not name or len(name)>150 or sport not in ('Cầu lông','Pickleball') or not area or len(area)>120:
        return None, 'Tên sân, môn thể thao và khu vực chưa hợp lệ.'
    if not re.fullmatch(r'(?:[0-9]+|[0-9]{1,3}(?:[.,][0-9]{3})+)',raw_price) or not digits or len(digits)>10 or int(digits)<1:
        return None, 'Giá phải là số nguyên dương, ví dụ 120.000.'
    price=f'{int(digits):,}'.replace(',','.')
    raw_lat=request.form.get('lat','').strip(); raw_lng=request.form.get('lng','').strip()
    if bool(raw_lat)!=bool(raw_lng): return None, 'Vui lòng nhập cả vĩ độ và kinh độ.'
    try:
        lat=float(raw_lat) if raw_lat else None; lng=float(raw_lng) if raw_lng else None
    except ValueError: return None, 'Vĩ độ và kinh độ phải là số.'
    if lat is not None and (not -90<=lat<=90 or not -180<=lng<=180): return None, 'Tọa độ nằm ngoài phạm vi hợp lệ.'
    return {'name':name,'sport':sport,'area':area,'price':price,'lat':lat,'lng':lng,'description':request.form.get('description','').strip()[:1000]}, None

def csrf_value():
    if '_csrf_token' not in session: session['_csrf_token']=secrets.token_urlsafe(32)
    return session['_csrf_token']

def safe_local_path(path):
    return bool(path and path.startswith('/') and not path.startswith('//') and '\\' not in path)

def local_now(): return datetime.now(APP_TIMEZONE)
def local_today(): return local_now().date()

def booking_has_started(booking):
    try:
        play_date=date.fromisoformat(booking['play_date'])
        start_text=booking['time_slot'].split('–',1)[0]
        starts_at=datetime.combine(play_date,time.fromisoformat(start_text),tzinfo=APP_TIMEZONE)
        return local_now() >= starts_at
    except (ValueError, IndexError, KeyError, TypeError):
        return True

def email_ready():
    return bool(os.environ.get('SPORTSLOT_SMTP_HOST') and os.environ.get('SPORTSLOT_SMTP_FROM'))

def send_email(recipient, subject, body):
    host=os.environ.get('SPORTSLOT_SMTP_HOST'); sender=os.environ.get('SPORTSLOT_SMTP_FROM')
    if not host or not sender:
        app.logger.info('Email notification skipped because SMTP is not configured.')
        return False
    message=EmailMessage(); message['From']=sender; message['To']=recipient; message['Subject']=subject; message.set_content(body)
    try:
        port=int(os.environ.get('SPORTSLOT_SMTP_PORT','587'))
        if os.environ.get('SPORTSLOT_SMTP_SSL')=='1':
            with smtplib.SMTP_SSL(host,port,timeout=10) as server:
                if os.environ.get('SPORTSLOT_SMTP_USER'): server.login(os.environ['SPORTSLOT_SMTP_USER'],os.environ.get('SPORTSLOT_SMTP_PASSWORD',''))
                server.send_message(message)
        else:
            with smtplib.SMTP(host,port,timeout=10) as server:
                server.starttls()
                if os.environ.get('SPORTSLOT_SMTP_USER'): server.login(os.environ['SPORTSLOT_SMTP_USER'],os.environ.get('SPORTSLOT_SMTP_PASSWORD',''))
                server.send_message(message)
        return True
    except (OSError, smtplib.SMTPException, ValueError) as error:
        app.logger.warning('Could not send SportSlot email notification: %s',error)
        return False

def send_booking_notification(booking_id, status, recipient_role):
    with db() as c:
        row=c.execute('''SELECT bookings.*,courts.name AS court_name,courts.owner_id,
            player.name AS player_name,player.email AS player_email,
            owner.email AS owner_email,owner.name AS owner_name
            FROM bookings JOIN courts ON courts.id=bookings.court_id
            JOIN users AS player ON player.id=bookings.user_id
            LEFT JOIN users AS owner ON owner.id=courts.owner_id WHERE bookings.id=?''',(booking_id,)).fetchone()
    if not row: return False
    recipient=row['player_email'] if recipient_role=='player' else row['owner_email']
    if not recipient: return False
    labels={'pending':'chờ xác nhận','confirmed':'đã xác nhận','rejected':'bị chủ sân từ chối','cancelled':'đã được khách hủy','completed':'đã hoàn thành'}
    subject=f'Cập nhật yêu cầu đặt sân SS{booking_id:05d}'
    body=(f'Yêu cầu SS{booking_id:05d} tại sân {row["court_name"]} '
          f'({row["play_date"]}, {row["time_slot"]}) hiện {labels.get(status,status)}.')
    return send_email(recipient,subject,body)

def booking_has_ended(booking):
    try:
        play_date=date.fromisoformat(booking['play_date'])
        end_text=booking['time_slot'].split('–',1)[1]
        ends_at=datetime.combine(play_date,time.fromisoformat(end_text),tzinfo=APP_TIMEZONE)
        return local_now() >= ends_at
    except (ValueError, IndexError, KeyError, TypeError):
        return False

@app.before_request
def protect_post():
    if request.method == 'POST':
        expected=session.get('_csrf_token', '')
        supplied=request.form.get('_csrf_token', '')
        if not expected or not hmac.compare_digest(expected, supplied): abort(400)

@app.context_processor
def inject_user(): return {'current_user':current_user(), 'today':local_today().isoformat(), 'csrf_token':csrf_value()}

@app.route('/')
def index():
    with db() as c: courts=c.execute('SELECT * FROM courts WHERE is_active=1 ORDER BY id DESC LIMIT 6').fetchall()
    return render_template('index.html',courts=courts)

@app.route('/courts')
def courts():
    sport=request.args.get('sport',''); area=request.args.get('area',''); q=request.args.get('q','')
    sql='SELECT * FROM courts WHERE is_active=1'; args=[]
    if sport: sql+=' AND sport=?'; args.append(sport)
    if area: sql+=' AND area LIKE ?'; args.append('%'+area+'%')
    if q: sql+=' AND (name LIKE ? OR area LIKE ? OR description LIKE ?)'; args += ['%'+q+'%']*3
    with db() as c: rows=c.execute(sql+' ORDER BY id DESC',args).fetchall()
    return render_template('courts.html',courts=rows,sport=sport,area=area,q=q)

@app.route('/courts/<int:court_id>')
def court_detail(court_id):
    with db() as c: court=c.execute('SELECT courts.*,users.name AS owner_name FROM courts LEFT JOIN users ON users.id=courts.owner_id WHERE courts.id=?',(court_id,)).fetchone()
    if not court: abort(404)
    return render_template('detail.html',court=court)

@app.route('/register',methods=['GET','POST'])
def register():
    if current_user(): return redirect(url_for('index'))
    if request.method=='POST':
        name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower(); phone=request.form.get('phone','').strip(); password=request.form.get('password',''); confirm=request.form.get('confirm_password',''); role=request.form.get('role','player')
        if not name or len(name)>100 or not email or len(email)>254 or not password: flash('Vui lòng nhập đầy đủ thông tin hợp lệ.','danger')
        elif not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$',email): flash('Email chưa đúng định dạng.','danger')
        elif len(password)<8 or len(password)>128: flash('Mật khẩu cần từ 8 đến 128 ký tự.','danger')
        elif password!=confirm: flash('Mật khẩu xác nhận không khớp.','danger')
        elif len(phone)>30: flash('Số điện thoại không được dài quá 30 ký tự.','danger')
        elif role not in ('player','owner'): flash('Vai trò không hợp lệ.','danger')
        else:
            try:
                with db() as c: cur=c.execute('INSERT INTO users(name,email,phone,password_hash,role) VALUES(?,?,?,?,?)',(name,email,phone,generate_password_hash(password),role)); uid=cur.lastrowid
                session.clear(); session['user_id']=uid; flash('Tạo tài khoản thành công!','success'); return redirect(url_for('owner_dashboard') if role=='owner' else url_for('index'))
            except sqlite3.IntegrityError: flash('Email này đã được đăng ký. Hãy đăng nhập hoặc dùng email khác.','danger')
    return render_template('auth.html',mode='register')

@app.route('/login',methods=['GET','POST'])
def login():
    if current_user():
        requested=request.args.get('next','')
        return redirect(requested if safe_local_path(requested) else url_for('index'))
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        with db() as c: user=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        if not user or not check_password_hash(user['password_hash'],password): flash('Email hoặc mật khẩu không chính xác.','danger')
        else:
            session.clear(); session['user_id']=user['id']; flash('Đăng nhập thành công.','success')
            next_url=request.form.get('next') or request.args.get('next','')
            if safe_local_path(next_url): return redirect(next_url)
            return redirect(url_for('owner_dashboard') if user['role']=='owner' else url_for('index'))
    return render_template('auth.html',mode='login')

@app.route('/logout',methods=['POST'])
@login_required
def logout(): session.clear(); flash('Bạn đã đăng xuất.','success'); return redirect(url_for('index'))

@app.route('/profile',methods=['GET','POST'])
@login_required
def profile():
    u=current_user()
    if request.method=='POST':
        name=request.form.get('name','').strip(); phone=request.form.get('phone','').strip()
        if not name or len(name)>100 or len(phone)>30:
            flash('Tên hoặc số điện thoại chưa hợp lệ.','danger')
        else:
            with db() as c: c.execute('UPDATE users SET name=?,phone=? WHERE id=?',(name,phone,u['id']))
            flash('Đã cập nhật hồ sơ.','success')
            return redirect(url_for('profile'))
    return render_template('profile.html',user=u)

@app.route('/profile/password',methods=['POST'])
@login_required
def change_password():
    u=current_user(); current=request.form.get('current_password',''); new=request.form.get('new_password',''); confirm=request.form.get('confirm_password','')
    with db() as c: row=c.execute('SELECT password_hash FROM users WHERE id=?',(u['id'],)).fetchone()
    if not check_password_hash(row['password_hash'],current): flash('Mật khẩu hiện tại không chính xác.','danger')
    elif len(new)<8 or len(new)>128: flash('Mật khẩu mới cần từ 8 đến 128 ký tự.','danger')
    elif new!=confirm: flash('Mật khẩu xác nhận không khớp.','danger')
    elif check_password_hash(row['password_hash'],new): flash('Mật khẩu mới phải khác mật khẩu hiện tại.','warning')
    else:
        with db() as c: c.execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(new),u['id']))
        session.clear(); flash('Đổi mật khẩu thành công. Vui lòng đăng nhập lại.','success')
        return redirect(url_for('login'))
    return redirect(url_for('profile'))

@app.route('/forgot-password',methods=['GET','POST'])
def forgot_password():
    if request.method=='POST':
        email=request.form.get('email','').strip().lower()
        with db() as c: user=c.execute('SELECT id,email FROM users WHERE email=?',(email,)).fetchone()
        public_url=os.environ.get('SPORTSLOT_PUBLIC_URL','').rstrip('/')
        if user and email_ready() and public_url:
            raw_token=secrets.token_urlsafe(32); token_hash=hashlib.sha256(raw_token.encode()).hexdigest()
            expires=(datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat()
            with db() as c:
                c.execute('DELETE FROM password_reset_tokens WHERE user_id=?',(user['id'],))
                c.execute('INSERT INTO password_reset_tokens(user_id,token_hash,expires_at) VALUES(?,?,?)',(user['id'],token_hash,expires))
            link=public_url+url_for('reset_password',token=raw_token)
            if not send_email(user['email'],'Đặt lại mật khẩu SportVLU',f'Bạn đã yêu cầu đặt lại mật khẩu. Mở liên kết trong 30 phút: {link}\nNếu bạn không yêu cầu, hãy bỏ qua email này.'):
                with db() as c: c.execute('DELETE FROM password_reset_tokens WHERE user_id=?',(user['id'],))
        flash('Nếu email thuộc tài khoản và dịch vụ email đã cấu hình, hướng dẫn đặt lại mật khẩu sẽ được gửi.','info')
        return redirect(url_for('forgot_password'))
    return render_template('password_reset.html',mode='request')

@app.route('/reset-password/<token>',methods=['GET','POST'])
def reset_password(token):
    token_hash=hashlib.sha256(token.encode()).hexdigest()
    now=datetime.now(timezone.utc).isoformat()
    with db() as c: reset=c.execute('SELECT user_id FROM password_reset_tokens WHERE token_hash=? AND expires_at>?',(token_hash,now)).fetchone()
    if not reset:
        flash('Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.','danger')
        return redirect(url_for('forgot_password'))
    if request.method=='POST':
        password=request.form.get('password',''); confirm=request.form.get('confirm_password','')
        if len(password)<8 or len(password)>128: flash('Mật khẩu cần từ 8 đến 128 ký tự.','danger')
        elif password!=confirm: flash('Mật khẩu xác nhận không khớp.','danger')
        else:
            with db() as c:
                c.execute('BEGIN IMMEDIATE')
                valid=c.execute('SELECT user_id FROM password_reset_tokens WHERE token_hash=? AND expires_at>?',(token_hash,datetime.now(timezone.utc).isoformat())).fetchone()
                if not valid:
                    flash('Liên kết đặt lại mật khẩu đã hết hạn hoặc đã được sử dụng.','danger')
                    return redirect(url_for('forgot_password'))
                c.execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(password),valid['user_id']))
                c.execute('DELETE FROM password_reset_tokens WHERE user_id=?',(valid['user_id'],))
            flash('Đặt lại mật khẩu thành công. Hãy đăng nhập bằng mật khẩu mới.','success')
            return redirect(url_for('login'))
    return render_template('password_reset.html',mode='reset',token=token)

@app.route('/api/courts/<int:court_id>/availability')
def court_availability(court_id):
    play_date=request.args.get('date','')
    try: parsed_date=date.fromisoformat(play_date)
    except ValueError: parsed_date=None
    if not parsed_date or parsed_date.isoformat()!=play_date or parsed_date<local_today():
        return jsonify(error='Ngày chơi không hợp lệ.'),400
    with db() as c:
        court=c.execute('SELECT id FROM courts WHERE id=? AND is_active=1',(court_id,)).fetchone()
        if not court: abort(404)
        rows=c.execute("SELECT time_slot FROM bookings WHERE court_id=? AND play_date=? AND status IN ('pending','confirmed')",(court_id,play_date)).fetchall()
    booked={row['time_slot'] for row in rows}
    return jsonify(booked_slots=[slot for slot in TIME_SLOTS if slot in booked],available_slots=[slot for slot in TIME_SLOTS if slot not in booked])

@app.route('/book/<int:court_id>',methods=['GET','POST'])
@login_required
def book(court_id):
    u=current_user()
    if u['role']!='player': flash('Chủ sân vui lòng dùng tài khoản người chơi để gửi yêu cầu đặt sân.','warning'); return redirect(url_for('court_detail',court_id=court_id))
    with db() as c: court=c.execute('SELECT * FROM courts WHERE id=? AND is_active=1',(court_id,)).fetchone()
    if not court: abort(404)
    if request.method=='POST':
        play_date=request.form.get('play_date',''); slot=request.form.get('time_slot',''); name=request.form.get('customer_name','').strip(); phone=request.form.get('phone','').strip(); note=request.form.get('note','').strip()
        clash=True
        try: parsed_date=date.fromisoformat(play_date)
        except ValueError: parsed_date=None
        if not parsed_date or parsed_date.isoformat()!=play_date or parsed_date<local_today() or slot not in TIME_SLOTS or not name or len(name)>100 or not phone or len(phone)>30: flash('Vui lòng kiểm tra ngày chơi, khung giờ và thông tin liên hệ.','danger')
        else:
            with db() as c:
                c.execute('BEGIN IMMEDIATE')
                still_active=c.execute('SELECT is_active FROM courts WHERE id=?',(court_id,)).fetchone()
                if not still_active or not still_active['is_active']:
                    flash('Sân này hiện không nhận đặt lịch mới.','warning')
                    return redirect(url_for('court_detail',court_id=court_id))
                clash=c.execute("SELECT id FROM bookings WHERE court_id=? AND play_date=? AND time_slot=? AND status IN ('pending','confirmed')",(court_id,play_date,slot)).fetchone()
                if clash: flash('Khung giờ này đã có yêu cầu đang chờ hoặc đã xác nhận. Vui lòng chọn giờ khác.','danger')
                else:
                    cur=c.execute('INSERT INTO bookings(court_id,user_id,play_date,time_slot,customer_name,phone,note) VALUES(?,?,?,?,?,?,?)',(court_id,u['id'],play_date,slot,name,phone,note)); bid=cur.lastrowid
            if not clash:
                flash(f'Đã gửi yêu cầu đặt sân. Mã yêu cầu: SS{bid:05d}','success')
                send_booking_notification(bid,'pending','player')
                send_booking_notification(bid,'pending','owner')
                return redirect(url_for('my_bookings'))
    return render_template('booking.html',court=court,user=u)

@app.route('/my-bookings')
@login_required
def my_bookings():
    u=current_user()
    if u['role']!='player': flash('Trang lịch đặt dành cho tài khoản người chơi.','warning'); return redirect(url_for('owner_dashboard'))
    with db() as c: rows=c.execute('SELECT bookings.*,courts.name AS court_name,courts.area,courts.sport FROM bookings JOIN courts ON courts.id=bookings.court_id WHERE bookings.user_id=? ORDER BY bookings.created_at DESC',(u['id'],)).fetchall()
    cancellable={row['id'] for row in rows if row['status'] in ('pending','confirmed') and not booking_has_started(row)}
    return render_template('my_bookings.html',bookings=rows,cancellable_booking_ids=cancellable)

@app.route('/my-bookings/<int:booking_id>/cancel',methods=['POST'])
@login_required
def cancel_booking(booking_id):
    u=current_user()
    if u['role']!='player': abort(403)
    notify_owner=False
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT * FROM bookings WHERE id=? AND user_id=?',(booking_id,u['id'])).fetchone()
        if not row: abort(404)
        if row['status'] in ('pending','confirmed') and not booking_has_started(row):
            c.execute("UPDATE bookings SET status='cancelled' WHERE id=?",(booking_id,)); flash('Đã hủy yêu cầu đặt sân.','success')
            notify_owner=True
        else: flash('Chỉ có thể hủy yêu cầu chưa bắt đầu.','warning')
    if notify_owner: send_booking_notification(booking_id,'cancelled','owner')
    return redirect(url_for('my_bookings'))

@app.route('/owner')
@role_required('owner')
def owner_dashboard():
    u=current_user(); status=request.args.get('status',''); play_date=request.args.get('play_date','')
    sql='SELECT bookings.*,courts.name AS court_name,courts.area,courts.sport,users.name AS player_name,users.email AS player_email FROM bookings JOIN courts ON courts.id=bookings.court_id JOIN users ON users.id=bookings.user_id WHERE courts.owner_id=?'; args=[u['id']]
    if status in ('pending','confirmed','rejected','cancelled','completed'): sql+=' AND bookings.status=?'; args.append(status)
    if play_date:
        try: parsed_date=date.fromisoformat(play_date)
        except ValueError: parsed_date=None
        if parsed_date and parsed_date.isoformat()==play_date: sql+=' AND bookings.play_date=?'; args.append(play_date)
        else: play_date=''
    with db() as c: bookings=c.execute(sql+' ORDER BY bookings.play_date DESC,bookings.time_slot',args).fetchall(); own_courts=c.execute('SELECT * FROM courts WHERE owner_id=? ORDER BY id DESC',(u['id'],)).fetchall()
    completable_booking_ids={row['id'] for row in bookings if row['status']=='confirmed' and booking_has_ended(row)}
    return render_template('owner.html',bookings=bookings,courts=own_courts,status=status,play_date=play_date,completable_booking_ids=completable_booking_ids)

@app.route('/owner/bookings/<int:booking_id>/<action>',methods=['POST'])
@role_required('owner')
def owner_booking_action(booking_id,action):
    if action not in ('confirm','reject','complete'): abort(404)
    u=current_user(); new={'confirm':'confirmed','reject':'rejected','complete':'completed'}[action]
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT bookings.*,courts.owner_id FROM bookings JOIN courts ON courts.id=bookings.court_id WHERE bookings.id=?',(booking_id,)).fetchone()
        if not row: abort(404)
        if row['owner_id'] != u['id']: abort(403)
        valid_transition=(action in ('confirm','reject') and row['status']=='pending') or (action=='complete' and row['status']=='confirmed' and booking_has_ended(row))
        if not valid_transition:
            flash('Trạng thái yêu cầu không cho phép thao tác này hoặc lịch chơi chưa kết thúc.','warning'); return redirect(url_for('owner_dashboard'))
        if action=='confirm':
            clash=c.execute("SELECT id FROM bookings WHERE court_id=? AND play_date=? AND time_slot=? AND id<>? AND status IN ('pending','confirmed')",(row['court_id'],row['play_date'],row['time_slot'],booking_id)).fetchone()
            if clash: flash('Không thể xác nhận: đã có lịch khác được xác nhận cùng khung giờ.','danger'); return redirect(url_for('owner_dashboard'))
        c.execute('UPDATE bookings SET status=? WHERE id=?',(new,booking_id))
    send_booking_notification(booking_id,new,'player')
    flash('Đã cập nhật trạng thái yêu cầu.','success'); return redirect(url_for('owner_dashboard'))

@app.route('/owner/courts/add',methods=['POST'])
@role_required('owner')
def add_court():
    u=current_user(); values,error=court_form_values()
    if error: flash(error,'danger')
    else:
        with db() as c: c.execute('INSERT INTO courts(name,sport,area,price,lat,lng,description,owner_id) VALUES(?,?,?,?,?,?,?,?)',(values['name'],values['sport'],values['area'],values['price'],values['lat'],values['lng'],values['description'],u['id']))
        flash('Đã thêm sân mới.','success')
    return redirect(url_for('owner_dashboard'))

@app.route('/owner/courts/<int:court_id>/edit',methods=['POST'])
@role_required('owner')
def edit_court(court_id):
    u=current_user(); values,error=court_form_values()
    with db() as c:
        court=c.execute('SELECT id FROM courts WHERE id=? AND owner_id=?',(court_id,u['id'])).fetchone()
        if not court: abort(404)
        if error: flash(error,'danger')
        else:
            c.execute('UPDATE courts SET name=?,sport=?,area=?,price=?,lat=?,lng=?,description=? WHERE id=? AND owner_id=?',(values['name'],values['sport'],values['area'],values['price'],values['lat'],values['lng'],values['description'],court_id,u['id']))
            flash('Đã cập nhật thông tin sân.','success')
    return redirect(url_for('owner_dashboard',_anchor='my-courts'))

@app.route('/owner/courts/<int:court_id>/delete',methods=['POST'])
@role_required('owner')
def delete_court(court_id):
    u=current_user()
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        court=c.execute('SELECT * FROM courts WHERE id=? AND owner_id=?',(court_id,u['id'])).fetchone()
        if not court: abort(404)
        has=c.execute("SELECT COUNT(*) FROM bookings WHERE court_id=? AND status IN ('pending','confirmed')",(court_id,)).fetchone()[0]
        if has: flash('Sân còn lịch đang chờ/đã xác nhận nên chưa thể ngừng kinh doanh.','warning')
        else: c.execute('UPDATE courts SET is_active=0 WHERE id=? AND owner_id=?',(court_id,u['id'])); flash('Đã ngừng kinh doanh sân; lịch sử đặt sân vẫn được giữ.','success')
    return redirect(url_for('owner_dashboard'))

@app.route('/owner/courts/<int:court_id>/activate',methods=['POST'])
@role_required('owner')
def activate_court(court_id):
    u=current_user()
    with db() as c:
        result=c.execute('UPDATE courts SET is_active=1 WHERE id=? AND owner_id=?',(court_id,u['id']))
        if result.rowcount!=1: abort(404)
    flash('Đã mở kinh doanh lại sân.','success')
    return redirect(url_for('owner_dashboard',_anchor='my-courts'))

@app.errorhandler(403)
def forbidden(e): return render_template('message.html',title='Không có quyền truy cập',message='Tài khoản của bạn không có quyền mở trang này.'),403
@app.errorhandler(400)
def bad_request(e): return render_template('message.html',title='Yêu cầu không hợp lệ',message='Trang đã hết hạn hoặc biểu mẫu không hợp lệ. Vui lòng tải lại và thử lại.'),400
@app.errorhandler(404)
def not_found(e): return render_template('message.html',title='Không tìm thấy',message='Trang hoặc dữ liệu bạn yêu cầu không tồn tại.'),404

init_db()
if __name__=='__main__': app.run(debug=os.environ.get('SPORTSLOT_DEBUG') == '1', port=5000)
