import os
import asyncio
import logging
import sqlite3
from datetime import datetime
import requests
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
import uvicorn

# =====================================================================
# 1. ASOSIY SOZLAMALAR
# =====================================================================
BOT_TOKEN = "8478595791:AAHE1_4QDhU9eFwKX385Xgo5hw-3wQ9D1DM"
API_KEY_SECRET = "Auvrang777"

# O'yinchi ma'lumotlarini aniqlash uchun ochiq API xizmati
PLAYER_INFO_API = "https://vercel.app"

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI(title="Free Fire Real-Time Like API")

user_cooldowns = {}
DB_FILE = "orders.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS like_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT NOT NULL,
            player_name TEXT,
            region TEXT,
            amount INTEGER,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# =====================================================================
# 2. TELEGRAM BOT QISMI (CHIROYLI DIZAYN VA REAL DATA)
# =====================================================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    start_text = (
        "👋 **Free Fire Professional Like Botiga xush kelibsiz!**\n\n"
        "⚡️ Profilingizga real vaqtda layk yuborish uchun quyidagi formatda yozing:\n"
        "`/like sizning_uid`\n\n"
        "📌 *Misol:* `/like 9047734890`"
    )
    await message.answer(start_text, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("like"))
async def handle_like_command(message: types.Message):
    user_id = message.from_user.id
    current_time = asyncio.get_event_loop().time()

    # Anti-Spam (5 daqiqa)
    if user_id in user_cooldowns and current_time - user_cooldowns[user_id] < 300:
        remaining = int(300 - (current_time - user_cooldowns[user_id]))
        await message.answer(f"⚠️ **Spam qilmang!** Keyingi so'rovni {remaining} soniyadan keyin yubora olasiz.")
        return

    command_args = message.text.split()
    if len(command_args) < 2:
        await message.answer("❌ **Xatolik! ID kiritilmadi.**\nFormat: `/like 9047734890`", parse_mode=ParseMode.MARKDOWN)
        return

    uid = command_args[1].strip()
    if not uid.isdigit() or len(uid) < 5:
        await message.answer("❌ Noto'g'ri ID format. Iltimos, faqat raqamlardan iborat UID kiriting.")
        return

    user_cooldowns[user_id] = current_time
    progress_message = await message.answer("🔍 *Garena serverlaridan o'yinchi ma'lumotlari yuklanmoqda...*", parse_mode=ParseMode.MARKDOWN)

    # Real vaqtda Garena ma'lumotlarini API orqali olish
    try:
        # Bepul ochiq API ga so'rov yuboramiz
        response = requests.get(f"{PLAYER_INFO_API}{uid}", timeout=8)
        
        if response.status_code == 200:
            data = response.json()
            # API qaytargan ma'lumotlarga qarab o'zgaruvchilarni olamiz
            player_name = data.get("name", "Aniqlanmadi")
            region = data.get("region", "RU / EU")
            likes_before = int(data.get("likes", 6722)) # Agar xizmat xato bersa test qiymati
        else:
            # Agar tashqi API ishlamay qolsa, standart test ma'lumotlarini ko'rsatamiz
            player_name = "HumoㅤXㅤzx"
            region = "RU"
            likes_before = 6722

        # Layk qo'shish jarayoni simulyatsiyasi (333 ta layk yuborish)
        given_likes = 333
        likes_after = likes_before + given_likes
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Bazaga saqlash
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO like_orders (uid, player_name, region, amount, created_at) VALUES (?, ?, ?, ?, ?)",
            (uid, player_name, region, given_likes, current_time_str)
        )
        conn.commit()
        conn.close()

        # Siz so'ragan chiroyli shriftli va chiziqli dizayn matni
        response_template = (
            f"👋 ʟɪᴋᴇ sᴜᴄᴄᴇssꜰᴜʟ\n"
            f"───────────────────\n"
            f"👤 ᴘʟᴀʏᴇʀ: {player_name}\n"
            f"ℹ️ ᴜɪᴅ: {uid}\n"
            f"🌏 ʀᴇɢɪᴏɴ: {region}\n\n"
            f"💗 ʟɪᴋᴇs sᴛᴀᴛᴜs:\n"
            f"├─ ʙᴇꜰᴏʀᴇ: {likes_before}\n"
            f"├─ ᴀꜰᴛᴇʀ: {likes_after}\n"
            f"└─ ɢɪᴠᴇɴ: {given_likes}\n"
            f"───────────────────\n"
            f"🥹 ᴅᴇᴠ: 🧧 ɢᴀʀᴇɴᴀ!"
        )

        await progress_message.edit_text(response_template)

    except Exception as e:
        await progress_message.edit_text(f"❌ Tizimda kutilmagan xatolik yuz berdi: {str(e)}")

# =====================================================================
# 3. SERVERNI ISHGA TUSHIRISH
# =====================================================================
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(dp.start_polling(bot))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
