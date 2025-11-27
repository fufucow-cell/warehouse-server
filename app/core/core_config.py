from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类"""
    
    # API 配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8003  # Warehouse server uses dedicated port
    API_DEBUG: bool = False
    APP_ENV: str = "dev"
    
    # 数据库配置（待資料庫提供後可透過環境變數覆寫）
    DB_HOST: str = "localhost"
    DB_PORT: int = 5434
    DB_USER: str = "cowlin"
    DB_PASSWORD: str = "abc123"
    DB_NAME: str = "smartwarehouse_warehouse_dev"
    DB_DRIVER: str = "postgresql"
    
    # 内部服务配置（用于跨服务调用）
    HOUSEHOLD_SERVER_URL: str = "http://localhost:8002"
    
    # JWT 配置（与 auth_server 共享）
    JWT_SECRET_KEY: str = "your-secret-key-change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    
    # CORS 配置（环境变量中使用逗号分隔，如：http://localhost:3000,http://localhost:8080）
    CORS_ORIGINS: str = "*"
    
    # 控制台日志开关（主要用于本地開發調試）
    LOG_REQUEST_CONSOLE: bool = False
    LOG_RESPONSE_CONSOLE: bool = False
    
    # 构建数据库 URL（支持异步和同步）
    @property
    def database_url(self) -> str:
        """同步数据库连接 URL"""
        return f"{self.DB_DRIVER}://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def database_url_async(self) -> str:
        """异步数据库连接 URL (使用 asyncpg)"""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def cors_origins_list(self) -> list[str]:
        """获取 CORS 来源列表"""
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

