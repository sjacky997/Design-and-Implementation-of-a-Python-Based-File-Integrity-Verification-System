# core/signers.py
"""
统一签名器接口

三种签名模式：
- ManualSigner : 用户手动输入私钥（演示用）
- ServerSigner : 服务器端加密存储私钥（生产环境，本方案A核心）
- ClientSigner : 浏览器端签名（高级安全场景）

所有签名器均实现 BaseSigner 接口，可被 ReportSigner 统一调用。
"""

from abc import ABC, abstractmethod
from gmssl import sm2, func
from .sm3_utils import compute_sm3_from_bytes


class BaseSigner(ABC):
    """签名器抽象基类"""

    @abstractmethod
    def sign(self, data: bytes) -> str:
        """对数据进行签名，返回十六进制字符串"""
        pass

    @abstractmethod
    def get_mode_name(self) -> str:
        """返回模式名称，用于展示"""
        pass


class ManualSigner(BaseSigner):
    """方案C：用户手动输入私钥（演示模式）"""

    def __init__(self, private_key_hex: str):
        if not private_key_hex or len(private_key_hex) != 64:
            raise ValueError("私钥必须为64位十六进制字符")
        self.private_key = private_key_hex
        self.crypt_sm2 = sm2.CryptSM2(private_key=self.private_key, public_key="")

    def sign(self, data: bytes) -> str:
        random_hex = func.random_hex(self.crypt_sm2.para_len)
        digest = compute_sm3_from_bytes(data)
        return self.crypt_sm2.sign(digest.encode(), random_hex)

    def get_mode_name(self) -> str:
        return "手动输入模式（演示）"


class ServerSigner(BaseSigner):
    """
    方案A：服务器端加密存储私钥（生产环境）

    - 服务器启动时从 encrypted_private.bin 加载并解密私钥
    - 私钥仅存于内存，不写入日志
    - 用户验证时无需输入私钥
    """

    def __init__(self,
                 encrypted_file: str = "encrypted_private.bin",
                 key_file: str = "keyfile.key"):
        # 延迟导入，避免循环依赖
        from .crypto_utils import load_private_key

        self.private_key = load_private_key(encrypted_file, key_file)
        if not self.private_key or len(self.private_key) != 64:
            raise ValueError("解密后的私钥格式不正确")
        self.crypt_sm2 = sm2.CryptSM2(private_key=self.private_key, public_key="")

    def sign(self, data: bytes) -> str:
        random_hex = func.random_hex(self.crypt_sm2.para_len)
        digest = compute_sm3_from_bytes(data)
        return self.crypt_sm2.sign(digest.encode(), random_hex)

    def get_mode_name(self) -> str:
        return "服务器自动签名模式（生产）"


class ClientSigner(BaseSigner):
    """
    方案B：浏览器端签名（服务器零接触私钥）

    - 签名运算在浏览器内完成
    - 服务器只接收签名结果，用于组装报告
    """

    def __init__(self, signature_from_client: str = None):
        self.signature = signature_from_client

    def sign(self, data: bytes) -> str:
        if self.signature:
            return self.signature
        raise ValueError("浏览器端签名结果未传入")

    def get_mode_name(self) -> str:
        return "浏览器端签名模式（高安全）"