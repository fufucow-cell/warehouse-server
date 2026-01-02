from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类"""
    
    # API 配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8003  # Warehouse server uses dedicated port
    API_DEBUG: bool = False
    APP_ENV: str = "dev"
    APP_NAME: str = "warehouse_server"  # 应用名称（用于数据库连接标识）
    
    # 数据库配置（待資料庫提供後可透過環境變數覆寫）
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3307
    DB_USER: str = "cowlin"
    DB_PASSWORD: str = "abc123"
    DB_NAME: str = "smartwarehouse_warehouse_dev"
    DB_DRIVER: str = "mysql"
    
    # JWT 配置（与 auth_server 共享）
    JWT_SECRET_KEY: str = "your-secret-key-change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    
    # 内部服务配置（用于跨服务调用）
    HOUSEHOLD_SERVER_URL: str = "http://localhost:8002"
    
    # CORS 配置（环境变量中使用逗号分隔，如：http://localhost:3000,http://localhost:8080）
    CORS_ORIGINS: str = "*"
    
    # 日志开关
    ENABLE_LOG: bool = True

    # 字段长度常量
    TABLE_MAX_LENGTH_NAME: int = 100 
    TABLE_MAX_LENGTH_DESCRIPTION: int = 200
    TABLE_MAX_LENGTH_LINK: int = 500
    
    # 文件上传配置
    UPLOAD_DIR: str = "uploads"  # 文件上传目录（相对于项目根目录）
    MAX_UPLOAD_SIZE: int = 2 * 1024 * 1024  # 最大文件大小：2MB（建议值，10KB 太小，1-2MB 适合物品照片）
    ALLOWED_IMAGE_EXTENSIONS: list[str] = [".jpg", ".jpeg", ".png"]  # 允许的图片扩展名
    
    # 图片 URL 基础地址（用于生成完整的图片访问 URL）
    BASE_URL: str = "http://localhost:8000"
    
    # 构建数据库 URL（支持异步和同步）
    @property
    def database_url(self) -> str:
        return f"{self.DB_DRIVER}://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def database_url_async(self) -> str:
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
    
    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


# 全局配置实例
settings = Settings()

