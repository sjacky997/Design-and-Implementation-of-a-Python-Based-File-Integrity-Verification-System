import json
import os
from datetime import datetime
from .sm3_utils import compute_sm3_from_bytes
from .sm2_utils import SM2Helper

class ReportSigner:
    def __init__(self, sm2_helper: SM2Helper):
        self.sm2 = sm2_helper

    def generate_report(self, pdf_name: str, is_tampered: bool, expected_hash: str, actual_hash: str) -> dict:
        return {
            "timestamp": datetime.now().isoformat(),
            "pdf_file": pdf_name,
            "status": "tampered" if is_tampered else "clean",
            "expected_hash": expected_hash,
            "actual_hash": actual_hash,
            "signature_of_report": None
        }

    def sign_report(self, report_dict: dict) -> str:
        report_json = json.dumps(report_dict, sort_keys=True)
        return self.sm2.sign(report_json.encode('utf-8'))

    def full_process(self, pdf_name: str, expected_hash: str, actual_hash: str) -> tuple:
        is_tampered = (expected_hash != actual_hash)
        report = self.generate_report(pdf_name, is_tampered, expected_hash, actual_hash)
        sig = self.sign_report(report)
        report["signature_of_report"] = sig
        return report, sig