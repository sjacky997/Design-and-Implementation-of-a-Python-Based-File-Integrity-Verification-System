# app.py
import os
import json
import uuid
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import (
    Flask, request, render_template, redirect, url_for,
    flash, send_file, session, jsonify
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config
from task_manager import task_manager
from core.core import load_whitelist


# ==================== 審計日誌 ====================
logging.basicConfig(
    filename='auth.log',
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
auth_logger = logging.getLogger('auth')


# ==================== Flask 應用 ====================
app = Flask(__name__)
app.config.from_object(Config)

app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'change-this-in-production-xyz123'),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=["200 per day", "50 per hour"]
)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf'}
MAX_BATCH_FILES = app.config['MAX_BATCH_FILES']

# 三個層級的密碼
PORTAL_PASSWORD_HASH = generate_password_hash(
    os.environ.get('PORTAL_PASSWORD', 'portal123'),
    method='pbkdf2:sha256'
)
VERIFY_PASSWORD_HASH = generate_password_hash(
    os.environ.get('VERIFY_PASSWORD', 'verify123'),
    method='pbkdf2:sha256'
)


# ==================== 任務函數 ====================

def process_register(pdf_path, contract_no, admin_id, original_filename):
    try:
        if not os.path.exists(pdf_path):
            return {'status': 'failed', 'contract_no': contract_no, 'reason': '文件不存在'}

        from core.sm3_utils import compute_sm3_from_file_chunked
        pdf_hash = compute_sm3_from_file_chunked(pdf_path)

        timestamp = datetime.now().isoformat()
        record = {
            'contract_no': contract_no,
            'pdf_hash': pdf_hash,
            'timestamp': timestamp,
            'admin_id': admin_id,
            'original_filename': original_filename
        }

        from core.signer_factory import get_signer
        signer = get_signer(mode='server')
        record_json = json.dumps(record, sort_keys=True)
        signature = signer.sign(record_json.encode('utf-8'))

        entry = {'record': record, 'signature': signature}
        _append_to_whitelist_atomic(entry)

        return {
            'status': 'success',
            'contract_no': contract_no,
            'pdf_hash': pdf_hash,
            'signature': signature,
            'timestamp': timestamp
        }
    except Exception as e:
        return {
            'status': 'failed',
            'contract_no': contract_no,
            'reason': f'{type(e).__name__}: {str(e)}'
        }


def process_verify(pdf_path, whitelist_path, signer_mode='server',
                   private_key_hex=None, original_filename=None):
    try:
        from core.sm3_utils import compute_sm3_from_file_chunked
        from core.signer_factory import get_signer
        from core.report_signer import ReportSigner

        signer = get_signer(mode=signer_mode, private_key_hex=private_key_hex)
        actual_hash = compute_sm3_from_file_chunked(pdf_path)

        whitelist = load_whitelist(whitelist_path)
        pdf_name = original_filename or os.path.basename(pdf_path)
        expected_hash = whitelist.get(pdf_name, "0" * 64)

        report_signer = ReportSigner(signer)
        report, signature = report_signer.full_process(
            pdf_name, expected_hash, actual_hash
        )

        report_filename = f'{os.path.splitext(pdf_name)[0]}_report.json'
        report_path = os.path.join(Config.REPORT_FOLDER, report_filename)
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return {
            'status': report['status'],
            'pdf_file': pdf_name,
            'expected_hash': expected_hash,
            'actual_hash': actual_hash,
            'signature_of_report': signature,
            'timestamp': report['timestamp'],
            'report_filename': report_filename
        }
    except Exception as e:
        return {
            'status': 'failed',
            'pdf_file': original_filename or os.path.basename(pdf_path),
            'reason': f'{type(e).__name__}: {str(e)}'
        }


def _append_to_whitelist_atomic(entry):
    from filelock import FileLock

    lock_path = Config.WHITELIST_FILE + '.lock'

    with FileLock(lock_path):
        if os.path.exists(Config.WHITELIST_FILE):
            with open(Config.WHITELIST_FILE, 'r', encoding='utf-8') as f:
                whitelist = json.load(f)
        else:
            whitelist = []

        contract_no = entry['record']['contract_no']
        for i, existing in enumerate(whitelist):
            if existing.get('record', {}).get('contract_no') == contract_no:
                whitelist[i] = entry
                break
        else:
            whitelist.append(entry)

        temp_path = Config.WHITELIST_FILE + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(whitelist, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, Config.WHITELIST_FILE)


# ==================== 輔助函數 ====================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_pdf(filepath):
    try:
        with open(filepath, 'rb') as f:
            header = f.read(5)
        if header != b'%PDF-':
            return False
        if os.path.getsize(filepath) > app.config['MAX_SINGLE_FILE_SIZE']:
            return False
        import fitz
        doc = fitz.open(filepath)
        doc.close()
        return True
    except Exception:
        return False


def save_upload_file(file, prefix=''):
    original_filename = secure_filename(file.filename)
    unique_name = f'{prefix}{uuid.uuid4().hex}_{original_filename}'
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
    file.save(filepath)
    return filepath, original_filename


# ==================== 權限裝飾器 ====================

def portal_required(f):
    """第一層：系統訪問權限"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('portal_logged_in'):
            flash('請先登錄系統', 'error')
            return redirect(url_for('portal_login'))
        return f(*args, **kwargs)
    return wrapper


def login_required(f):
    """第二層：驗證功能權限"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('portal_logged_in'):
            flash('請先登錄系統', 'error')
            return redirect(url_for('portal_login'))
        if not session.get('logged_in'):
            flash('請先登錄驗證功能', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    """第二層：管理員功能權限"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('portal_logged_in'):
            flash('請先登錄系統', 'error')
            return redirect(url_for('portal_login'))
        if not session.get('is_admin'):
            flash('請先登錄管理員賬戶', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return wrapper


# ==================== 第一層：系統入口登錄 ====================

@app.route('/', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def portal_login():
    """第一層登錄：系統訪問入口"""
    if session.get('portal_logged_in'):
        return redirect(url_for('portal'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        client_ip = request.remote_addr

        if check_password_hash(PORTAL_PASSWORD_HASH, password):
            session.clear()
            session['portal_logged_in'] = True
            session['portal_login_time'] = datetime.now().isoformat()
            session.permanent = True

            auth_logger.info(f"PORTAL LOGIN SUCCESS ip={client_ip}")
            flash('系統登錄成功', 'success')
            return redirect(url_for('portal'))
        else:
            auth_logger.warning(f"PORTAL LOGIN FAILED ip={client_ip}")
            flash('訪問密碼錯誤', 'error')

    return render_template('portal_login.html')


@app.route('/portal/logout')
def portal_logout():
    """完全登出（清除所有身份）"""
    client_ip = request.remote_addr
    session.clear()
    auth_logger.info(f"PORTAL LOGOUT ip={client_ip}")
    flash('已完全登出', 'success')
    return redirect(url_for('portal_login'))

@app.route('/force_portal_logout')
def force_portal_logout():
    """
    強制登出系統入口
    用於：用戶關閉 /portal 分頁後重新打開，sessionStorage 已清空的情況
    """
    session.clear()
    auth_logger.info(f"PORTAL FORCE LOGOUT (new tab detected) ip={request.remote_addr}")
    flash('檢測到新分頁，請重新登錄系統', 'error')
    return redirect(url_for('portal_login'))


# ==================== 選擇頁 ====================

@app.route('/portal')
@portal_required
def portal():
    """功能選擇頁"""
    return render_template('portal.html')


# ==================== 第二層：驗證功能登錄 ====================

@app.route('/login', methods=['GET', 'POST'])
@portal_required
@limiter.limit("5 per minute")
def login():
    """第二層登錄：驗證功能"""
    if session.get('logged_in'):
        return redirect(url_for('verify'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        client_ip = request.remote_addr

        if check_password_hash(VERIFY_PASSWORD_HASH, password):
            session['logged_in'] = True
            session['verify_login_time'] = datetime.now().isoformat()
            session.pop('is_admin', None)

            auth_logger.info(f"VERIFY LOGIN SUCCESS ip={client_ip}")
            flash('驗證功能登錄成功', 'success')
            return redirect(url_for('verify'))
        else:
            auth_logger.warning(f"VERIFY LOGIN FAILED ip={client_ip}")
            flash('驗證密碼錯誤', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """驗證功能登出（保留系統登錄）"""
    session.pop('logged_in', None)
    session.pop('verify_login_time', None)
    auth_logger.info(f"VERIFY LOGOUT ip={request.remote_addr}")
    flash('已登出驗證功能', 'success')
    return redirect(url_for('portal'))


# 🆕 強制登出驗證功能（用於關閉分頁後重新打開的場景）
@app.route('/force_logout')
def force_logout():
    """
    強制登出驗證功能
    用於：用戶關閉分頁後重新打開，sessionStorage 已清空的情況
    """
    session.pop('logged_in', None)
    session.pop('verify_login_time', None)
    auth_logger.info(f"VERIFY FORCE LOGOUT (new tab detected) ip={request.remote_addr}")
    flash('檢測到新分頁，請重新登錄驗證功能', 'error')
    return redirect(url_for('portal'))


# ==================== 驗證功能頁面 ====================

@app.route('/verify')
@login_required
def verify():
    """驗證功能首頁"""
    server_signer_ready = (
        os.path.exists('encrypted_private.bin') and
        os.path.exists('keyfile.key')
    )
    return render_template('index.html',
                           server_signer_ready=server_signer_ready,
                           max_batch=MAX_BATCH_FILES)


@app.route('/batch_verify', methods=['POST'])
@login_required
def batch_verify():
    files = request.files.getlist('pdf_files')
    signer_mode = request.form.get('signer_mode', 'server')
    private_key = request.form.get('private_key', '').strip()

    if not files or files[0].filename == '':
        flash('請至少上傳一個 PDF 文件', 'error')
        return redirect(url_for('verify'))

    if len(files) > MAX_BATCH_FILES:
        flash(f'單批次最多支持 {MAX_BATCH_FILES} 個文件', 'error')
        return redirect(url_for('verify'))

    if signer_mode == 'manual':
        if not private_key or len(private_key) != 64:
            flash('手動模式需要有效的64位私鑰', 'error')
            return redirect(url_for('verify'))

    whitelist_file = request.files.get('whitelist_file')
    if whitelist_file and whitelist_file.filename:
        whitelist_path, _ = save_upload_file(whitelist_file, prefix='wl_')
    else:
        whitelist_path = app.config['WHITELIST_FILE']
        if not os.path.exists(whitelist_path):
            flash('系統白名單不存在', 'error')
            return redirect(url_for('verify'))

    task_ids = []
    file_info = []

    for pdf_file in files:
        if not allowed_file(pdf_file.filename):
            flash(f'文件 {pdf_file.filename} 格式不正確', 'error')
            return redirect(url_for('verify'))

        pdf_path, original_filename = save_upload_file(pdf_file, prefix='verify_')

        if not validate_pdf(pdf_path):
            flash(f'文件 {pdf_file.filename} 不是有效 PDF', 'error')
            return redirect(url_for('verify'))

        task_id = task_manager.submit(
            process_verify,
            pdf_path,
            whitelist_path,
            signer_mode,
            private_key if signer_mode == 'manual' else None,
            original_filename
        )
        task_ids.append(task_id)
        file_info.append({
            'task_id': task_id,
            'filename': original_filename,
            'path': pdf_path
        })

    return render_template('batch_progress.html',
                           task_ids=task_ids,
                           file_info=file_info,
                           operation='verify')


# ==================== 第二層：管理員功能登錄 ====================

@app.route('/admin/login', methods=['GET', 'POST'])
@portal_required
@limiter.limit("5 per minute")
def admin_login():
    """第二層登錄：管理員功能"""
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        if request.form.get('password', '') == app.config['ADMIN_PASSWORD']:
            session['is_admin'] = True
            session['admin_login_time'] = datetime.now().isoformat()
            session.pop('logged_in', None)

            auth_logger.info(f"ADMIN LOGIN SUCCESS ip={request.remote_addr}")
            flash('管理員登錄成功', 'success')
            return redirect(url_for('admin_dashboard'))
        auth_logger.warning(f"ADMIN LOGIN FAILED ip={request.remote_addr}")
        flash('管理員密碼錯誤', 'error')
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    """管理員登出（保留系統登錄）"""
    session.pop('is_admin', None)
    session.pop('admin_login_time', None)
    auth_logger.info(f"ADMIN LOGOUT ip={request.remote_addr}")
    flash('已登出管理員賬戶', 'success')
    return redirect(url_for('portal'))


# 🆕 強制登出管理員功能（用於關閉分頁後重新打開的場景）
@app.route('/force_admin_logout')
def force_admin_logout():
    """
    強制登出管理員功能
    用於：用戶關閉分頁後重新打開，sessionStorage 已清空的情況
    """
    session.pop('is_admin', None)
    session.pop('admin_login_time', None)
    auth_logger.info(f"ADMIN FORCE LOGOUT (new tab detected) ip={request.remote_addr}")
    flash('檢測到新分頁，請重新登錄管理員賬戶', 'error')
    return redirect(url_for('portal'))


# ==================== 管理員功能頁面 ====================

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    whitelist = []
    if os.path.exists(app.config['WHITELIST_FILE']):
        with open(app.config['WHITELIST_FILE'], 'r', encoding='utf-8') as f:
            whitelist = json.load(f)

    records = []
    for entry in whitelist:
        rec = entry.get('record', {})
        records.append({
            'contract_no': rec.get('contract_no', ''),
            'pdf_hash': rec.get('pdf_hash', ''),
            'original_filename': rec.get('original_filename', ''),
            'timestamp': rec.get('timestamp', ''),
            'admin_id': rec.get('admin_id', '')
        })

    return render_template('admin_dashboard.html',
                           records=records,
                           total=len(records),
                           max_batch=MAX_BATCH_FILES)


@app.route('/admin/batch_register', methods=['POST'])
@admin_required
def admin_batch_register():
    files = request.files.getlist('pdf_files')
    contract_nos = request.form.getlist('contract_nos')
    admin_id = session.get('admin_id', 'admin001')

    if not files or files[0].filename == '':
        flash('請至少上傳一個 PDF 文件', 'error')
        return redirect(url_for('admin_dashboard'))

    if len(files) > MAX_BATCH_FILES:
        flash(f'單批次最多支持 {MAX_BATCH_FILES} 個文件', 'error')
        return redirect(url_for('admin_dashboard'))

    if len(contract_nos) != len(files):
        flash('合同編號數量與文件數量不匹配', 'error')
        return redirect(url_for('admin_dashboard'))

    task_ids = []
    file_info = []

    for pdf_file, contract_no in zip(files, contract_nos):
        contract_no = contract_no.strip()
        if not contract_no:
            flash('合同編號不能為空', 'error')
            return redirect(url_for('admin_dashboard'))

        if not allowed_file(pdf_file.filename):
            flash(f'文件 {pdf_file.filename} 格式不正確', 'error')
            return redirect(url_for('admin_dashboard'))

        pdf_path, original_filename = save_upload_file(pdf_file, prefix='register_')

        if not validate_pdf(pdf_path):
            flash(f'文件 {pdf_file.filename} 不是有效 PDF', 'error')
            return redirect(url_for('admin_dashboard'))

        task_id = task_manager.submit(
            process_register,
            pdf_path,
            contract_no,
            admin_id,
            original_filename
        )
        task_ids.append(task_id)
        file_info.append({
            'task_id': task_id,
            'filename': original_filename,
            'contract_no': contract_no,
            'path': pdf_path
        })

    return render_template('batch_progress.html',
                           task_ids=task_ids,
                           file_info=file_info,
                           operation='register')


@app.route('/admin/register', methods=['POST'])
@admin_required
def admin_register():
    pdf_file = request.files.get('pdf_file')
    contract_no = request.form.get('contract_no', '').strip()
    admin_id = request.form.get('admin_id', 'admin001')

    if not pdf_file or not contract_no:
        flash('請上傳 PDF 並填寫合同編號', 'error')
        return redirect(url_for('admin_dashboard'))

    pdf_path, original_filename = save_upload_file(pdf_file, prefix='register_')

    if not validate_pdf(pdf_path):
        flash('無效 PDF', 'error')
        return redirect(url_for('admin_dashboard'))

    result = process_register(pdf_path, contract_no, admin_id, original_filename)

    if result['status'] == 'success':
        flash(f'合同 {contract_no} 錄入成功', 'success')
    else:
        flash(f'錄入失敗：{result.get("reason")}', 'error')

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete/<contract_no>', methods=['POST'])
@admin_required
def admin_delete(contract_no):
    if not os.path.exists(app.config['WHITELIST_FILE']):
        flash('白名單為空', 'error')
        return redirect(url_for('admin_dashboard'))

    with open(app.config['WHITELIST_FILE'], 'r', encoding='utf-8') as f:
        whitelist = json.load(f)

    original_len = len(whitelist)
    whitelist = [e for e in whitelist
                 if e.get('record', {}).get('contract_no') != contract_no]

    if len(whitelist) == original_len:
        flash(f'未找到合同: {contract_no}', 'error')
    else:
        with open(app.config['WHITELIST_FILE'], 'w', encoding='utf-8') as f:
            json.dump(whitelist, f, indent=2, ensure_ascii=False)
        flash(f'已刪除: {contract_no}', 'success')

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/download_whitelist')
@admin_required
def admin_download_whitelist():
    if not os.path.exists(app.config['WHITELIST_FILE']):
        flash('白名單文件不存在', 'error')
        return redirect(url_for('admin_dashboard'))
    return send_file(app.config['WHITELIST_FILE'], as_attachment=True)


# ==================== 任務狀態 API ====================

@app.route('/api/task_status/<task_id>')
@login_required
def task_status(task_id):
    return jsonify(task_manager.get_status(task_id))


@app.route('/api/batch_status', methods=['POST'])
@login_required
def batch_status():
    task_ids = request.json.get('task_ids', [])
    results = [task_manager.get_status(tid) for tid in task_ids]
    return jsonify({'tasks': results})


# ==================== 批量結果頁 ====================

@app.route('/batch_result_page')
@login_required
def batch_result_page():
    return render_template('batch_result.html')


# ==================== 報告下載 ====================

@app.route('/download/<filename>')
@login_required
def download_report(filename):
    filename = secure_filename(filename)
    filepath = os.path.join(app.config['REPORT_FOLDER'], filename)

    if not os.path.exists(filepath):
        flash('報告不存在', 'error')
        return redirect(url_for('verify'))

    return send_file(filepath, as_attachment=True)


# ==================== 啟動 ====================

if __name__ == '__main__':
    server_ready = (
        os.path.exists('encrypted_private.bin') and
        os.path.exists('keyfile.key')
    )
    print('=' * 60)
    print('三層登錄架構已啟動')
    print('-' * 60)
    print(f'第一層（系統入口）密碼: {os.environ.get("PORTAL_PASSWORD", "portal123")}')
    print(f'第二層（驗證功能）密碼: {os.environ.get("VERIFY_PASSWORD", "verify123")}')
    print(f'第二層（管理員功能）密碼: {app.config["ADMIN_PASSWORD"]}')
    print('-' * 60)
    print(f'批量上限: {MAX_BATCH_FILES} 個文件')
    print(f'簽名模式: {"服務器端已就緒" if server_ready else "需手動輸入私鑰"}')
    print(f'任務處理: ThreadPoolExecutor (4 線程)')
    print('=' * 60)
    app.run(debug=False, host='0.0.0.0', port=5001)