import os
from gmssl import sm2, func
from .sm3_utils import compute_sm3_from_bytes

class SM2Helper:
    def __init__(self, private_key_hex: str = None):
        if private_key_hex is None:
            self.private_key = os.urandom(32).hex()
        else:
            self.private_key = private_key_hex
        self.crypt_sm2 = sm2.CryptSM2(private_key=self.private_key, public_key="")

    def sign(self, data: bytes) -> str:
        random_hex = func.random_hex(self.crypt_sm2.para_len)
        digest = compute_sm3_from_bytes(data)
        return self.crypt_sm2.sign(digest.encode(), random_hex)

    def verify(self, data: bytes, signature_hex: str) -> bool:
        digest = compute_sm3_from_bytes(data)
        return self.crypt_sm2.verify(signature_hex, digest.encode())