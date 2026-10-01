# app.py
import os
import json
import uuid
from datetime import datetime
from functools import wraps
from flask import (
    Flask, request, render_template, redirect, url_for,
    flash, send_file, session, jsonify
)
from werkzeug.utils import secure_filename

from config import Config
from task_manager import task_manager
from core.core import load_whitelist


app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf'}
MAX_BATCH_FILES = app.config['MAX_BATCH_FILES']


# ==================== 任務函數 ====================

def process_register(pdf_path, contract_no, admin_id, original_filename):
    """
    單個文件的錄入任務
    
    參數：
    - pdf_path: 上傳文件的實際存儲路徑（含 UUID 前綴）
    - contract_no: 合同編號
    - admin_id: 管理員ID
    - original_filename: 原始文件名（不含 UUID 前綴，如 "contract_0.pdf"）
    """
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
            'original_filename': original_filename   # ← 存原始文件名（乾淨的名稱）
        }

        # 加載簽名器並簽名
        from core.signer_factory import get_signer
        signer = get_signer(mode='server')
        record_json = json.dumps(record, sort_keys=True)
        signature = signer.sign(record_json.encode('utf-8'))

        # 寫入白名單
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
    """
    單個文件的驗證任務
    
    參數：
    - pdf_path: 上傳文件的實際存儲路徑（含 UUID 前綴）
    - whitelist_path: 白名單路徑
    - signer_mode: 簽名模式
    - private_key_hex: 手動模式下的私鑰
    - original_filename: 原始文件名（不含 UUID 前綴，如 "contract_0.pdf"）
    """
    try:
        from core.sm3_utils import compute_sm3_from_file_chunked
        from core.signer_factory import get_signer
        from core.report_signer import ReportSigner

        signer = get_signer(mode=signer_mode, private_key_hex=private_key_hex)
        actual_hash = compute_sm3_from_file_chunked(pdf_path)

        whitelist = load_whitelist(whitelist_path)

        # 優先用原始文件名查找
        pdf_name = original_filename or os.path.basename(pdf_path)
        expected_hash = whitelist.get(pdf_name, "0" * 64)

        # 生成報告並簽名
        report_signer = ReportSigner(signer)
        report, signature = report_signer.full_process(
            pdf_name, expected_hash, actual_hash
        )

        # 保存報告
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
    """原子追加白名單記錄"""
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
    """驗證文件是否為 PDF"""
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
    """
    保存上傳文件
    
    返回：
    - (filepath, original_filename)
      - filepath: 實際存儲路徑（含 UUID 前綴，確保唯一性）
      - original_filename: 原始文件名（不含 UUID 前綴）
    """
    original_filename = secure_filename(file.filename)
    unique_name = f'{prefix}{uuid.uuid4().hex}_{original_filename}'
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
    file.save(filepath)
    return filepath, original_filename


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            flash('請先登入管理員賬戶', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return wrapper


# ==================== 用戶端 ====================

@app.route('/')
def index():
    server_signer_ready = (
        os.path.exists('encrypted_private.bin') and
        os.path.exists('keyfile.key')
    )
    return render_template('index.html',
                           server_signer_ready=server_signer_ready,
                           max_batch=MAX_BATCH_FILES)


@app.route('/batch_verify', methods=['POST'])
def batch_verify():
    files = request.files.getlist('pdf_files')
    signer_mode = request.form.get('signer_mode', 'server')
    private_key = request.form.get('private_key', '').strip()

    if not files or files[0].filename == '':
        flash('請至少上傳一個 PDF 文件', 'error')
        return redirect(url_for('index'))

    if len(files) > MAX_BATCH_FILES:
        flash(f'單批次最多支持 {MAX_BATCH_FILES} 個文件', 'error')
        return redirect(url_for('index'))

    if signer_mode == 'manual':
        if not private_key or len(private_key) != 64:
            flash('手動模式需要有效的64位私鑰', 'error')
            return redirect(url_for('index'))

    # 白名單
    whitelist_file = request.files.get('whitelist_file')
    if whitelist_file and whitelist_file.filename:
        whitelist_path, _ = save_upload_file(whitelist_file, prefix='wl_')
    else:
        whitelist_path = app.config['WHITELIST_FILE']
        if not os.path.exists(whitelist_path):
            flash('系統白名單不存在', 'error')
            return redirect(url_for('index'))

    # 提交任務
    task_ids = []
    file_info = []

    for pdf_file in files:
        if not allowed_file(pdf_file.filename):
            flash(f'文件 {pdf_file.filename} 格式不正確', 'error')
            return redirect(url_for('index'))

        # ✅ 獲取 (filepath, original_filename)
        pdf_path, original_filename = save_upload_file(pdf_file, prefix='verify_')

        if not validate_pdf(pdf_path):
            flash(f'文件 {pdf_file.filename} 不是有效 PDF', 'error')
            return redirect(url_for('index'))

        # ✅ 傳入原始文件名
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


# ==================== 管理員端 ====================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password', '') == app.config['ADMIN_PASSWORD']:
            session['is_admin'] = True
            return redirect(url_for('admin_dashboard'))
        flash('密碼錯誤', 'error')
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))


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

        # ✅ 獲取 (filepath, original_filename)
        pdf_path, original_filename = save_upload_file(pdf_file, prefix='register_')

        if not validate_pdf(pdf_path):
            flash(f'文件 {pdf_file.filename} 不是有效 PDF', 'error')
            return redirect(url_for('admin_dashboard'))

        # ✅ 傳入原始文件名
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
    """單文件錄入（同步）"""
    pdf_file = request.files.get('pdf_file')
    contract_no = request.form.get('contract_no', '').strip()
    admin_id = request.form.get('admin_id', 'admin001')

    if not pdf_file or not contract_no:
        flash('請上傳 PDF 並填寫合同編號', 'error')
        return redirect(url_for('admin_dashboard'))

    # ✅ 獲取 (filepath, original_filename)
    pdf_path, original_filename = save_upload_file(pdf_file, prefix='register_')

    if not validate_pdf(pdf_path):
        flash('無效 PDF', 'error')
        return redirect(url_for('admin_dashboard'))

    # ✅ 傳入原始文件名
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
def task_status(task_id):
    """查詢單個任務狀態"""
    return jsonify(task_manager.get_status(task_id))


@app.route('/api/batch_status', methods=['POST'])
def batch_status():
    """批量查詢任務狀態"""
    task_ids = request.json.get('task_ids', [])
    results = [task_manager.get_status(tid) for tid in task_ids]
    return jsonify({'tasks': results})


# ==================== 批量結果頁 ====================

@app.route('/batch_result_page')
def batch_result_page():
    return render_template('batch_result.html')


# ==================== 報告下載 ====================

@app.route('/download/<filename>')
def download_report(filename):
    filename = secure_filename(filename)
    filepath = os.path.join(app.config['REPORT_FOLDER'], filename)

    if not os.path.exists(filepath):
        flash('報告不存在', 'error')
        return redirect(url_for('index'))

    return send_file(filepath, as_attachment=True)


# ==================== 啟動 ====================

if __name__ == '__main__':
    server_ready = (
        os.path.exists('encrypted_private.bin') and
        os.path.exists('keyfile.key')
    )
    print('=' * 60)
    print(f'批量上限: {MAX_BATCH_FILES} 個文件')
    print(f'簽名模式: {"服務器端已就緒" if server_ready else "需手動輸入私鑰"}')
    print(f'任務處理: ThreadPoolExecutor (4 線程)')
    print('=' * 60)
    app.run(debug=False, host='0.0.0.0', port=5001)