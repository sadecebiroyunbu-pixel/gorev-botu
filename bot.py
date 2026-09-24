# bot.py

import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMINS, REWARDS
from database import (
    init_db, get_user, create_user, update_balance, 
    create_task, get_active_tasks, add_completion, check_completion, add_xp
)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ==================== STATES ====================
class AddTask(StatesGroup):
    waiting_for_link = State()
    waiting_for_title = State()

# ==================== KEYBOARDS ====================
def main_menu():
    kb = [
        [InlineKeyboardButton(text="💰 Kazanç", callback_data="earn"),
         InlineKeyboardButton(text="📢 Tanıt", callback_data="promote")],
        [InlineKeyboardButton(text="👤 Hesabım", callback_data="profile"),
         InlineKeyboardButton(text="📋 Görevlerim", callback_data="my_tasks")],
        [InlineKeyboardButton(text="📌 Kurallar", callback_data="rules"),
         InlineKeyboardButton(text="🔗 Referans", callback_data="referral")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def earn_categories():
    kb = [
        [InlineKeyboardButton(text="📢 Kanallar", callback_data="cat_channel"),
         InlineKeyboardButton(text="👥 Gruplar", callback_data="cat_group")],
        [InlineKeyboardButton(text="👁 Görüntülenme", callback_data="cat_view"),
         InlineKeyboardButton(text="🤖 Botlar", callback_data="cat_bot")],
        [InlineKeyboardButton(text="❤️ Tepkiler", callback_data="cat_reaction"),
         InlineKeyboardButton(text="⚡ Boost", callback_data="cat_boost")],
        [InlineKeyboardButton(text="🔙 Geri", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def promote_menu():
    kb = [
        [InlineKeyboardButton(text="📢 Kanal", callback_data="add_channel"),
         InlineKeyboardButton(text="👥 Grup", callback_data="add_group")],
        [InlineKeyboardButton(text="🤖 Bot", callback_data="add_bot"),
         InlineKeyboardButton(text="👁 Gönderi", callback_data="add_view")],
        [InlineKeyboardButton(text="🔙 Geri", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ==================== HANDLERS ====================
@dp.message(CommandStart())
async def start_handler(message: Message):
    user = message.from_user
    referrer = None
    if len(message.text.split()) > 1:
        try:
            referrer = int(message.text.split()[1])
        except:
            pass
    
    await create_user(user.id, user.username, user.full_name, referrer)
    
    text = (
        f"👋 <b>PR GRAM | DRAGON</b>'a hoş geldin!\n\n"
        f"Telegram'da tanıtım platformu\n\n"
        f"Görev yap, GRAM kazan, kendi kanalını/grubunu tanıt!"
    )
    await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "Ana menüye döndün.",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "earn")
async def earn_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎯 <b>Kazanmak için görev kategorisi seç</b>",
        reply_markup=earn_categories(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("cat_"))
async def category_handler(callback: CallbackQuery):
    cat = callback.data.replace("cat_", "")
    tasks = await get_active_tasks(cat)
    
    if not tasks:
        await callback.message.edit_text(
            "❌ <b>Uygun görev yok</b>\n\n"
            "⚠️ Kanallardan / Gruplardan 7 günden önce ayrılma. "
            "Aksi halde görev yapman engellenir ve kazandığın GRAM iptal edilir.",
            reply_markup=earn_categories(),
            parse_mode="HTML"
        )
        return
    
    # Basit gösterim (geliştirilebilir)
    text = f"📋 <b>{cat.upper()} görevleri</b>\n\n"
    kb = []
    for task in tasks[:5]:
        text += f"• {task[3]} → +{task[6]} GRAM\n"
        kb.append([InlineKeyboardButton(
            text=f"✅ {task[3][:30]}",
            callback_data=f"do_{task[0]}"
        )])
    
    kb.append([InlineKeyboardButton(text="🔙 Geri", callback_data="earn")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")

@dp.callback_query(F.data == "promote")
async def promote_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "📢 <b>Ne tanıtmak istiyorsun?</b>",
        reply_markup=promote_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "profile")
async def profile_handler(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Kullanıcı bulunamadı", show_alert=True)
        return
    
    text = (
        f"👤 <b>Kabin:</b>\n\n"
        f"🆔 Kimliğim: <code>{user[0]}</code>\n"
        f"🐣 Seviye: Acemi {user[5]}/500 XP\n"
        f"💰 Bakiye: <b>{user[3]} GRAM</b>"
    )
    await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "rules")
async def rules_handler(callback: CallbackQuery):
    text = (
        "📌 <b>Kurallar</b>\n\n"
        "1. Görev yaptıktan sonra kanaldan/gruptan <b>7 gün</b> boyunca çıkma.\n"
        "2. 7 günden önce çıkarsan kazandığın GRAM geri alınır.\n"
        "3. Sahte abonelik / bot kullanımı yasaktır.\n"
        "4. Herkes kendi görevini ekleyebilir.\n"
        "5. Bakiye hiçbir zaman kaybolmaz."
    )
    await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "referral")
async def referral_handler(callback: CallbackQuery):
    link = f"https://t.me/{(await bot.get_me()).username}?start={callback.from_user.id}"
    text = (
        f"🔗 <b>Referans Linkin:</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"Arkadaşlarını davet et, onlar görev yaptıkça sen de GRAM kazan!"
    )
    await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")

# ==================== BAŞLATMA ====================
async def main():
    await init_db()
    print("Bot başlatıldı...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
