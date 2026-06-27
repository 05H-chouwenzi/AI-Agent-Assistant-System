"""
密码加密 —— hashlib (兼容性好，无长度限制)
"""
import hashlib

SALT = "EnterpriseAI_2024"

def hash_password(password: str) -> str:
    """加密密码"""
    return hashlib.sha256((password + SALT).encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return hash_password(plain_password) == hashed_password
