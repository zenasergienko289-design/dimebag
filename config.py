import os
from pathlib import Path

# =====================================================
# ПУТИ
# =====================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Файл базы будет лежать на уровень выше папки bot
DB_PATH = os.path.join(os.path.dirname(BASE_DIR), "funpay.db")
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# Папка с фронтом Mini App
WEBAPP_DIR = Path(BASE_DIR).parent / "webapp"

# =====================================================
# БОТ
# =====================================================
BOT_TOKEN = "8886426256:AAHJhNYZXnDhj3K68E5RHacEIJgG830_c4Q"
BOT_USERNAME = "papagaratbot"  # без @ — используется в ссылках на сделки

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