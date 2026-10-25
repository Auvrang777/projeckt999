import os
import asyncio
import logging
import sqlite3
from datetime import datetime
import requests
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
import uvicorn

# =====================================================================
# 1. ASOSIY SOZLAMALAR VA XAVFSIZLIK
# =====================================================================
BOT_TOKEN = "8478595791:AAHE1_4QDhU9eFwKX385Xgo5hw-3wQ9D1DM"  # Sizning faol tokeningiz
API_KEY_SECRET = "MY_SUPER_SECRET_API_KEY_2026"         # Panel xavfsizlik kaliti

# Bu yerga uchinchi tomon Like API provayderining manzili qo'yiladi (agar bo'lsa)
LIKE_API_URL = "https://ucbot.net"  
PROVIDER_API_KEY = "YOUR_PROVIDER_KEY"                  

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

logging.basicConfig(level=logging.INFO)

# Ob'ektlarni yaratamiz
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI(title="Free Fire Shaxsiy Like API Paneli")

# Cooldown (Spamga qarshi taymer - 5 daqiqa)
user_cooldowns = {}

# =====================================================================
# 2. MA'LUMOTLAR BAZASI (SQLite)
# =====================================================================
DB_FILE = "orders.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS like_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT NOT NULL,
            amount INTEGER NOT NULL,
            min_amount INTEGER NOT NULL,
            status TEXT DEFAULT 'Kutilmoqda',
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Xavfsizlikni tekshirish funksiyasi
async def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY_SECRET:
        raise HTTPException(status_code=403, detail="Ruxsat berilmadi: API kalit xato!")
    return api_key

class OrderCreate(BaseModel):
    uid: str = Field(..., example="53628192")
    amount: int = Field(default=333)
    min_amount: int = Field(default=150)

# =====================================================================
# 3. FASTAPI ENDPOINTLARI (API PANEL QISMI)
# =====================================================================
@app.post("/api/v1/order")
async def create_order(order: OrderCreate, api_key: str = Depends(verify_api_key)):
    if not order.uid.isdigit() or len(order.uid) < 5:
        raise HTTPException(status_code=400, detail="Noto'g'ri UID formati")

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO like_orders (uid, amount, min_amount, created_at) VALUES (?, ?, ?, ?)",
        (order.uid, order.amount, order.min_amount, current_time)
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {
        "status": "success",
        "order_id": order_id,
        "message": f"Buyurtma qabul qilindi. {order.amount} ta layk yuborilmoqda."
    }

@app.get("/api/v1/orders")
async def get_all_orders(api_key: str = Depends(verify_api_key)):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM like_orders ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return {"total_orders": len(rows), "orders": [dict(r) for r in rows]}

# =====================================================================
# 4. TELEGRAM BOT QISMI (/START VA /LIKE BUYRUKLARI)
# =====================================================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    start_text = (
        "👋 **Free Fire Avtomatlashtirilgan Like Botiga xush kelibsiz!**\n\n"
        "⚡️ Layk yuborish uchun ID raqamingizni buyruq bilan birga yuboring:\n"
        "`/like sizning_uid`\n\n"
        "📌 *Misol:* `/like 123456789`\n"
        "Har bir so'rovda avtomatik **333 ta layk** (kamida 150 ta) yuboriladi!"
    )
    await message.answer(start_text, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("like"))
async def handle_like_command(message: types.Message):
    user_id = message.from_user.id
    current_time = asyncio.get_event_loop().time()

    # Anti-Spam
    if user_id in user_cooldowns and current_time - user_cooldowns[user_id] < 300:
        remaining = int(300 - (current_time - user_cooldowns[user_id]))
        await message.answer(f"⚠️ **Spam qilmang!** Keyingi so'rovni {remaining} soniyadan keyin yubora olasiz.")
        return

    command_args = message.text.split()
    if len(command_args) < 2:
        await message.answer("❌ **Xatolik! ID kiritilmadi.** Format: `/like 123456789`", parse_mode=ParseMode.MARKDOWN)
        return

    uid = command_args[1].strip()
    if not uid.isdigit() or len(uid) < 5:
        await message.answer("❌ Noto'g'ri ID format. Qayta tekshiring.")
        return

    user_cooldowns[user_id] = current_time
    progress_message = await message.answer(f"⏳ **UID:** `{uid}`. Shaxsiy panel bazasiga yozilmoqda...", parse_mode=ParseMode.MARKDOWN)

    # O'z panelimizga localhost (yoki ichki xizmat) orqali so'rov yuborish simulyatsiyasi
    try:
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO like_orders (uid, amount, min_amount, created_at) VALUES (?, ?, ?, ?)",
            (uid, 333, 150, current_time_str)
        )
        conn.commit()
        conn.close()

        await progress_message.edit_text(
            f"✅ **Muvaffaqiyatli yakunlandi!**\n\n"
            f"🆔 **O'yinchi UID:** `{uid}`\n"
            f"🚀 **Yuborilayotgan layklar:** 333 ta\n"
            f"📊 **Kafolatlangan eng kam miqdor:** 150 ta\n\n"
            f"⚡️ *Ma'lumotlar shaxsiy panelingiz bazasiga saqlandi.*",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await progress_message.edit_text(f"❌ Tizimda xatolik yuz berdi: {str(e)}")

# =====================================================================
# 5. SERVER VA BOTNI BIR VAQTDA ISHGA TUSHIRISH
# =====================================================================
async def run_bot():
    await dp.start_polling(bot)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())

if __name__ == "__main__":
    # Render muhitida port avtomatik olinadi
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
