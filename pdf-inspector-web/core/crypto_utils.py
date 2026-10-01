# core/crypto_utils.py
"""
SM2 私钥的加密存储与解密加载

使用 Fernet（对称加密）对私钥进行加密：
- keyfile.key         → Fernet 密钥（128位base64编码）
- encrypted_private.bin → 加密后的私钥密文

安全原则：
- keyfile.key 与 encrypted_private.bin 应分开存放
- 生产环境应将 keyfile.key 存储在环境变量或密钥管理服务中
"""

import os
from cryptography.fernet import Fernet


def generate_fernet_key(save_path: str = "keyfile.key") -> bytes:
    """生成 Fernet 密钥并保存"""
    key = Fernet.generate_key()
    with open(save_path, "wb") as f:
        f.write(key)
    return key


def encrypt_private_key(private_key_hex: str,
                        key_file: str = "keyfile.key",
                        output_file: str = "encrypted_private.bin") -> None:
    """用 Fernet 加密私钥并保存"""
    if not os.path.exists(key_file):
        raise FileNotFoundError(f"密钥文件不存在: {key_file}")

    with open(key_file, "rb") as f:
        key = f.read()

    f = Fernet(key)
    encrypted = f.encrypt(private_key_hex.encode())
    with open(output_file, "wb") as out:
        out.write(encrypted)


def load_private_key(encrypted_file: str = "encrypted_private.bin",
                     key_file: str = "keyfile.key") -> str:
    """从加密文件加载并解密私钥"""
    if not os.path.exists(key_file):
        raise FileNotFoundError(f"密钥文件不存在: {key_file}")
    if not os.path.exists(encrypted_file):
        raise FileNotFoundError(f"加密私钥文件不存在: {encrypted_file}")

    with open(key_file, "rb") as f:
        key = f.read()
    with open(encrypted_file, "rb") as f:
        encrypted = f.read()

    f = Fernet(key)
    return f.decrypt(encrypted).decode()