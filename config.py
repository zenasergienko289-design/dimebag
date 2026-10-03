import os
from pathlib import Path

# =====================================================
# ПУТИ
# =====================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(os.path.dirname(BASE_DIR), "funpay.db")
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# ⚠️ WEBAPP_DIR: папка, где лежат index.html и static/
# Вариант A: /app/webapp/  (фронт в подпапке)
WEBAPP_DIR = Path(BASE_DIR) / "webapp"

# Если у тебя фронт лежит прямо в /app (index.html рядом с api.py) — используй:
# WEBAPP_DIR = Path(BASE_DIR)

# Если фронт лежит в /webapp (на уровень выше /app) — используй:
# WEBAPP_DIR = Path("/webapp")

# =====================================================
# БОТ
# =====================================================
BOT_TOKEN = "8886426256:AAHJhNYZXnDhj3K68E5RHacEIJgG830_c4Q"
BOT_USERNAME = "papagaratbot"

MANAGER_USER = "RelayerForGifts"
HELPER_USER = "RelayerForGifts"
SUPPORT_LINK = f"https://t.me/{MANAGER_USER}"

# =====================================================
# MINI APP
# =====================================================
MINI_APP_URL = "https://zenasergienko289-design.github.io/-/"
WEBAPP_URL = MINI_APP_URL
API_HOST = "127.0.0.1"
API_PORT = 8000
