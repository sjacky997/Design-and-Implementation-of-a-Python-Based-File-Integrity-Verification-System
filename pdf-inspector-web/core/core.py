# core/core.py
import os
import json
from .sm3_utils import compute_sm3_from_file
from .signer_factory import get_signer
from .report_signer import ReportSigner


def load_whitelist(whitelist_path: str) -> dict:
    whitelist = {}
    if not os.path.exists(whitelist_path):
        return whitelist
    with open(whitelist_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for entry in data:
        record = entry.get("record", {})
        contract_no = record.get("contract_no", "")
        pdf_hash = record.get("pdf_hash", "")
        original_filename = record.get("original_filename", "")
        if contract_no and pdf_hash:
            whitelist[f"{contract_no}.pdf"] = pdf_hash
            whitelist[contract_no] = pdf_hash
            if original_filename:
                whitelist[original_filename] = pdf_hash
    return whitelist


def detect_and_sign(pdf_path, whitelist_path, private_key_hex=None, signer_mode="auto"):
    """
    核心检测函数（支持多种签名模式）
    """
    signer = get_signer(mode=signer_mode, private_key_hex=private_key_hex)

    actual_hash = compute_sm3_from_file(pdf_path)
    whitelist = load_whitelist(whitelist_path)
    pdf_name = os.path.basename(pdf_path)
    expected_hash = whitelist.get(pdf_name, "0" * 64)

    report_signer = ReportSigner(signer)
    report, sig = report_signer.full_process(pdf_name, expected_hash, actual_hash)
    return report, sig