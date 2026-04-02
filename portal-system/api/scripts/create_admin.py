"""
首次部署或恢复管理员账号。用法：
  cd api && python scripts/create_admin.py
需已设置 .env 中的 DATABASE_URL、JWT_SECRET_KEY 等，且数据库已创建表。
默认创建的管理员为 用户名=admin、密码=admin123，与 linscio-ai 全系统通用管理员一致。
创建的管理员会同步写入 Registry htpasswd，可用同一账号登录管理后台与 Registry UI（docker login）。
同时会创建或更新同名门户用户（PortalUser），使该账号也可登录门户网站。
若管理员已存在，会将其密码同步到镜像仓库认证（便于恢复仅 htpasswd 被清空的情况）。
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from app.models import AdminUser, PortalUser
from app.services.auth_service import hash_password
from app.services.registry_service import write_htpasswd


async def main():
    username = os.environ.get("ADMIN_USERNAME", "admin")
    password = os.environ.get("ADMIN_PASSWORD", "admin123")
    password_hash = hash_password(password)

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        # 1. 创建或更新管理员
        r = await db.execute(select(AdminUser).where(AdminUser.username == username))
        existing_admin = r.scalar_one_or_none()
        if existing_admin:
            if os.environ.get("ADMIN_UPDATE_PASSWORD") == "1":
                existing_admin.password_hash = password_hash
                await db.commit()
                print(f"已更新管理员 {username} 的密码")
            else:
                print(f"管理员 {username} 已存在，跳过创建（将同步密码到门户与镜像仓库）")
        else:
            admin = AdminUser(
                username=username,
                password_hash=password_hash,
                scope="super",
            )
            db.add(admin)
            await db.commit()
            print(f"已创建管理员: {username}")

        # 2. 创建或更新同名门户用户，使管理员账号可登录门户网站
        r2 = await db.execute(select(PortalUser).where(PortalUser.username == username))
        portal_user = r2.scalar_one_or_none()
        if portal_user:
            portal_user.password_hash = password_hash
            await db.commit()
            print(f"已同步门户用户 {username} 的密码，可用该账号登录门户网站")
        else:
            portal_user = PortalUser(
                username=username,
                password_hash=password_hash,
                email=os.environ.get("ADMIN_EMAIL") or f"{username}@admin.local",
                is_active=True,
            )
            db.add(portal_user)
            await db.commit()
            print(f"已创建同名门户用户 {username}，可用该账号登录门户网站")

    # 3. 同步到 Registry htpasswd（新建或恢复镜像仓库认证）
    if write_htpasswd(username, password):
        print("已同步到镜像仓库认证，可用该账号登录 Registry UI 或 docker login")
        print("若 Registry 已运行，请执行: docker compose restart linscio-registry 以重新加载认证")
    else:
        print("警告: 未能写入 registry/auth/htpasswd，请检查 API 容器对 registry/auth 的写权限")


if __name__ == "__main__":
    asyncio.run(main())
