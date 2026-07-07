"""
客户端 IP 获取工具
"""
from fastapi import Request


def get_client_ip(request: Request) -> str:
    """从请求中提取客户端真实 IP（支持反向代理）"""
    # 优先取 X-Forwarded-For（NGINX 等反向代理会设置）
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # 取第一个 IP（客户端真实 IP）
        return forwarded.split(",")[0].strip()

    # 其次取 X-Real-IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # 兜底取直连 IP
    client = request.client
    if client:
        return client.host

    return "unknown"
