"""
Alembic 迁移：迁移前备份，失败则回滚
可被 Electron 或单独脚本调用
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

# 添加 backend 到 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(Path(__file__).resolve().parent.parent)

from app.core.config import settings


def main():
    import time
    db_path = Path(settings.db_path)
    backup = None
    if db_path.exists():
        stamp = int(time.time())
        backup = f"{settings.db_path}.{stamp}.linscio-backup"
        shutil.copy2(settings.db_path, backup)
        print(f"Backed up to {backup}")
    else:
        print("DB not found, skipping backup")

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=Path(__file__).resolve().parent.parent,
    )
    if result.returncode != 0 and backup:
        shutil.copy2(backup, settings.db_path)
        print(f"Migration failed, restored from {backup}")
        sys.exit(1)


if __name__ == "__main__":
    main()
