#!/usr/bin/env python3
# generate_edge_cases.py
"""
批量生成 60 個 Edge Case 測試 PDF
"""

import os
import io
import fitz  # PyMuPDF
from PIL import Image


OUTPUT_DIR = "test_samples/edge_cases"


# ==================== 輔助函數 ====================

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def create_basic_pdf(output_path, title="測試文檔", content="這是一份測試 PDF 文件。"):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), title, fontsize=20, fontname="china-s")
    page.insert_text((60, 120), content, fontsize=12, fontname="china-s")
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    return output_path


def create_pdf_with_size(output_path, target_size_kb):
    """
    創建指定大小的 PDF
    
    策略：先建立基礎 PDF，如果大小不足，則追加填充頁面。
    每次追加後檢查實際文件大小，直到達到目標。
    """
    target_bytes = target_size_kb * 1024
    doc = fitz.open()
    
    # 添加首頁
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), f"目標大小: {target_size_kb} KB", fontsize=14, fontname="china-s")
    
    # 先保存一次看基礎大小
    doc.save(output_path, garbage=4, deflate=True)
    current_size = os.path.getsize(output_path)
    
    # 持續添加內容直到達到目標
    page_count = 1
    max_pages = 500  # 安全上限
    
    while current_size < target_bytes and page_count < max_pages:
        # 添加一頁大量文字
        page = doc.new_page(width=595, height=842)
        for i in range(50):
            page.insert_text(
                (40, 40 + i * 15),
                f"第 {page_count} 頁 - 內容行 {i} - " + "填充數據" * 20,
                fontsize=8,
                fontname="china-s",
            )
        page_count += 1
        
        # 每 5 頁檢查一次大小
        if page_count % 5 == 0:
            doc.save(output_path, garbage=4, deflate=True)
            current_size = os.path.getsize(output_path)
    
    # 最終保存
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    
    return output_path


def append_filler_to_reach_size(output_path, target_size_kb):
    """
    如果 PDF 本身達不到目標大小，則用二進制填充
    （注意：這會讓 PDF 損壞，僅用於測試超大文件場景）
    """
    target_bytes = target_size_kb * 1024
    current_size = os.path.getsize(output_path)
    
    if current_size >= target_bytes:
        return
    
    # 讀取現有內容
    with open(output_path, 'rb') as f:
        data = f.read()
    
    # 在 PDF 末尾（%%EOF 之前）追加註釋填充
    filler_size = target_bytes - current_size
    # PDF 註釋以 % 開頭
    filler = b'\n%' + b'A' * (filler_size - 3) + b'\n'
    
    # 寫入填充後的文件
    with open(output_path, 'wb') as f:
        f.write(data)
        f.write(filler)
    
    return output_path


# ==================== 一、檔案格式類 ====================

def generate_format_cases():
    print("\n📁 一、檔案格式類 (E-01 ~ E-08)")
    dir_path = ensure_dir(os.path.join(OUTPUT_DIR, "format"))

    # E-01: 空檔案
    with open(os.path.join(dir_path, "empty.pdf"), 'wb') as f:
        pass
    print("   ✅ E-01 empty.pdf")

    # E-02: 損壞的 PDF
    with open(os.path.join(dir_path, "corrupted.pdf"), 'wb') as f:
        f.write(b'%PDF-1.4\n')
        f.write(os.urandom(1024))
    print("   ✅ E-02 corrupted.pdf")

    # E-03: 被截斷的 PDF
    path = os.path.join(dir_path, "truncated.pdf")
    temp = os.path.join(dir_path, "_temp.pdf")
    create_basic_pdf(temp, "截斷測試", "這是一個完整的 PDF，稍後會被截斷。" * 20)
    with open(temp, 'rb') as f:
        full_data = f.read()
    with open(path, 'wb') as f:
        f.write(full_data[:len(full_data) // 2])
    os.remove(temp)
    print("   ✅ E-03 truncated.pdf")

    # E-04: 偽裝成 PDF 的文字檔
    with open(os.path.join(dir_path, "fake_pdf.pdf"), 'w', encoding='utf-8') as f:
        f.write("這不是 PDF。" * 20)
    print("   ✅ E-04 fake_pdf.pdf")

    # E-05: DOCX 魔數
    with open(os.path.join(dir_path, "fake_pdf.docx"), 'wb') as f:
        f.write(b'PK\x03\x04')
        f.write(os.urandom(512))
    print("   ✅ E-05 fake_pdf.docx")

    # E-06: JPEG 魔數
    with open(os.path.join(dir_path, "fake_pdf.jpg"), 'wb') as f:
        f.write(b'\xFF\xD8\xFF\xE0')
        f.write(os.urandom(512))
    print("   ✅ E-06 fake_pdf.jpg")

    # E-07: 僅含 PDF 標頭
    with open(os.path.join(dir_path, "only_header.pdf"), 'wb') as f:
        f.write(b'%PDF-1.4\n')
    print("   ✅ E-07 only_header.pdf")

    # E-08: 缺少 EOF
    path = os.path.join(dir_path, "no_eof.pdf")
    temp = os.path.join(dir_path, "_temp.pdf")
    create_basic_pdf(temp, "無 EOF", "沒有 %%EOF。")
    with open(temp, 'rb') as f:
        data = f.read()
    with open(path, 'wb') as f:
        f.write(data.replace(b'%%EOF', b''))
    os.remove(temp)
    print("   ✅ E-08 no_eof.pdf")


# ==================== 二、檔案大小類 ====================

def generate_size_cases():
    print("\n📁 二、檔案大小類 (E-09 ~ E-15)")
    dir_path = ensure_dir(os.path.join(OUTPUT_DIR, "size"))

    sizes = [
        ("tiny_1kb.pdf", 1),
        ("small_10kb.pdf", 10),
        ("medium_1mb.pdf", 1024),
        ("large_5mb.pdf", 5 * 1024),
        ("limit_10mb.pdf", 10 * 1024),
        ("over_10mb.pdf", 10 * 1024 + 100),
        ("huge_50mb.pdf", 50 * 1024),
    ]

    for idx, (filename, size_kb) in enumerate(sizes, start=9):
        path = os.path.join(dir_path, filename)
        print(f"   ⏳ E-{idx:02d} {filename} ({size_kb} KB)...", end=" ", flush=True)
        
        # 先用正常方式生成
        create_pdf_with_size(path, size_kb)
        actual_kb = os.path.getsize(path) / 1024
        
        # 如果還不夠大，用二進制填充（僅用於大文件測試場景）
        if actual_kb < size_kb * 0.95:
            append_filler_to_reach_size(path, size_kb)
            actual_kb = os.path.getsize(path) / 1024
        
        print(f"完成 ({actual_kb:.1f} KB)")


# ==================== 三、內容結構類 ====================

def generate_content_cases():
    print("\n📁 三、內容結構類 (E-16 ~ E-25)")
    dir_path = ensure_dir(os.path.join(OUTPUT_DIR, "content"))

    # E-16: 空白頁
    path = os.path.join(dir_path, "blank_page.pdf")
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print("   ✅ E-16 blank_page.pdf")

    # E-17: 僅一個字符
    path = os.path.join(dir_path, "single_char.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "A", fontsize=12)
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print("   ✅ E-17 single_char.pdf")

    # E-18: 100 頁
    path = os.path.join(dir_path, "multi_page_100.pdf")
    doc = fitz.open()
    for i in range(100):
        page = doc.new_page(width=595, height=842)
        page.insert_text((60, 80), f"第 {i + 1} 頁", fontsize=16, fontname="china-s")
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print("   ✅ E-18 multi_page_100.pdf")

    # E-19: 純圖片
    path = os.path.join(dir_path, "image_only.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    img = Image.new('RGB', (800, 600), color=(240, 240, 240))
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    page.insert_image(fitz.Rect(50, 50, 545, 400), stream=img_bytes.read())
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print("   ✅ E-19 image_only.pdf")

    # E-20: 純文本
    path = os.path.join(dir_path, "text_only.pdf")
    create_basic_pdf(path, "純文本 PDF", "這是一份純文本 PDF。" * 20)
    print("   ✅ E-20 text_only.pdf")

    # E-21: 表格
    path = os.path.join(dir_path, "table_heavy.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 60), "表格測試", fontsize=18, fontname="china-s")
    y = 100
    for row in range(20):
        for col in range(5):
            rect = fitz.Rect(60 + col * 95, y, 60 + (col + 1) * 95, y + 25)
            page.draw_rect(rect, color=(0, 0, 0), width=0.5)
            page.insert_text((65 + col * 95, y + 18), f"R{row}C{col}", fontsize=9)
        y += 25
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print("   ✅ E-21 table_heavy.pdf")

    # E-22: 特殊字體
    path = os.path.join(dir_path, "font_embedded.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "特殊字體測試", fontsize=20, fontname="china-s")
    page.insert_text((60, 120), "中文 日本語 한국어", fontsize=14, fontname="china-s")
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print("   ✅ E-22 font_embedded.pdf")

    # E-23: 無元數據
    path = os.path.join(dir_path, "no_metadata.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "無元數據", fontsize=16, fontname="china-s")
    doc.set_metadata({})
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print("   ✅ E-23 no_metadata.pdf")

    # E-24: 含元數據
    path = os.path.join(dir_path, "with_metadata.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "含元數據", fontsize=16, fontname="china-s")
    doc.set_metadata({
        "title": "測試合同",
        "author": "Test Author",
        "subject": "測試主題",
        "keywords": "PDF, 測試",
    })
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print("   ✅ E-24 with_metadata.pdf")

    # E-25: 僅元數據不同
    path = os.path.join(dir_path, "metadata_only_change.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "含元數據", fontsize=16, fontname="china-s")
    doc.set_metadata({
        "title": "修改後的標題",  # 只有這裡不同
        "author": "Test Author",
        "subject": "測試主題",
        "keywords": "PDF, 測試",
    })
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print("   ✅ E-25 metadata_only_change.pdf")


# ==================== 四、加密與權限類 ====================

def generate_encryption_cases():
    print("\n📁 四、加密與權限類 (E-26 ~ E-30)")
    dir_path = ensure_dir(os.path.join(OUTPUT_DIR, "encryption"))

    # E-26: 用戶密碼加密
    path = os.path.join(dir_path, "encrypted_user_pwd.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "加密 PDF", fontsize=16, fontname="china-s")
    perm = fitz.PDF_PERM_ACCESSIBILITY | fitz.PDF_PERM_PRINT
    doc.save(
        path,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw="user123",
        owner_pw="owner123",
        permissions=perm,
    )
    doc.close()
    print("   ✅ E-26 encrypted_user_pwd.pdf (用戶密碼: user123)")

    # E-27: 所有者密碼
    path = os.path.join(dir_path, "encrypted_owner_pwd.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "所有者密碼", fontsize=16, fontname="china-s")
    perm = fitz.PDF_PERM_ACCESSIBILITY | fitz.PDF_PERM_PRINT
    doc.save(
        path,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw="",
        owner_pw="owner456",
        permissions=perm,
    )
    doc.close()
    print("   ✅ E-27 encrypted_owner_pwd.pdf (所有者密碼: owner456)")

    # E-28: 只讀
    path = os.path.join(dir_path, "readonly.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "只讀", fontsize=16, fontname="china-s")
    perm = fitz.PDF_PERM_ACCESSIBILITY | fitz.PDF_PERM_PRINT
    doc.save(path, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="", owner_pw="readonly", permissions=perm)
    doc.close()
    print("   ✅ E-28 readonly.pdf")

    # E-29: 禁止複製
    path = os.path.join(dir_path, "no_copy.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "禁止複製", fontsize=16, fontname="china-s")
    perm = fitz.PDF_PERM_ACCESSIBILITY | fitz.PDF_PERM_PRINT
    doc.save(path, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="", owner_pw="nocopy", permissions=perm)
    doc.close()
    print("   ✅ E-29 no_copy.pdf")

    # E-30: 已簽名
    path = os.path.join(dir_path, "signed.pdf")
    create_basic_pdf(path, "已簽名 PDF", "模擬已含數字簽名的 PDF。")
    print("   ✅ E-30 signed.pdf")


# ==================== 五、檔案名稱類 ====================

def generate_filename_cases():
    print("\n📁 五、檔案名稱類 (E-31 ~ E-38)")
    dir_path = ensure_dir(os.path.join(OUTPUT_DIR, "filename"))

    filenames = [
        ("中文名稱合同.pdf", "中文檔名"),
        ("with space.pdf", "含空格檔名"),
        ("with_underscore.pdf", "含下劃線檔名"),
        ("with.dots.in.name.pdf", "含多個點的檔名"),
        ("UPPERCASE.PDF", "全大寫副檔名"),
        ("very_long_filename_" + "超長檔名測試" * 20 + ".pdf", "超長檔名"),
        ("特殊@#$%字符.pdf", "含特殊字符檔名"),
        (".hidden.pdf", "隱藏檔案"),
    ]

    for idx, (filename, desc) in enumerate(filenames, start=31):
        path = os.path.join(dir_path, filename)
        try:
            create_basic_pdf(path, f"檔名測試 - {desc}", f"測試檔名：{filename[:50]}")
            display_name = filename[:50] + ('...' if len(filename) > 50 else '')
            print(f"   ✅ E-{idx:02d} {display_name}")
        except Exception as e:
            print(f"   ❌ E-{idx:02d} {filename[:50]} - 失敗: {e}")


# ==================== 六、內容篡改類 ====================

def generate_tamper_cases():
    print("\n📁 六、內容篡改類 (E-39 ~ E-45)")
    dir_path = ensure_dir(os.path.join(OUTPUT_DIR, "tamper"))

    # 建立原始
    original_path = os.path.join(dir_path, "_original.pdf")
    create_basic_pdf(original_path, "合同測試文檔", "甲方：A 公司\n乙方：B 公司\n金額：250,000 元\n" * 10)

    with open(original_path, 'rb') as f:
        original_data = f.read()

    # E-39: 改 1 字節
    path = os.path.join(dir_path, "tamper_1byte.pdf")
    tampered = bytearray(original_data)
    mid = len(tampered) // 2
    tampered[mid] = (tampered[mid] + 1) % 256
    with open(path, 'wb') as f:
        f.write(bytes(tampered))
    print("   ✅ E-39 tamper_1byte.pdf")

    # E-40: 改空白字符
    path = os.path.join(dir_path, "tamper_whitespace.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "合同測試文檔", fontsize=16, fontname="china-s")
    page.insert_text((60, 120), "甲方：A 公司   ", fontsize=12, fontname="china-s")
    page.insert_text((60, 150), "乙方：B 公司", fontsize=12, fontname="china-s")
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print("   ✅ E-40 tamper_whitespace.pdf")

    # E-41: 改元數據
    path = os.path.join(dir_path, "tamper_metadata.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "合同測試文檔", fontsize=16, fontname="china-s")
    doc.set_metadata({"title": "被篡改的標題", "author": "Hacker"})
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print("   ✅ E-41 tamper_metadata.pdf")

    # E-42: 頁面順序改變
    path = os.path.join(dir_path, "tamper_page_order.pdf")
    doc = fitz.open()
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text((60, 80), "第二頁的內容", fontsize=16, fontname="china-s")
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text((60, 80), "第一頁的內容", fontsize=16, fontname="china-s")
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print("   ✅ E-42 tamper_page_order.pdf")

    # E-43: 字體改變
    path = os.path.join(dir_path, "tamper_font.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "合同測試文檔", fontsize=24, fontname="china-s")
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print("   ✅ E-43 tamper_font.pdf")

    # E-44: 重新壓縮
    path = os.path.join(dir_path, "tamper_recompress.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "合同測試文檔", fontsize=16, fontname="china-s")
    doc.save(path, garbage=0, deflate=False, clean=False)
    doc.close()
    print("   ✅ E-44 tamper_recompress.pdf")

    # E-45: 重新保存
    path = os.path.join(dir_path, "tamper_resave.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "合同測試文檔", fontsize=16, fontname="china-s")
    doc.save(path, garbage=4, deflate=True, clean=True)
    doc.close()
    print("   ✅ E-45 tamper_resave.pdf")

    os.remove(original_path)


# ==================== 七、系統邊界類 ====================

def generate_system_cases():
    print("\n📁 七、系統邊界類 (E-46 ~ E-50)")
    dir_path = ensure_dir(os.path.join(OUTPUT_DIR, "system"))

    create_basic_pdf(os.path.join(dir_path, "duplicate_of_contract_0.pdf"), "合同 0", "重複版本。")
    print("   ✅ E-46 duplicate_of_contract_0.pdf")

    create_basic_pdf(os.path.join(dir_path, "not_in_whitelist.pdf"), "未註冊合同", "不在白名單中。")
    print("   ✅ E-47 not_in_whitelist.pdf")

    create_basic_pdf(os.path.join(dir_path, "whitelist_missing.pdf"), "白名單缺失", "白名單中沒有此合同。")
    print("   ✅ E-48 whitelist_missing.pdf")

    create_basic_pdf(os.path.join(dir_path, "hash_collision_test.pdf"), "碰撞測試 A", "內容 A。")
    print("   ✅ E-49 hash_collision_test.pdf")

    create_basic_pdf(os.path.join(dir_path, "zero_hash.pdf"), "零哈希測試", "期望哈希為全 0。")
    print("   ✅ E-50 zero_hash.pdf")


# ==================== 八、特殊場景類 ====================

def generate_special_cases():
    print("\n📁 八、特殊場景類 (E-51 ~ E-60)")
    dir_path = ensure_dir(os.path.join(OUTPUT_DIR, "special"))

    create_basic_pdf(os.path.join(dir_path, "pdf_1_4.pdf"), "PDF 1.4", "1.4 版本。")
    print("   ✅ E-51 pdf_1_4.pdf")

    create_basic_pdf(os.path.join(dir_path, "pdf_1_7.pdf"), "PDF 1.7", "1.7 版本。")
    print("   ✅ E-52 pdf_1_7.pdf")

    create_basic_pdf(os.path.join(dir_path, "pdf_2_0.pdf"), "PDF 2.0", "2.0 版本。")
    print("   ✅ E-53 pdf_2_0.pdf")

    create_basic_pdf(os.path.join(dir_path, "pdf_a.pdf"), "PDF/A", "存檔格式。")
    print("   ✅ E-54 pdf_a.pdf")

    create_basic_pdf(os.path.join(dir_path, "pdf_x.pdf"), "PDF/X", "印刷格式。")
    print("   ✅ E-55 pdf_x.pdf")

    # E-56: 線性化 PDF（移除 linear=True，PyMuPDF 新版本已不支援）
    path = os.path.join(dir_path, "linearized.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "線性化 PDF", fontsize=16, fontname="china-s")
    # ✅ 修復：移除 linear=True 參數
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print("   ✅ E-56 linearized.pdf（注意：新版本 PyMuPDF 不再支援線性化）")

    create_basic_pdf(os.path.join(dir_path, "portfolio.pdf"), "PDF 組合", "組合檔案。")
    print("   ✅ E-57 portfolio.pdf")

    # E-58: 表單
    path = os.path.join(dir_path, "form_filled.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "表單測試", fontsize=16, fontname="china-s")
    widget = fitz.Widget()
    widget.field_name = "name"
    widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    widget.rect = fitz.Rect(60, 120, 300, 150)
    widget.field_value = "張三"
    page.add_widget(widget)
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print("   ✅ E-58 form_filled.pdf")

    # E-59: 註釋
    path = os.path.join(dir_path, "annotation.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 80), "註釋測試", fontsize=16, fontname="china-s")
    annot = page.add_text_annot(fitz.Point(100, 150), "這是一個註釋")
    annot.set_info(title="測試註釋", content="這是註釋內容")
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print("   ✅ E-59 annotation.pdf")

    # E-60: 書籤
    path = os.path.join(dir_path, "bookmark.pdf")
    doc = fitz.open()
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text((60, 80), "第一章", fontsize=16, fontname="china-s")
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text((60, 80), "第二章", fontsize=16, fontname="china-s")
    doc.set_toc([[1, "第一章", 1], [1, "第二章", 2]])
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    print("   ✅ E-60 bookmark.pdf")


# ==================== 主程序 ====================

def main():
    print("=" * 60)
    print("📄 開始生成 60 個 Edge Case PDF")
    print("=" * 60)

    if os.path.exists(OUTPUT_DIR):
        import shutil
        shutil.rmtree(OUTPUT_DIR)

    ensure_dir(OUTPUT_DIR)

    generate_format_cases()
    generate_size_cases()
    generate_content_cases()
    generate_encryption_cases()
    generate_filename_cases()
    generate_tamper_cases()
    generate_system_cases()
    generate_special_cases()

    print("\n" + "=" * 60)
    print("📊 生成完成")
    print("=" * 60)

    total = 0
    for subdir in sorted(os.listdir(OUTPUT_DIR)):
        subdir_path = os.path.join(OUTPUT_DIR, subdir)
        if os.path.isdir(subdir_path):
            count = len([f for f in os.listdir(subdir_path)
                         if os.path.isfile(os.path.join(subdir_path, f))])
            total += count
            print(f"  {subdir:15s}: {count} 個文件")

    print(f"\n  {'總計':15s}: {total} 個文件")
    print(f"  輸出目錄: {os.path.abspath(OUTPUT_DIR)}")
    print("=" * 60)


if __name__ == "__main__":
    main()