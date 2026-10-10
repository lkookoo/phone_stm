# app/config/settings.py
from pathlib import Path
import os

import yaml
from dotenv import load_dotenv
from pydantic_settings import BaseSettings


# 项目根目录：D:\phone_stm
#   __file__            = D:\phone_stm\app\config\settings.py
#   .parent             = D:\phone_stm\app\config
#   .parent.parent      = D:\phone_stm\app
#   .parent.parent.parent = D:\phone_stm
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ★ 关键：显式指定 .env 路径，把变量注入 os.environ
#   adapter 里 os.environ.get("HTTPS_PROXY") 就读这里
#   override=True：.env 的值优先于系统环境变量
load_dotenv(BASE_DIR / ".env", override=True)


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://x1:x1pass@localhost:5432/x1monitor"
    symbols_file: str = str(BASE_DIR / "app" / "config" / "symbols.yaml")
    health_interval: int = 5
    failover_threshold: float = 70.0
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    class Config:
        env_file = str(BASE_DIR / ".env")
        extra = "ignore"


settings = Settings()


def load_symbols():
    with open(settings.symbols_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


SYMBOLS = load_symbols()