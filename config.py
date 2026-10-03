import os
from pathlib import Path

# =====================================================
# ПУТИ
# =====================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(os.path.dirname(BASE_DIR), "funpay.db")
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

WEBAPP_DIR = Path(BASE_DIR) / "webapp"

# =====================================================
# БОТ
# =====================================================
BOT_TOKEN = "8937795556:AAGuQE_VtkwVAkQXbjaKNhnG3DOAvlxUvig"
BOT_USERNAME = "Fun8Pay_bot"

MANAGER_USER = "Gifts_Bankings"
HELPER_USER = "Gifts_Bankings"
SUPPORT_LINK = f"https://t.me/{MANAGER_USER}"

# =====================================================
# MINI APP
# =====================================================
MINI_APP_URL = "https://zenasergienko289-design.github.io/-/"
WEBAPP_URL = MINI_APP_URL
API_HOST = "127.0.0.1"
API_PORT = 8000
