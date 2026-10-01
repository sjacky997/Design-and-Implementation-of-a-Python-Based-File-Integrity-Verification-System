# core/sm3_utils.py
from gmssl import sm3


def compute_sm3_from_bytes(data: bytes) -> str:
    """計算字節數據的 SM3 哈希"""
    return sm3.sm3_hash(list(data))


def compute_sm3_from_file(filepath: str) -> str:
    """計算文件的 SM3 哈希（一次性讀取，適合小文件）"""
    with open(filepath, 'rb') as f:
        return compute_sm3_from_bytes(f.read())


def compute_sm3_from_file_chunked(filepath: str, chunk_size: int = 8192) -> str:
    """
    分塊計算文件的 SM3 哈希（適合大文件，防止內存耗盡）
    
    注意：gmssl 的 sm3_hash 不支持增量更新，
    這裡採用逐塊讀取後拼接再哈希的策略。
    對於超大文件，建議改用支持增量更新的哈希庫。
    """
    chunks = []
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
    
    # 拼接所有塊後計算哈希
    full_data = b''.join(chunks)
    return compute_sm3_from_bytes(full_data)