# core/signer_factory.py
"""
签名器工厂：根据模式返回对应的签名器
"""

import os
from .signers import ManualSigner, ServerSigner, ClientSigner


def get_signer(mode: str = "auto", **kwargs):
    """
    根据模式返回签名器实例。

    参数:
        mode: "manual" / "server" / "client" / "auto"
        private_key_hex        : 手动模式下的私钥
        signature_from_client  : 浏览器端签名结果
        encrypted_file         : 服务器存储加密私钥路径（默认 encrypted_private.bin）
        key_file               : Fernet 密钥路径（默认 keyfile.key）
    """

    if mode == "manual":
        return ManualSigner(kwargs.get("private_key_hex"))

    elif mode == "server":
        return ServerSigner(
            encrypted_file=kwargs.get("encrypted_file", "encrypted_private.bin"),
            key_file=kwargs.get("key_file", "keyfile.key"),
        )

    elif mode == "client":
        return ClientSigner(kwargs.get("signature_from_client"))

    elif mode == "auto":
        # 优先服务器端存储
        if os.path.exists("encrypted_private.bin") and os.path.exists("keyfile.key"):
            try:
                return ServerSigner()
            except Exception:
                pass
        # 回退到手动输入
        if kwargs.get("private_key_hex"):
            return ManualSigner(kwargs.get("private_key_hex"))

        raise ValueError("无法自动选择签名模式，请指定 mode 参数")

    else:
        raise ValueError(f"不支持的签名模式: {mode}")