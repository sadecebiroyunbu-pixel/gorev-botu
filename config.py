# config.py
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable bulunamadı! Render'de Environment kısmına ekle.")

# Admin ID'lerin (kendi Telegram ID'ni yaz)
ADMINS = [123456789]  # buraya kendi ID'ni yaz

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
