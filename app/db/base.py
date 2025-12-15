from sqlalchemy.orm import DeclarativeBase

# 声明式基类（用于 Alembic 迁移）
class Base(DeclarativeBase):
    pass
