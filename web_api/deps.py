"""
共享 FastAPI 依赖项，供所有路由复用
"""
from src.storage.database import DatabaseManager
from src.helpers import load_config


def get_db():
    """提供 DatabaseManager 实例。调用方负责调用 db.close()。"""
    config = load_config()
    return DatabaseManager(config['storage']['db_path'])


def get_db_dep():
    """FastAPI Depends 用生成器版本，请求结束后自动关闭。"""
    config = load_config()
    db = DatabaseManager(config['storage']['db_path'])
    try:
        yield db
    finally:
        db.close()
