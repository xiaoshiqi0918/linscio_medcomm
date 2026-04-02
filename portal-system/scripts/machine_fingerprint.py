#!/usr/bin/env python3
"""
机器指纹生成（7.1）- 供主应用/客户端调用，生成唯一 machine_id。
主应用在心跳、绑定、生成次数校验时传入此值；Portal 仅提供本脚本作为参考。
"""
import hashlib
import subprocess


def get_machine_fingerprint() -> str:
    features = []
    try:
        with open("/etc/machine-id", "r") as f:
            features.append(f.read().strip())
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["dmidecode", "-t", "baseboard", "-s", "serial-number"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r.stdout and r.stdout.strip():
            features.append(r.stdout.strip())
    except Exception:
        pass
    raw = "|".join(filter(None, features)).encode() or b"fallback"
    return hashlib.sha256(raw).hexdigest()[:32]


if __name__ == "__main__":
    print(get_machine_fingerprint())
