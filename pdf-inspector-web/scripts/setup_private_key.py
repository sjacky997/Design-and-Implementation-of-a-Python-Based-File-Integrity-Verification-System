#!/usr/bin/env python3
# scripts/setup_private_key.py
"""
一次性初始化脚本：生成并加密存储 SM2 私钥

使用场景：
    管理员在部署服务器时，执行一次此脚本，
    生成 encrypted_private.bin 和 keyfile.key。

用法：
    python scripts/setup_private_key.py

流程：
    1. 询问是否使用随机生成的新私钥，还是粘贴已有私钥
    2. 生成 Fernet 密钥 (keyfile.key)
    3. 用 Fernet 加密私钥，写入 encrypted_private.bin
"""

import os
import sys
import getpass

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sm2_utils import SM2Helper
from core.crypto_utils import generate_fernet_key, encrypt_private_key


def main():
    print("=" * 60)
    print("🔐 SM2 私钥初始化工具（方案A：服务器端加密存储）")
    print("=" * 60)

    # 检查是否已存在
    if os.path.exists("encrypted_private.bin"):
        ans = input("⚠️ 已存在 encrypted_private.bin，是否覆盖？(y/N): ").strip().lower()
        if ans != "y":
            print("操作已取消。")
            return

    # 选择私钥来源
    print("\n请选择私钥来源：")
    print("  1. 随机生成新的 SM2 私钥")
    print("  2. 手动粘贴已有的 64 位十六进制私钥")
    choice = input("请输入选项 (1/2): ").strip()

    if choice == "2":
        private_key = getpass.getpass("请粘贴私钥（输入不回显）: ").strip()
        if len(private_key) != 64:
            print("❌ 私钥必须为 64 位十六进制字符")
            return
        try:
            int(private_key, 16)
        except ValueError:
            print("❌ 私钥不是有效的十六进制字符串")
            return
    else:
        print("\n⚙️ 正在生成随机私钥...")
        helper = SM2Helper()
        private_key = helper.private_key
        print(f"✅ 已生成私钥：{private_key[:16]}...{private_key[-8:]}")

    # 生成 Fernet 密钥
    print("\n🔑 正在生成 Fernet 密钥 (keyfile.key)...")
    generate_fernet_key("keyfile.key")

    # 加密私钥
    print("🔒 正在加密私钥 (encrypted_private.bin)...")
    encrypt_private_key(private_key, "keyfile.key", "encrypted_private.bin")

    print("\n" + "=" * 60)
    print("✅ 初始化完成！")
    print("=" * 60)
    print(f"  keyfile.key             → {os.path.abspath('keyfile.key')}")
    print(f"  encrypted_private.bin   → {os.path.abspath('encrypted_private.bin')}")
    print("\n⚠️  安全提醒：")
    print("  1. 请务必备份 keyfile.key，丢失后无法恢复私钥")
    print("  2. 生产环境应将 keyfile.key 与 encrypted_private.bin 分开存放")
    print("  3. 请勿将这两个文件提交到 Git 仓库")
    print("=" * 60)


if __name__ == "__main__":
    main()