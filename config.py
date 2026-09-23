import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Virgülle ayrılmış admin user_id listesi, örn: "123456789,987654321"
_admin_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_raw.split(",") if x.strip().isdigit()]

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN ortam değişkeni ayarlanmamış!")

if not ADMIN_IDS:
    raise RuntimeError("ADMIN_IDS ortam değişkeni ayarlanmamış! Örn: 123456789")
