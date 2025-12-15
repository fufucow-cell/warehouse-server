# 此文件保留用於向後兼容，實際的資料庫連接已移至 app.db.session
# 建議新代碼直接使用 app.db.session.get_db 和 app.db.base.Base

from app.db.session import get_db, AsyncSessionLocal, engine
from app.db.base import Base

__all__ = ["get_db", "AsyncSessionLocal", "engine", "Base"]
