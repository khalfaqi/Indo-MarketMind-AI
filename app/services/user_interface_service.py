import asyncio
import uuid
import httpx
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from app.config.settings import settings


# ── In-memory session store ──────────────────────────────────────────────────
sessions: dict[int, dict] = {}

SESSION_TIMEOUT = 10 * 60  # 10 menit dalam detik
CHAT_API_URL = "http://localhost:8000/chat" 

# ── Helpers ──────────────────────────────────────────────────────────────────

def get_or_create_session(user_id: int) -> str:
    """Ambil thread_id aktif atau buat sesi baru."""
    now = datetime.utcnow()
    session = sessions.get(user_id)

    if session:
        elapsed = (now - session["last_active"]).total_seconds()
        if elapsed > SESSION_TIMEOUT:
            # Session expired → reset
            sessions[user_id] = {"thread_id": str(uuid.uuid4()), "last_active": now}
        else:
            sessions[user_id]["last_active"] = now
    else:
        sessions[user_id] = {"thread_id": str(uuid.uuid4()), "last_active": now}

    return sessions[user_id]["thread_id"]


def reset_session(user_id: int) -> str:
    """Force reset session, kembalikan thread_id baru."""
    new_thread_id = str(uuid.uuid4())
    sessions[user_id] = {"thread_id": new_thread_id, "last_active": datetime.utcnow()}
    return new_thread_id


# ── Background task: sweep expired sessions ──────────────────────────────────

async def session_cleanup_loop():
    """Hapus session yang expired dari memori setiap 5 menit."""
    while True:
        await asyncio.sleep(5 * 60)
        now = datetime.utcnow()
        expired = [
            uid for uid, data in sessions.items()
            if (now - data["last_active"]).total_seconds() > SESSION_TIMEOUT
        ]
        for uid in expired:
            del sessions[uid]


# ── Handlers ─────────────────────────────────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    thread_id = reset_session(user_id)
    await update.message.reply_text(
        "👋 Halo! Saya *MarketMind*, asisten pasar saham kamu.\n\n"
        "Tanyakan apapun tentang saham, misalnya:\n"
        "• _Harga BBCA sekarang berapa?_\n"
        "• _Bandingkan TLKM dengan EXCL_\n\n"
        "Sesi akan otomatis direset jika tidak ada aktivitas selama *10 menit*.",
        parse_mode="Markdown"
    )


async def reset_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    reset_session(user_id)
    await update.message.reply_text(
        "🔄 Sesi percakapan kamu telah direset. Mulai topik baru sekarang!"
    )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    thread_id = get_or_create_session(user_id)

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                CHAT_API_URL,
                json={"question": user_text, "thread_id": thread_id}
            )
            response.raise_for_status()
            data = response.json()

        answer = data.get("answer", "Maaf, tidak ada jawaban.")
        await update.message.reply_text(answer)

    except httpx.TimeoutException:
        await update.message.reply_text(
            "⏱️ Request timeout. Server sedang sibuk, coba lagi sebentar."
        )
    except httpx.HTTPStatusError as e:
        await update.message.reply_text(
            f"❌ Server error: {e.response.status_code}. Coba lagi nanti."
        )
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Terjadi kesalahan: {str(e)}"
        )


# ── Entry point ───────────────────────────────────────────────────────────────

async def run_bot():
    app = Application.builder().token(settings.TELE_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("reset", reset_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    asyncio.create_task(session_cleanup_loop()) 

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    await asyncio.Event().wait()

