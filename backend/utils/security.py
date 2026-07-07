"""
密码加密 —— 支持 bcrypt（新密码）和 SHA256（旧用户，兼容）

注意：passlib 与最新 bcrypt 存在兼容性问题，此处直接使用 bcrypt 原生库。
"""
import hashlib
import bcrypt


def hash_password(password: str) -> str:
    """加密密码 —— 使用 bcrypt 自动加盐"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _is_sha256_hex(hash_str: str) -> bool:
    """判断是否为 64 位小写十六进制字符串（旧版 SHA256）"""
    if len(hash_str) != 64:
        return False
    try:
        int(hash_str, 16)
        return True
    except ValueError:
        return False


def _is_bcrypt(hash_str: str) -> bool:
    """判断是否为 bcrypt hash"""
    return hash_str.startswith("$2b$") or hash_str.startswith("$2a$") or hash_str.startswith("$2y$")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码 —— 兼容 bcrypt 和旧版 SHA256"""
    # 1) bcrypt
    if _is_bcrypt(hashed_password):
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except Exception:
            return False

    # 2) 旧版 SHA256 hex
    if _is_sha256_hex(hashed_password):
        return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password

    return False
