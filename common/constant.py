from typing import Any


class Constant:
    """
    常量类
    """
    # 常量请求头
    HEADERS: dict[str, Any] = {"User-Agent": "Dart/2.17 (dart:io)"}
    # 工学云请求参数
    BASE_URL: str = "https://api.moguding.net:9000"
    MD5_SALT: str = "3478cbbc33f84bd00d75d7dfa69e0daa"
    AES_ENCRYPT_SECRET_KEY: bytes = b"23DbtQHR2UMbH6mJ"
    AES_ENCRYPT_BASE64_SECRET_KEY: bytes = b"XwKsGlMcdPMEhR1B"
