#!/usr/bin/env python3
"""
生成 Ed25519 密钥对，用于授权管理公钥签名方案。
门户配置私钥（LINSCIO_LICENSE_PRIVATE_KEY），客户端配置公钥（LINSCIO_LICENSE_PUBLIC_KEY）。
"""
import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main():
    key = Ed25519PrivateKey.generate()
    private_bytes = key.private_bytes_raw()
    public_bytes = key.public_key().public_bytes_raw()
    private_b64 = base64.b64encode(private_bytes).decode("ascii")
    public_b64 = base64.b64encode(public_bytes).decode("ascii")
    print("将以下内容分别配置到门户与客户端，请勿泄露私钥。")
    print()
    print("# 门户 .env（portal-system）")
    print(f"LINSCIO_LICENSE_PRIVATE_KEY={private_b64}")
    print()
    print("# 主产品 .env 或客户端配置")
    print(f"LINSCIO_LICENSE_PUBLIC_KEY={public_b64}")


if __name__ == "__main__":
    main()
