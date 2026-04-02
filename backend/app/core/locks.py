"""
分域写锁
五个域互不阻塞，同一域内串行写
"""
import asyncio

_domain_locks: dict[str, asyncio.Lock] = {}

DOMAINS = (
    "articles",
    "images",
    "literature",
    "knowledge",
    "examples",
    "system",
)


def get_domain_lock(domain: str) -> asyncio.Lock:
    """获取指定域的信号量"""
    if domain not in _domain_locks:
        _domain_locks[domain] = asyncio.Lock()
    return _domain_locks[domain]


async def acquire_domain(domain: str):
    """获取域锁"""
    lock = get_domain_lock(domain)
    return await lock.acquire()


def release_domain(domain: str):
    """释放域锁"""
    lock = get_domain_lock(domain)
    if lock.locked():
        lock.release()
