# config.py
import os

class Config:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-in-production')
    UPLOAD_FOLDER = 'uploads'
    REPORT_FOLDER = 'reports'
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB（單批次總大小）
    
    # 批量操作限制
    MAX_BATCH_FILES = 5                     # ✅ 批量上限：5份PDF
    MAX_SINGLE_FILE_SIZE = 10 * 1024 * 1024 # 單文件最大10MB
    
    # Celery
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    
    # 管理員
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
    
    # 白名單
    WHITELIST_FILE = 'whitelist.json'
    
    # 簽名模式
    DEFAULT_SIGNER_MODE = os.environ.get('SIGNER_MODE', 'auto')