import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.exceptions import TelegramBadRequest

import config
import database as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


# ============================================================
#  FSM STATES (admin görev ekleme sihirbazı)
# ============================================================

class AddTask(StatesGroup):
    title = State()
    type_ = State()
    target = State()
    url = State()


class SetReward(StatesGroup):
    waiting_link = State()


# ============================================================
#  KLAVYELER
# ============================================================

def task_list_keyboard(tasks, progress_map):
    kb = []
    for t in tasks:
        status = progress_map.get(t["id"], "bekliyor")
        icon = {"onaylandi": "✅", "inceleniyor": "⏳", "reddedildi": "❌"}.get(status, "🔲")
        kb.append([InlineKeyboardButton(text=f"{icon} {t['title']}", callback_data=f"task_{t['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def task_detail_keyboard(task):
    kb = [
        [InlineKeyboardButton(text="🔗 Linke Git", url=task["url"])],
    ]
    if task["type"] == "kanal":
        kb.append([InlineKeyboardButton(text="✅ Katıldım, Kontrol Et", callback_data=f"check_{task['id']}")])
    else:
        kb.append([InlineKeyboardButton(text="✅ Yaptım, Kanıt Gönder", callback_data=f"proof_{task['id']}")])
    kb.append([InlineKeyboardButton(text="⬅️ Görev Listesi", callback_data="back_list")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_review_keyboard(user_id, task_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Onayla", callback_data=f"adminok_{user_id}_{task_id}"),
        InlineKeyboardButton(text="❌ Reddet", callback_data=f"adminno_{user_id}_{task_id}"),
    ]])


# ============================================================
#  KULLANICI AKIŞI
# ============================================================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    tasks = await db.get_active_tasks()
    if not tasks:
        await message.answer("Şu anda aktif görev bulunmuyor. Daha sonra tekrar dene.")
        return

    if await db.all_tasks_approved(message.from_user.id):
        await send_reward(message.from_user.id)
        return

    progress_map = await db.get_user_progress_map(message.from_user.id)
    await message.answer(
        "👋 Hoş geldin!\n\nÖdülü almak için aşağıdaki görevleri tamamla:",
        reply_markup=task_list_keyboard(tasks, progress_map)
    )


@router.callback_query(F.data == "back_list")
async def back_list(call: CallbackQuery):
    tasks = await db.get_active_tasks()
    progress_map = await db.get_user_progress_map(call.from_user.id)
    await call.message.edit_text("Görev listesi:", reply_markup=task_list_keyboard(tasks, progress_map))
    await call.answer()


@router.callback_query(F.data.startswith("task_"))
async def show_task(call: CallbackQuery):
    task_id = int(call.data.split("_")[1])
    task = await db.get_task(task_id)
    if not task or not task["active"]:
        await call.answer("Bu görev artık aktif değil.", show_alert=True)
        return
    await call.message.edit_text(
        f"📌 <b>{task['title']}</b>\n\nAşağıdaki linke git, ardından ilgili butona bas.",
        reply_markup=task_detail_keyboard(task),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("check_"))
async def check_membership(call: CallbackQuery):
    task_id = int(call.data.split("_")[1])
    task = await db.get_task(task_id)
    if not task:
        await call.answer("Görev bulunamadı.", show_alert=True)
        return

    try:
        member = await bot.get_chat_member(chat_id=task["target"], user_id=call.from_user.id)
        if member.status in ("member", "administrator", "creator"):
            await db.set_progress(call.from_user.id, task_id, "onaylandi")
            await call.answer("✅ Katılımın doğrulandı!", show_alert=True)
            if await db.all_tasks_approved(call.from_user.id):
                await send_reward(call.from_user.id)
            else:
                await back_list(call)
        else:
            await call.answer("❌ Henüz katılmamışsın. Katıldıktan sonra tekrar dene.", show_alert=True)
    except TelegramBadRequest as e:
        logger.warning(f"getChatMember hata: {e}")
        await call.answer("Kontrol edilemedi. Botun o kanalda/grupta admin olduğundan emin ol.", show_alert=True)


@router.callback_query(F.data.startswith("proof_"))
async def ask_proof(call: CallbackQuery, state: FSMContext):
    task_id = int(call.data.split("_")[1])
    task = await db.get_task(task_id)
    if not task:
        await call.answer("Görev bulunamadı.", show_alert=True)
        return
    await state.update_data(proof_task_id=task_id)
    await call.message.answer("📸 Lütfen bu görevi tamamladığına dair ekran görüntüsünü gönder (fotoğraf olarak).")
    await call.answer()


@router.message(F.photo)
async def receive_proof(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = data.get("proof_task_id")
    if not task_id:
        return  # ilgisiz fotoğraf, görmezden gel

    task = await db.get_task(task_id)
    if not task:
        await message.answer("Bu görev artık bulunmuyor.")
        return

    photo_file_id = message.photo[-1].file_id
    await db.set_progress(message.from_user.id, task_id, "inceleniyor", photo_file_id)
    await state.update_data(proof_task_id=None)

    await message.answer("📤 Kanıtın gönderildi, incelemeye alındı. Onaylanınca haber vereceğim.")

    uname = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    caption = (
        f"🆕 <b>Kanıt İncelemesi</b>\n"
        f"Kullanıcı: {uname} (ID: <code>{message.from_user.id}</code>)\n"
        f"Görev: {task['title']} (ID: {task_id})"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_photo(
                admin_id, photo_file_id, caption=caption, parse_mode="HTML",
                reply_markup=admin_review_keyboard(message.from_user.id, task_id)
            )
        except Exception as e:
            logger.warning(f"Admin {admin_id}'e gönderilemedi: {e}")


async def send_reward(user_id: int):
    reward = await db.get_setting("reward_link")
    if reward:
        await bot.send_message(user_id, f"🎉 Tebrikler, tüm görevleri tamamladın!\n\nÖdülün: {reward}")
    else:
        await bot.send_message(user_id, "🎉 Tebrikler, tüm görevleri tamamladın! (Ödül linki henüz ayarlanmamış)")


# ============================================================
#  ADMIN: onay / red
# ============================================================

@router.callback_query(F.data.startswith("adminok_"))
async def admin_approve(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Yetkin yok.", show_alert=True)
        return
    _, user_id, task_id = call.data.split("_")
    user_id, task_id = int(user_id), int(task_id)

    await db.set_progress(user_id, task_id, "onaylandi")
    await call.message.edit_caption(caption=call.message.caption + "\n\n✅ ONAYLANDI", parse_mode="HTML")
    await call.answer("Onaylandı.")

    task = await db.get_task(task_id)
    await bot.send_message(user_id, f"✅ '{task['title']}' göreviniz onaylandı!")

    if await db.all_tasks_approved(user_id):
        await send_reward(user_id)


@router.callback_query(F.data.startswith("adminno_"))
async def admin_reject(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Yetkin yok.", show_alert=True)
        return
    _, user_id, task_id = call.data.split("_")
    user_id, task_id = int(user_id), int(task_id)

    await db.set_progress(user_id, task_id, "reddedildi")
    await call.message.edit_caption(caption=call.message.caption + "\n\n❌ REDDEDİLDİ", parse_mode="HTML")
    await call.answer("Reddedildi.")

    task = await db.get_task(task_id)
    await bot.send_message(user_id, f"❌ '{task['title']}' göreviniz reddedildi. Doğru kanıtla tekrar deneyebilirsin: /start")


# ============================================================
#  ADMIN: görev ekleme sihirbazı
# ============================================================

@router.message(Command("gorevekle"))
async def add_task_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AddTask.title)
    await message.answer("Görev başlığı nedir? (kullanıcıya gösterilecek isim)")


@router.message(AddTask.title)
async def add_task_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddTask.type_)
    await message.answer(
        "Görev tipi ne?\n"
        "• <code>kanal</code> — bot otomatik kontrol eder (botu o kanala admin ekle)\n"
        "• <code>bot</code> — kullanıcı ekran görüntüsü gönderir, sen onaylarsın",
        parse_mode="HTML"
    )


@router.message(AddTask.type_)
async def add_task_type(message: Message, state: FSMContext):
    ttype = message.text.strip().lower()
    if ttype not in ("kanal", "bot"):
        await message.answer("Lütfen sadece 'kanal' ya da 'bot' yaz.")
        return
    await state.update_data(type_=ttype)
    if ttype == "kanal":
        await state.set_state(AddTask.target)
        await message.answer(
            "Kanalın/grubun kullanıcı adını (@kanaladi) ya da chat ID'sini gönder.\n"
            "⚠️ Bu botu o kanala/gruba ADMİN olarak eklemeyi unutma, yoksa kontrol çalışmaz."
        )
    else:
        await state.update_data(target=None)
        await state.set_state(AddTask.url)
        await message.answer("Kullanıcının gideceği linki gönder (örn. https://t.me/digerbot):")


@router.message(AddTask.target)
async def add_task_target(message: Message, state: FSMContext):
    await state.update_data(target=message.text.strip())
    await state.set_state(AddTask.url)
    await message.answer("Kullanıcıya gösterilecek link nedir? (kanala davet linki)")


@router.message(AddTask.url)
async def add_task_url(message: Message, state: FSMContext):
    data = await state.get_data()
    task_id = await db.add_task(
        title=data["title"],
        ttype=data["type_"],
        target=data.get("target"),
        url=message.text.strip()
    )
    await state.clear()
    await message.answer(f"✅ Görev eklendi (ID: {task_id}).")


@router.message(Command("gorevler"))
async def list_tasks_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    tasks = await db.get_all_tasks()
    if not tasks:
        await message.answer("Henüz görev yok.")
        return
    lines = []
    for t in tasks:
        durum = "aktif" if t["active"] else "pasif"
        lines.append(f"#{t['id']} [{t['type']}] {t['title']} — {durum}")
    await message.answer("\n".join(lines))


@router.message(Command("gorevsil"))
async def delete_task_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Kullanım: /gorevsil <id>")
        return
    await db.delete_task(int(parts[1]))
    await message.answer("Görev pasif hale getirildi.")


@router.message(Command("odulayarla"))
async def set_reward_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(SetReward.waiting_link)
    await message.answer("Tüm görevler bitince kullanıcıya gösterilecek ÖDÜL linkini gönder:")


@router.message(SetReward.waiting_link)
async def set_reward_finish(message: Message, state: FSMContext):
    await db.set_setting("reward_link", message.text.strip())
    await state.clear()
    await message.answer("✅ Ödül linki kaydedildi.")


@router.message(Command("yardim"))
async def help_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Görevleri görmek için /start yaz.")
        return
    await message.answer(
        "<b>Admin Komutları</b>\n"
        "/gorevekle — yeni görev ekle\n"
        "/gorevler — tüm görevleri listele\n"
        "/gorevsil ID — görevi pasif yap\n"
        "/odulayarla — final ödül linkini belirle\n",
        parse_mode="HTML"
    )


# ============================================================
#  RENDER İÇİN: canlılık kontrolü (health check) web sunucusu
# ============================================================

async def start_web_server():
    from aiohttp import web
    import os

    async def health(request):
        return web.Response(text="Bot çalışıyor.")

    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health-check sunucusu {port} portunda başladı.")


async def main():
    await db.init_db()
    await start_web_server()
    logger.info("Bot başlatılıyor (polling)...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
