# bot.py

import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.enums import ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, REWARDS
from database import (
    init_db, get_user, create_user, update_balance, get_balance,
    get_active_tasks, get_task, add_completion, check_completion, create_task
)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ==================== STATES ====================
class AddTask(StatesGroup):
    waiting_link = State()
    waiting_title = State()

# ==================== KEYBOARDS ====================
def main_menu():
    kb = [
        [InlineKeyboardButton(text="💰 Kazanç", callback_data="earn"),
         InlineKeyboardButton(text="📢 Tanıt", callback_data="promote")],
        [InlineKeyboardButton(text="👤 Hesabım", callback_data="profile"),
         InlineKeyboardButton(text="📌 Kurallar", callback_data="rules")],
        [InlineKeyboardButton(text="🔗 Referans", callback_data="referral")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def earn_categories():
    kb = [
        [InlineKeyboardButton(text="📢 Kanallar", callback_data="cat_channel"),
         InlineKeyboardButton(text="👥 Gruplar", callback_data="cat_group")],
        [InlineKeyboardButton(text="🤖 Botlar", callback_data="cat_bot"),
         InlineKeyboardButton(text="👁 Görüntülenme", callback_data="cat_view")],
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

def task_keyboard(task_id: int, link: str):
    kb = [
        [InlineKeyboardButton(text="✅ Abone Ol", url=link)],
        [InlineKeyboardButton(text="🔄 Kontrol Et", callback_data=f"check_{task_id}")],
        [InlineKeyboardButton(text="🔙 Geri", callback_data="earn")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ İptal", callback_data="cancel_add")]
    ])

# ==================== HANDLERS ====================
@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
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
        f"Görev yap, GRAM kazan, kendi kanalını tanıt!"
    )
    await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Ana menü", reply_markup=main_menu())

@dp.callback_query(F.data == "cancel_add")
async def cancel_add(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("İptal edildi.", reply_markup=main_menu())

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
            "⚠️ Kanallardan / Gruplardan 7 günden önce ayrılma.\n"
            "Aksi halde görev yapman engellenir ve kazandığın GRAM iptal edilir.",
            reply_markup=earn_categories(),
            parse_mode="HTML"
        )
        return
    
    text = f"📋 <b>{cat.upper()} Görevleri</b>\n\n"
    kb = []
    
    for task in tasks[:8]:
        task_id, _, _, title, link, _, reward, *_ = task
        text += f"• {title} → <b>+{reward} GRAM</b>\n"
        kb.append([InlineKeyboardButton(
            text=f"✅ {title[:25]} (+{reward})",
            callback_data=f"task_{task_id}"
        )])
    
    kb.append([InlineKeyboardButton(text="🔙 Geri", callback_data="earn")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")

@dp.callback_query(F.data.startswith("task_"))
async def show_task(callback: CallbackQuery):
    task_id = int(callback.data.replace("task_", ""))
    task = await get_task(task_id)
    
    if not task:
        await callback.answer("Görev bulunamadı", show_alert=True)
        return
    
    _, _, _, title, link, _, reward, *_ = task
    
    text = (
        f"📌 <b>{title}</b>\n\n"
        f"Ödül: <b>+{reward} GRAM</b>\n\n"
        f"1. Aşağıdaki butona tıkla ve abone ol\n"
        f"2. Sonra <b>Kontrol Et</b> butonuna bas"
    )
    await callback.message.edit_text(text, reply_markup=task_keyboard(task_id, link), parse_mode="HTML")

@dp.callback_query(F.data.startswith("check_"))
async def check_task(callback: CallbackQuery):
    task_id = int(callback.data.replace("check_", ""))
    user_id = callback.from_user.id
    
    if await check_completion(user_id, task_id):
        await callback.answer("Bu görevi zaten tamamladın!", show_alert=True)
        return
    
    task = await get_task(task_id)
    if not task:
        await callback.answer("Görev bulunamadı", show_alert=True)
        return
    
    _, _, task_type, title, link, chat_id, reward, *_ = task
    
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        
        if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            success = await add_completion(user_id, task_id)
            if success:
                await update_balance(user_id, reward)
                new_balance = await get_balance(user_id)
                
                await callback.message.edit_text(
                    f"✅ <b>Görev tamamlandı!</b>\n\n"
                    f"+{reward} GRAM kazandın\n"
                    f"Yeni bakiyen: <b>{new_balance} GRAM</b>\n\n"
                    f"⚠️ 7 günden önce ayrılma, yoksa GRAM geri alınır.",
                    reply_markup=main_menu(),
                    parse_mode="HTML"
                )
            else:
                await callback.answer("Bu görevi zaten yaptın!", show_alert=True)
        else:
            await callback.answer("❌ Henüz abone olmamışsın!", show_alert=True)
            
    except Exception as e:
        logging.error(f"Check error: {e}")
        await callback.answer(
            "❌ Kontrol başarısız!\n\n"
            "• Bot kanalda admin mi?\n"
            "• Link doğru mu?",
            show_alert=True
        )

# ==================== GÖREV EKLEME ====================
@dp.callback_query(F.data == "promote")
async def promote_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "📢 <b>Ne tanıtmak istiyorsun?</b>",
        reply_markup=promote_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.in_({"add_channel", "add_group", "add_bot", "add_view"}))
async def start_add_task(callback: CallbackQuery, state: FSMContext):
    task_type = callback.data.replace("add_", "")
    
    type_names = {
        "channel": "Kanal",
        "group": "Grup",
        "bot": "Bot",
        "view": "Gönderi"
    }
    
    await state.update_data(task_type=task_type)
    await state.set_state(AddTask.waiting_link)
    
    await callback.message.edit_text(
        f"📎 <b>{type_names.get(task_type, 'Görev')} linkini gönder</b>\n\n"
        f"Örnek:\n"
        f"• https://t.me/kanaladi\n"
        f"• https://t.me/+DavetKodu\n\n"
        f"Botun o kanalda/grupta <b>admin</b> olması gerekir!",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )

@dp.message(AddTask.waiting_link)
async def process_link(message: Message, state: FSMContext):
    link = message.text.strip()
    
    if not ("t.me/" in link or "telegram.me/" in link):
        await message.answer("❌ Geçerli bir Telegram linki gönder.", reply_markup=cancel_kb())
        return
    
    await state.update_data(link=link)
    await state.set_state(AddTask.waiting_title)
    
    await message.answer(
        "📝 Görev başlığını yaz (kısa olsun):\n\n"
        "Örnek: En iyi kripto kanalı",
        reply_markup=cancel_kb()
    )

@dp.message(AddTask.waiting_title)
async def process_title(message: Message, state: FSMContext):
    title = message.text.strip()[:50]
    data = await state.get_data()
    
    task_type = data.get("task_type")
    link = data.get("link")
    
    # chat_id'yi linkten doğru çıkar
    chat_id = link
    if "t.me/" in link:
        part = link.split("t.me/")[-1].split("?")[0].strip("/")
        if part.startswith("+"):
            # özel davet linki
            chat_id = link
        else:
            chat_id = "@" + part.lstrip("@")
    
    reward = REWARDS.get(task_type, 500)
    
    task_id = await create_task(
        owner_id=message.from_user.id,
        task_type=task_type,
        title=title,
        link=link,
        chat_id=chat_id,
        reward=reward
    )
    
    await state.clear()
    
    await message.answer(
        f"✅ <b>Görev başarıyla eklendi!</b>\n\n"
        f"Başlık: {title}\n"
        f"Ödül: +{reward} GRAM\n"
        f"Görev ID: {task_id}\n\n"
        f"Artık diğer kullanıcılar bu görevi yapabilir.\n\n"
        f"⚠️ Botu kanala/gruba <b>admin</b> olarak eklemeyi unutma!",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "profile")
async def profile_handler(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer("Kullanıcı bulunamadı", show_alert=True)
        return
    
    text = (
        f"👤 <b>Hesabım</b>\n\n"
        f"🆔 ID: <code>{user[0]}</code>\n"
        f"🐣 Seviye: Acemi\n"
        f"💰 Bakiye: <b>{user[3]} GRAM</b>"
    )
    await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "rules")
async def rules_handler(callback: CallbackQuery):
    text = (
        "📌 <b>Kurallar</b>\n\n"
        "1. Görev yaptıktan sonra kanaldan/gruptan <b>7 gün</b> boyunca çıkma.\n"
        "2. 7 günden önce çıkarsan kazandığın GRAM geri alınır.\n"
        "3. Sahte abonelik yasaktır.\n"
        "4. Görev eklerken botun kanalda admin olması gerekir.\n"
        "5. Bakiye hiçbir zaman kaybolmaz."
    )
    await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "referral")
async def referral_handler(callback: CallbackQuery):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={callback.from_user.id}"
    text = (
        f"🔗 <b>Referans Linkin:</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"Arkadaşlarını davet et, onlar görev yaptıkça sen de kazan!"
    )
    await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")

# ==================== BAŞLATMA ====================
async def main():
    await init_db()
    print("Bot başlatıldı...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
