"""
重试装饰器
"""
import time
import functools


def retry(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
    """
    重试装饰器

    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 延迟倍数
        exceptions: 需要重试的异常类型
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        print(f"[WARN] attempt {attempt + 1} failed: {e}")
                        print(f"  retrying after {current_delay}s...")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        print(f"[ERROR] failed after {max_attempts} attempts")

            raise last_exception

        return wrapper
    return decorator


def async_retry(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
    """异步重试装饰器"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            import asyncio
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        print(f"[WARN] attempt {attempt + 1} failed: {e}")
                        print(f"  retrying after {current_delay}s...")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        print(f"[ERROR] failed after {max_attempts} attempts")

            raise last_exception

        return wrapper
    return decorator
