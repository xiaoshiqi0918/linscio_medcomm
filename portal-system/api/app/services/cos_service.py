"""
腾讯云 COS 预签名 URL 服务（安装包下载）。
未配置 COS_SECRET_ID / COS_SECRET_KEY 时，调用方应返回 503 或明确提示。
"""
from app.config import settings


def is_cos_configured() -> bool:
    return bool(
        getattr(settings, "COS_SECRET_ID", None)
        and getattr(settings, "COS_SECRET_KEY", None)
    )


def generate_presign_url(file_key: str, expires_in: int = 7200) -> str:
    """
    生成 COS 对象的 GET 预签名 URL（用于浏览器下载）。
    :param file_key: 对象在桶内的 key，如 releases/v1.0.0/linscio-ai-v1.0.0.tar.gz
    :param expires_in: 签名有效秒数，默认 2 小时
    :return: 预签名 URL
    """
    if not is_cos_configured():
        raise RuntimeError("COS 未配置，无法生成下载链接")
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError:
        raise RuntimeError("COS SDK 未安装，请安装 cos-python-sdk-v5")

    config = CosConfig(
        Region=settings.COS_REGION,
        SecretId=settings.COS_SECRET_ID,
        SecretKey=settings.COS_SECRET_KEY,
        Scheme="https",
    )
    client = CosS3Client(config)
    bucket = settings.COS_BUCKET
    url = client.get_presigned_url(
        Bucket=bucket,
        Key=file_key,
        Method="GET",
        Expired=expires_in,
    )
    return url
