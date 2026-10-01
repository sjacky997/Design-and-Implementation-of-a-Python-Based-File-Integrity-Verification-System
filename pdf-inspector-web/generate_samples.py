#!/usr/bin/env python3
# generate_samples.py
"""
批量生成測試用 PDF 合同

生成內容：
- 10 份原始合同（contract_0.pdf ~ contract_9.pdf）
- 每份原始合同生成 4 個篡改版本（共 40 份）
- 總計 50 份 PDF

輸出目錄：
- test_samples/original/   （原始合同）
- test_samples/tampered/   （篡改合同）
"""

import os
import fitz  # PyMuPDF


# ==================== 合同定義 ====================

CONTRACTS = [
    {
        "id": 0,
        "title": "辦公設備採購合同",
        "party_a": "A 科技有限公司",
        "party_b": "B 辦公設備供應商",
        "amount": "250,000.00",
        "account": "6222 0000 1111 1234",
        "date": "2026-03-15",
        "penalty": "5%",
        "content": "甲方向乙方採購筆記本電腦 50 台，型號 ThinkPad X1 Carbon，"
                   "單價 5,000 元，總金額 250,000.00 元。乙方應於交貨日期前完成交付。",
    },
    {
        "id": 1,
        "title": "電子產品銷售合同",
        "party_a": "C 電子科技有限公司",
        "party_b": "D 電子產品經銷商",
        "amount": "480,000.00",
        "account": "6222 0000 2222 5678",
        "date": "2026-03-20",
        "penalty": "8%",
        "content": "甲方向乙方銷售智能手機 200 部，型號 Galaxy S26，"
                   "單價 2,400 元，總金額 480,000.00 元。貨款於交貨後 30 日內結清。",
    },
    {
        "id": 2,
        "title": "企業諮詢服務合同",
        "party_a": "E 集團有限公司",
        "party_b": "F 管理諮詢公司",
        "amount": "120,000.00",
        "account": "6222 0000 3333 9012",
        "date": "2026-04-01",
        "penalty": "10%",
        "content": "甲方聘請乙方提供年度戰略諮詢服務，服務期 12 個月，"
                   "服務費 120,000.00 元，分四期支付，每期 30,000 元。",
    },
    {
        "id": 3,
        "title": "辦公室租賃合同",
        "party_a": "G 網絡科技有限公司",
        "party_b": "H 商業地產有限公司",
        "amount": "35,000.00",
        "account": "6222 0000 4444 3456",
        "date": "2026-04-15",
        "penalty": "15%",
        "content": "甲方租賃乙方位於中環的辦公場地 200 平方米，"
                   "月租金 35,000.00 元，押金三個月共 105,000 元，租期兩年。",
    },
    {
        "id": 4,
        "title": "短期借款合同",
        "party_a": "I 實業有限公司",
        "party_b": "J 商業銀行",
        "amount": "1,000,000.00",
        "account": "6222 0000 5555 7890",
        "date": "2026-05-01",
        "penalty": "20%",
        "content": "甲方向乙方借款人民幣 1,000,000.00 元，借款期限 6 個月，"
                   "年利率 4.35%，到期一次性還本付息。",
    },
    {
        "id": 5,
        "title": "技術開發合同",
        "party_a": "K 製造業集團",
        "party_b": "L 軟件開發團隊",
        "amount": "300,000.00",
        "account": "6222 0000 6666 2345",
        "date": "2026-06-30",
        "penalty": "12%",
        "content": "甲方委託乙方開發企業資源管理系統（ERP），"
                   "開發費 300,000.00 元，交付日期為 2026-06-30，"
                   "驗收合格後支付尾款。",
    },
    {
        "id": 6,
        "title": "貨物運輸合同",
        "party_a": "M 物流有限公司",
        "party_b": "N 貿易有限公司",
        "amount": "28,000.00",
        "account": "6222 0000 7777 6789",
        "date": "2026-05-20",
        "penalty": "6%",
        "content": "乙方委託甲方承運貨物至上海港，貨物價值 800,000 元，"
                   "運費 28,000.00 元，甲方應於 5 日內完成運輸。",
    },
    {
        "id": 7,
        "title": "員工保密協議",
        "party_a": "O 互聯網公司",
        "party_b": "員工 張三",
        "amount": "200,000.00",
        "account": "6222 0000 8888 0123",
        "date": "2026-06-01",
        "penalty": "100%",
        "content": "乙方任職期間及離職後 3 年內，不得洩露甲方商業秘密，"
                   "違反者需支付違約金 200,000.00 元。",
    },
    {
        "id": 8,
        "title": "設備維護服務合同",
        "party_a": "P 電子有限公司",
        "party_b": "Q 設備維護公司",
        "amount": "80,000.00",
        "account": "6222 0000 9999 4567",
        "date": "2026-06-15",
        "penalty": "8%",
        "content": "乙方為甲方提供年度設備維護服務，年服務費 80,000.00 元，"
                   "響應時間 4 小時內，服務期 12 個月。",
    },
    {
        "id": 9,
        "title": "團體意外保險合同",
        "party_a": "R 集團有限公司",
        "party_b": "S 保險股份有限公司",
        "amount": "50,000.00",
        "account": "6222 0000 0000 8901",
        "date": "2026-07-01",
        "penalty": "5%",
        "content": "甲方為旗下 100 名員工投保團體意外險，"
                   "年保費 50,000.00 元，每人保額 1,000,000 元。",
    },
]


# ==================== PDF 生成函數 ====================

def create_pdf(output_path, title, party_a, party_b, amount, account,
               date, penalty, content, tamper_type=None):
    """
    生成一份合同 PDF
    
    tamper_type:
        None         → 原始合同
        "amount"     → 篡改金額
        "account"    → 篡改收款賬號
        "date"       → 篡改日期
        "penalty"    → 篡改違約金條款
    """
    # 根據篡改類型修改欄位
    display_amount = amount
    display_account = account
    display_date = date
    display_penalty = penalty
    warning = ""

    if tamper_type == "amount":
        # 金額 +40%
        try:
            numeric = float(amount.replace(",", ""))
            display_amount = f"{numeric * 1.4:,.2f}"
        except ValueError:
            display_amount = "999,999.00"
        warning = "⚠️ 金額已修改"

    elif tamper_type == "account":
        # 賬號最後 4 位改成 5678
        display_account = account[:-4] + "5678"
        warning = "⚠️ 收款賬號已修改"

    elif tamper_type == "date":
        # 日期延後 2 個月
        display_date = "2026-08-15" if date < "2026-08" else "2026-09-30"
        warning = "⚠️ 交貨日期已修改"

    elif tamper_type == "penalty":
        # 違約金 +10%
        try:
            pct = int(penalty.replace("%", ""))
            display_penalty = f"{pct + 10}%"
        except ValueError:
            display_penalty = "25%"
        warning = "⚠️ 違約金條款已修改"

    # ==================== 建立 PDF ====================
    doc = fitz.open()

    # ---- 第 1 頁：封面 ----
    page = doc.new_page(width=595, height=842)  # A4

    # 標題
    page.insert_text(
        (180, 80),
        title,
        fontsize=22,
        fontname="china-s",   # 簡體中文
        color=(0, 0, 0),
    )

    # 篡改警告（如果有）
    if warning:
        page.insert_text(
            (200, 120),
            warning,
            fontsize=14,
            fontname="china-s",
            color=(1, 0, 0),
        )

    # 合同編號
    page.insert_text(
        (60, 160),
        f"合同編號：CT-2026-{100 + int(date[-2:]):03d}",
        fontsize=12,
        fontname="china-s",
    )

    # 簽署雙方
    page.insert_text((60, 200), f"甲方（委託方）：{party_a}", fontsize=12, fontname="china-s")
    page.insert_text((60, 225), f"乙方（承接方）：{party_b}", fontsize=12, fontname="china-s")

    # 分隔線
    page.draw_line((60, 245), (535, 245), color=(0, 0, 0), width=1)

    # 合同內容
    page.insert_text((60, 280), "一、合同主要內容", fontsize=14, fontname="china-s", color=(0, 0, 0.6))
    
    # 內容自動換行
    text_rect = fitz.Rect(60, 300, 535, 400)
    page.insert_textbox(
        text_rect,
        content,
        fontsize=12,
        fontname="china-s",
        align=fitz.TEXT_ALIGN_LEFT,
    )

    # 關鍵條款
    page.insert_text((60, 440), "二、關鍵條款", fontsize=14, fontname="china-s", color=(0, 0, 0.6))
    page.insert_text((80, 470), f"合同金額：{display_amount} 元", fontsize=12, fontname="china-s")
    page.insert_text((80, 495), f"收款賬號：{display_account}", fontsize=12, fontname="china-s")
    page.insert_text((80, 520), f"履行日期：{display_date}", fontsize=12, fontname="china-s")
    page.insert_text((80, 545), f"違約金比例：{display_penalty}", fontsize=12, fontname="china-s")

    # 簽名區
    page.draw_line((60, 620), (535, 620), color=(0.6, 0.6, 0.6), width=1)
    page.insert_text((80, 660), "甲方簽章：________________", fontsize=12, fontname="china-s")
    page.insert_text((80, 710), "乙方簽章：________________", fontsize=12, fontname="china-s")
    page.insert_text((80, 760), "簽署日期：2026 年 01 月 01 日", fontsize=12, fontname="china-s")

    # ---- 第 2 頁：附加條款（增加文件大小與真實感） ----
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((60, 60), "三、附加條款", fontsize=14, fontname="china-s", color=(0, 0, 0.6))

    clauses = [
        "1. 本合同自雙方簽署之日起生效，有效期至合同履行完畢。",
        "2. 雙方應嚴格按照合同條款履行義務，任何一方違約需承擔相應責任。",
        "3. 本合同未盡事宜，由雙方協商解決，協商不成的，提交仲裁機構仲裁。",
        "4. 本合同一式兩份，甲乙雙方各執一份，具有同等法律效力。",
        "5. 任何對本合同的修改均需雙方書面同意並簽署補充協議。",
        "6. 因不可抗力導致合同無法履行的，雙方互不追究違約責任。",
        "7. 本合同所涉及的商業秘密，雙方均有保密義務。",
        "8. 合同履行過程中產生的爭議，適用中華人民共和國法律。",
    ]
    y = 100
    for clause in clauses:
        rect = fitz.Rect(60, y, 535, y + 50)
        page2.insert_textbox(rect, clause, fontsize=11, fontname="china-s")
        y += 55

    # 保存
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    return output_path


# ==================== 主程序 ====================

def main():
    # 建立輸出目錄
    original_dir = "test_samples/original"
    tampered_dir = "test_samples/tampered"
    os.makedirs(original_dir, exist_ok=True)
    os.makedirs(tampered_dir, exist_ok=True)

    print("=" * 60)
    print("📄 開始生成測試用例 PDF")
    print("=" * 60)

    # ---- 生成原始合同 ----
    print(f"\n📁 生成原始合同 → {original_dir}/")
    for contract in CONTRACTS:
        filename = f"contract_{contract['id']}.pdf"
        filepath = os.path.join(original_dir, filename)
        create_pdf(
            filepath,
            contract["title"],
            contract["party_a"],
            contract["party_b"],
            contract["amount"],
            contract["account"],
            contract["date"],
            contract["penalty"],
            contract["content"],
            tamper_type=None,
        )
        print(f"   ✅ {filename}  ({contract['title']})")

    # ---- 生成篡改版本 ----
    print(f"\n📁 生成篡改合同 → {tampered_dir}/")
    tamper_types = [
        ("amount", "金額篡改"),
        ("account", "收款賬號篡改"),
        ("date", "日期篡改"),
        ("penalty", "違約金條款篡改"),
    ]

    for contract in CONTRACTS:
        for idx, (tamper_type, tamper_name) in enumerate(tamper_types):
            filename = f"contract_{contract['id']}_tamper_{idx}.pdf"
            filepath = os.path.join(tampered_dir, filename)
            create_pdf(
                filepath,
                contract["title"],
                contract["party_a"],
                contract["party_b"],
                contract["amount"],
                contract["account"],
                contract["date"],
                contract["penalty"],
                contract["content"],
                tamper_type=tamper_type,
            )
            print(f"   ✅ {filename}  ({tamper_name})")

    # ---- 統計 ----
    print("\n" + "=" * 60)
    print("📊 生成完成")
    print("=" * 60)
    print(f"  原始合同：{len(os.listdir(original_dir))} 份")
    print(f"  篡改合同：{len(os.listdir(tampered_dir))} 份")
    print(f"  總計：{len(os.listdir(original_dir)) + len(os.listdir(tampered_dir))} 份")
    print("=" * 60)


if __name__ == "__main__":
    main()