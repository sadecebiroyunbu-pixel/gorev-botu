# config.py
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable bulunamadı!")

# Admin ID'leri (Render'deki ADMIN_IDS değişkeninden alıyor)
admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMINS = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]

# Başlangıç bakiyesi
START_BALANCE = 0

# Görev ödülleri
REWARDS = {
    "channel": 750,
    "group": 1000,
    "bot": 500,
    "view": 300,
    "reaction": 400,
    "boost": 800
}

# 7 günlük kilit süresi (saniye)
LOCK_DAYS = 7 * 24 * 60 * 60
