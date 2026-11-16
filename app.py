import os
import io
import json
import secrets
import re
import uuid
import time
import functools
from datetime import datetime
from collections import defaultdict
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import qrcode
from reporting import (
    LOAN_COLUMNS, RECORD_COLUMNS, create_workbook, excel_date,
    matches_loan, matches_record,
)

LOCAL_SETTINGS = {}
local_settings_path = os.path.join(os.path.dirname(__file__), 'local_settings.json')
if os.path.isfile(local_settings_path):
    with open(local_settings_path, encoding='utf-8') as settings_file:
        LOCAL_SETTINGS = json.load(settings_file)

app = Flask(__name__)

# ----------------- 安全性設定 -----------------
app.secret_key = os.environ.get('SECRET_KEY') or LOCAL_SETTINGS.get('secret_key') or secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 上傳限制 5MB

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'inventory.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ----------------- 管理員帳號密碼 -----------------
ADMIN_USERS = LOCAL_SETTINGS.get('admin_users', {})

# ----------------- 防暴力破解機制 -----------------
FAILED_LOGINS = defaultdict(lambda: {'count': 0, 'locked_until': 0})
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_TIME = 600

def is_ip_locked(ip):
    record = FAILED_LOGINS[ip]
    if time.time() < record['locked_until']:
        return True, int(record['locked_until'] - time.time())
    if record['locked_until'] != 0 and time.time() >= record['locked_until']:
        FAILED_LOGINS[ip] = {'count': 0, 'locked_until': 0}
    return False, 0

def record_login_failure(ip):
    FAILED_LOGINS[ip]['count'] += 1
    if FAILED_LOGINS[ip]['count'] >= MAX_FAILED_ATTEMPTS:
        FAILED_LOGINS[ip]['locked_until'] = time.time() + LOCKOUT_TIME

def reset_login_attempts(ip):
    if ip in FAILED_LOGINS:
        del FAILED_LOGINS[ip]

# ----------------- 權限驗證裝飾器 -----------------
def admin_required(view_func):
    @functools.wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            flash("此頁面僅限管理員存取，請先登入！", "warning")
            return redirect(url_for('login', next=request.url))
        return view_func(*args, **kwargs)
    return wrapper

# ----------------- 資料庫模型 -----------------
db = SQLAlchemy(app)

class Box(db.Model):
    __tablename__ = 'boxes'
    id = db.Column(db.Integer, primary_key=True)
    box_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), default="產線區")
    description = db.Column(db.String(200), default="")
    items = db.relationship('Item', backref='box', lazy=True, cascade="all, delete-orphan")

class Item(db.Model):
    __tablename__ = 'items'
    id = db.Column(db.Integer, primary_key=True)
    box_id = db.Column(db.Integer, db.ForeignKey('boxes.id'), nullable=False)
    mitac_pn = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default="")
    stock = db.Column(db.Integer, default=0)
    image_filename = db.Column(db.String(200), default="")

class Log(db.Model):
    __tablename__ = 'logs'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    operator = db.Column(db.String(100), nullable=False)
    box_name = db.Column(db.String(100), nullable=False)
    mitac_pn = db.Column(db.String(100), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    action_type = db.Column(db.String(20), default="領出")
    note = db.Column(db.String(200), default="")

# ----------------- 核心功能：自動抓取 tunnel.log 最新網址 -----------------
def get_current_tunnel_url():
    """自動讀取由 2_一鍵啟動系統.bat 產生的 tunnel.log 中的 Cloudflare 網址"""
    log_path = os.path.join(BASE_DIR, 'tunnel.log')
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # 搜尋 https://xxxx.trycloudflare.com 格式
                match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', content)
                if match:
                    return match.group(0)
        except Exception:
            pass
    return None

# ----------------- 使用者與認證路由 -----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    client_ip = request.headers.get('CF-Connecting-IP', request.remote_addr)

    if request.method == 'POST':
        locked, remaining = is_ip_locked(client_ip)
        if locked:
            flash(f"密碼錯誤次數過多，IP 已被鎖定！請在 {remaining} 秒後再試。", "danger")
            return render_template('login.html')

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if username in ADMIN_USERS and check_password_hash(ADMIN_USERS[username], password):
            reset_login_attempts(client_ip)
            session.clear()
            session['is_admin'] = True
            session['admin_user'] = username
            flash(f"登入成功！歡迎管理者 {username}", "success")
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('admin')
            return redirect(next_page)
        else:
            record_login_failure(client_ip)
            remaining_attempts = MAX_FAILED_ATTEMPTS - FAILED_LOGINS[client_ip]['count']
            if remaining_attempts > 0:
                flash(f"帳號或密碼錯誤！剩餘 {remaining_attempts} 次嘗試機會。", "danger")
            else:
                flash("密碼錯誤次數過多，IP 已被鎖定 10 分鐘！", "danger")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("已成功登出！", "info")
    return redirect(url_for('index'))

@app.route('/')
def index():
    boxes = Box.query.all()
    return render_template('index.html', boxes=boxes)

@app.route('/box/<string:box_code>')
def view_box(box_code):
    box = Box.query.filter_by(box_code=box_code).first_or_404()
    return render_template('box_view.html', box=box)

@app.route('/checkout', methods=['POST'])
def checkout():
    item_id = request.form.get('item_id', type=int)
    quantity = request.form.get('quantity', type=int)
    operator = request.form.get('operator', '').strip()
    note = request.form.get('note', '').strip()

    if not operator:
        flash("請輸入操作人員工號或姓名！", "danger")
        return redirect(request.referrer)
    if not quantity or quantity <= 0:
        flash("領出數量必須大於 0！", "danger")
        return redirect(request.referrer)

    item = Item.query.get_or_404(item_id)
    if item.stock < quantity:
        flash(f"庫存不足！【{item.name}】目前庫存僅剩 {item.stock} 件。", "danger")
        return redirect(request.referrer)

    item.stock -= quantity

    new_log = Log(
        operator=operator,
        box_name=item.box.name,
        mitac_pn=item.mitac_pn,
        item_name=item.name,
        quantity=quantity,
        action_type="領出",
        note=note
    )
    db.session.add(new_log)
    db.session.commit()

    flash(f"成功領出 【{item.name}】 {quantity} 件！剩餘庫存：{item.stock}", "success")
    return redirect(url_for('view_box', box_code=item.box.box_code))

@app.route('/records')
def records():
    logs = Log.query.order_by(Log.timestamp.desc()).all()
    return render_template('records.html', logs=logs)


@app.route('/records/export')
def export_records():
    logs = Log.query.order_by(Log.timestamp.desc()).yield_per(500)
    rows = (
        (
            log.timestamp, log.item_name, log.action_type,
            -abs(log.quantity) if log.action_type == '領出' else log.quantity,
            log.box_name, log.mitac_pn, log.operator, log.note,
        )
        for log in logs if matches_record(log, request.args)
    )
    output = create_workbook('Stock history', RECORD_COLUMNS, rows, request.args.get('lang'))
    response = send_file(
        output, as_attachment=True,
        download_name=f"stock-history-{datetime.now():%Y%m%d}.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response.headers['Cache-Control'] = 'private, no-store'
    return response

# ----------------- 管理員後台控制 -----------------
@app.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin():
    if request.method == 'POST':
        action = request.form.get('action')
        admin_user = session.get('admin_user', 'Admin')

        # 1. 修改庫存
        if action == 'update_stock':
            item_id = request.form.get('item_id', type=int)
            mode = request.form.get('mode')
            qty = request.form.get('qty', type=int)
            item = Item.query.get_or_404(item_id)

            if mode == 'add' and qty > 0:
                item.stock += qty
                action_name = "入庫補充"
                log_qty = qty
            elif mode == 'set' and qty >= 0:
                diff = qty - item.stock
                item.stock = qty
                action_name = "庫存盤點調整"
                log_qty = diff
            else:
                flash("數量設定有誤！", "danger")
                return redirect(url_for('admin'))

            new_log = Log(
                operator=f"管理員 ({admin_user})",
                box_name=item.box.name,
                mitac_pn=item.mitac_pn,
                item_name=item.name,
                quantity=log_qty,
                action_type=action_name,
                note="管理員後台維護"
            )
            db.session.add(new_log)
            db.session.commit()
            flash(f"【{item.name}】庫存更新成功！目前庫存：{item.stock}", "success")

        # 2. 編輯設備 (修改名稱、PN、規格、照片)
        elif action == 'edit_item':
            item_id = request.form.get('item_id', type=int)
            item = Item.query.get_or_404(item_id)

            item.box_id = request.form.get('box_id', type=int)
            item.mitac_pn = request.form.get('mitac_pn', '').strip()
            item.name = request.form.get('name', '').strip()
            item.description = request.form.get('description', '').strip()
            item.stock = request.form.get('stock', type=int, default=item.stock)

            image_file = request.files.get('image')
            if image_file and image_file.filename != '':
                if allowed_file(image_file.filename):
                    ext = secure_filename(image_file.filename).rsplit('.', 1)[1].lower()
                    filename = f"{uuid.uuid4().hex}.{ext}"
                    image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    item.image_filename = filename
                else:
                    flash("僅允許上傳圖片檔案 (PNG, JPG, JPEG, GIF, WEBP)！", "danger")
                    return redirect(url_for('admin'))

            db.session.commit()
            flash(f"設備【{item.name}】資料與照片更新成功！", "success")

        # 3. 建立備品箱
        elif action == 'add_box':
            box_code = request.form.get('box_code', '').strip().upper()
            name = request.form.get('name', '').strip()
            location = request.form.get('location', '').strip()
            desc = request.form.get('description', '').strip()
            if not box_code or not name:
                flash("Project Code 與 Name 不可為空！", "danger")
            elif not Box.query.filter_by(box_code=box_code).first():
                new_box = Box(box_code=box_code, name=name, location=location, description=desc)
                db.session.add(new_box)
                db.session.commit()
                flash(f"成功新增備品箱：{name} ({box_code})", "success")
            else:
                flash(f"箱號 {box_code} 已存在！", "danger")

        # 4. 編輯備品箱
        elif action == 'edit_box':
            box_id = request.form.get('box_id', type=int)
            box = Box.query.get_or_404(box_id)
            new_code = request.form.get('box_code', '').strip().upper()

            existing_box = Box.query.filter_by(box_code=new_code).first()
            if existing_box and existing_box.id != box.id:
                flash(f"Project Code【{new_code}】已被其他備品箱使用！", "danger")
                return redirect(url_for('admin'))

            box.box_code = new_code
            box.name = request.form.get('name', '').strip()
            box.location = request.form.get('location', '').strip()
            box.description = request.form.get('description', '').strip()
            db.session.commit()
            flash(f"備品箱【{box.name}】資訊已更新！", "success")

        # 5. 刪除備品箱
        elif action == 'delete_box':
            box_id = request.form.get('box_id', type=int)
            box = Box.query.get_or_404(box_id)
            box_name = box.name
            db.session.delete(box)
            db.session.commit()
            flash(f"備品箱【{box_name}】及其所有設備已刪除！", "warning")

        # 6. 新增設備
        elif action == 'add_item':
            box_id = request.form.get('box_id', type=int)
            mitac_pn = request.form.get('mitac_pn', '').strip()
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            stock = request.form.get('stock', type=int, default=0)

            image_file = request.files.get('image')
            filename = ""
            if image_file and image_file.filename != '':
                if allowed_file(image_file.filename):
                    ext = secure_filename(image_file.filename).rsplit('.', 1)[1].lower()
                    filename = f"{uuid.uuid4().hex}.{ext}"
                    image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                else:
                    flash("僅允許上傳圖片檔案 (PNG, JPG, JPEG, GIF, WEBP)！", "danger")
                    return redirect(url_for('admin'))

            new_item = Item(
                box_id=box_id,
                mitac_pn=mitac_pn,
                name=name,
                description=description,
                stock=stock,
                image_filename=filename
            )
            db.session.add(new_item)
            db.session.commit()
            flash(f"已新增備品：{name} (Mitac PN: {mitac_pn})", "success")

        # 7. 刪除設備
        elif action == 'delete_item':
            item_id = request.form.get('item_id', type=int)
            item = Item.query.get_or_404(item_id)
            item_name = item.name
            db.session.delete(item)
            db.session.commit()
            flash(f"備品【{item_name}】已成功刪除！", "warning")

        return redirect(url_for('admin'))

    boxes = Box.query.all()
    tunnel_url = get_current_tunnel_url()
    return render_template('admin.html', boxes=boxes, tunnel_url=tunnel_url)

# ----------------- 資料庫模型 (在 Log 模型下方加入 Loan) -----------------
class Loan(db.Model):
    __tablename__ = 'loans'
    id = db.Column(db.Integer, primary_key=True)
    device_name = db.Column(db.String(100), nullable=False)          # 設備
    project_name = db.Column(db.String(100), default="")             # 專案名稱
    mitac_pn = db.Column(db.String(100), default="")                 # Mitac P/N
    serial_number = db.Column(db.String(100), default="")            # 序號 (SN)
    status = db.Column(db.String(50), default="已借出")              # 當前狀態 (已借出 / 已歸還)
    location = db.Column(db.String(100), default="")                 # 存放位置
    borrower = db.Column(db.String(100), nullable=False)             # 借用人
    borrower_email = db.Column(db.String(120), default="")           # 借用人信箱
    borrow_date = db.Column(db.String(50), nullable=False)           # 借出日期 (YYYY-MM-DD)
    expected_return_date = db.Column(db.String(50), default="")      # 預計歸還日期 (YYYY-MM-DD)
    actual_return_date = db.Column(db.String(50), default="")        # 實際歸還日期 (YYYY-MM-DD)
    note = db.Column(db.Text, default="")                            # 備註
    created_at = db.Column(db.DateTime, default=datetime.now)

# ----------------- 設備借用表 路由功能 -----------------
@app.route('/loans', methods=['GET'])
def loans():
    status_filter = request.args.get('status', 'ALL')
    loan_records = Loan.query.order_by(Loan.id.desc()).all()
    today_str = datetime.now().strftime('%Y-%m-%d')
    projects = sorted({loan.project_name for loan in loan_records if loan.project_name})
    return render_template(
        'loans.html', loans=loan_records, today=today_str,
        current_status=status_filter, projects=projects,
    )


@app.route('/loans/export')
def export_loans():
    today = datetime.now().strftime('%Y-%m-%d')
    loan_records = Loan.query.order_by(Loan.id.desc()).yield_per(500)
    rows = (
        tuple(
            excel_date(getattr(loan, name)) if name.endswith('_date')
            else getattr(loan, name)
            for name, *_ in LOAN_COLUMNS
        )
        for loan in loan_records if matches_loan(loan, request.args, today)
    )
    output = create_workbook('Equipment loans', LOAN_COLUMNS, rows, request.args.get('lang'))
    response = send_file(
        output, as_attachment=True,
        download_name=f"equipment-loans-{datetime.now():%Y%m%d}.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@app.route('/loans/return/<int:loan_id>', methods=['POST'])
def return_loan(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    if loan.status == '已歸還':
        flash('此設備已完成歸還。', 'info')
        return redirect(url_for('loans'))
    if loan.status != '已借出':
        flash('目前狀態無法直接歸還，請開啟編輯確認。', 'danger')
        return redirect(url_for('loans'))
    returned_on = request.form.get('actual_return_date', '').strip()
    try:
        returned_date = datetime.strptime(returned_on, '%Y-%m-%d').date()
        borrowed_date = datetime.strptime(loan.borrow_date, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        flash('請確認借出及歸還日期格式。', 'danger')
        return redirect(url_for('loans'))
    if returned_date < borrowed_date:
        flash('歸還日期不可早於借出日期。', 'danger')
        return redirect(url_for('loans'))
    updated = Loan.query.filter_by(id=loan_id, status='已借出').update(
        {'status': '已歸還', 'actual_return_date': returned_date.isoformat()},
        synchronize_session=False,
    )
    db.session.commit()
    if updated:
        flash(f'【{loan.device_name}】已完成歸還。', 'success')
    else:
        flash('此筆紀錄的狀態已更新，請重新確認。', 'info')
    return redirect(url_for('loans'))

@app.route('/loans/add', methods=['POST'])
def add_loan():
    device_name = request.form.get('device_name', '').strip()
    project_name = request.form.get('project_name', '').strip()
    mitac_pn = request.form.get('mitac_pn', '').strip()
    serial_number = request.form.get('serial_number', '').strip()
    location = request.form.get('location', '').strip()
    borrower = request.form.get('borrower', '').strip()
    borrower_email = request.form.get('borrower_email', '').strip()
    borrow_date = request.form.get('borrow_date', '').strip() or datetime.now().strftime('%Y-%m-%d')
    expected_return_date = request.form.get('expected_return_date', '').strip()
    note = request.form.get('note', '').strip()

    if not device_name or not borrower:
        flash("「設備名稱」與「借用人」為必填欄位！ / Device Name and Borrower are required!", "danger")
        return redirect(url_for('loans'))

    new_loan = Loan(
        device_name=device_name,
        project_name=project_name,
        mitac_pn=mitac_pn,
        serial_number=serial_number,
        status="已借出",
        location=location,
        borrower=borrower,
        borrower_email=borrower_email,
        borrow_date=borrow_date,
        expected_return_date=expected_return_date,
        actual_return_date="",
        note=note
    )
    db.session.add(new_loan)
    db.session.commit()
    flash(f"已成功登記借出設備【{device_name}】！", "success")
    return redirect(url_for('loans'))

@app.route('/loans/update/<int:loan_id>', methods=['POST'])
def update_loan(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    is_admin = session.get('is_admin', False)

    # 一般使用者可修改的欄位：狀態、借出日期、預計歸還日期、實際歸還日期、備註
    new_status = request.form.get('status', loan.status).strip()
    loan.status = new_status
    loan.borrow_date = request.form.get('borrow_date', loan.borrow_date).strip()
    loan.expected_return_date = request.form.get('expected_return_date', loan.expected_return_date).strip()
    loan.actual_return_date = request.form.get('actual_return_date', loan.actual_return_date).strip()
    loan.note = request.form.get('note', loan.note).strip()

    # 自動帶入歸還日期：若狀態切換為已歸還且實際歸還日期為空，自動補上今日
    if loan.status == "已歸還" and not loan.actual_return_date:
        loan.actual_return_date = datetime.now().strftime('%Y-%m-%d')

    # 管理員額外可修改所有欄位
    if is_admin:
        loan.device_name = request.form.get('device_name', loan.device_name).strip()
        loan.project_name = request.form.get('project_name', loan.project_name).strip()
        loan.mitac_pn = request.form.get('mitac_pn', loan.mitac_pn).strip()
        loan.serial_number = request.form.get('serial_number', loan.serial_number).strip()
        loan.location = request.form.get('location', loan.location).strip()
        loan.borrower = request.form.get('borrower', loan.borrower).strip()
        loan.borrower_email = request.form.get('borrower_email', loan.borrower_email).strip()

    db.session.commit()
    flash(f"【{loan.device_name}】借用資料已更新！", "success")
    return redirect(url_for('loans'))

@app.route('/loans/delete/<int:loan_id>', methods=['POST'])
@admin_required
def delete_loan(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    dev_name = loan.device_name
    db.session.delete(loan)
    db.session.commit()
    flash(f"已刪除【{dev_name}】的借用紀錄！", "warning")
    return redirect(url_for('loans'))

# ----------------- QR Code 動態產生 (自動結合 Cloudflare 網址) -----------------
@app.route('/qrcode/<string:box_code>')
def generate_qrcode(box_code):
    # 優先嘗試從 tunnel.log 抓取當前穿透網址
    tunnel_url = get_current_tunnel_url()

    if tunnel_url:
        base_url = tunnel_url
    else:
        # 如果沒開穿透，則退回使用目前連線的網址 (例如 http://127.0.0.1:5000)
        base_url = request.host_url.rstrip('/')

    url = f"{base_url}/box/{box_code}"

    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

# ----------------- 啟動伺服器 -----------------
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
