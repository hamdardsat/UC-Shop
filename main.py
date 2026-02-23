import os
import sqlite3
import re
from telegram import ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 255196166  # آیدی عددی خودت را بگذار

PACKAGES = ["60", "325", "660", "1800", "3850", "8100"]

# ================= DATABASE =================
conn = sqlite3.connect("codes.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS codes (
    code TEXT PRIMARY KEY,
    package TEXT,
    status TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    package TEXT,
    code TEXT,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()

admin_state = {}

# ================= MENUS =================
def main_menu(is_admin=False):
    keyboard = [
        ["📦 60 UC", "📦 325 UC"],
        ["📦 660 UC", "📦 1800 UC"],
        ["📦 3850 UC", "📦 8100 UC"],
        ["📊 Stock"]
    ]
    if is_admin:
        keyboard.append(["➕ Add Codes"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def package_menu():
    keyboard = [
        ["60", "325"],
        ["660", "1800"],
        ["3850", "8100"],
        ["🔙 Cancel"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ================= START =================
def start(update, context):
    if update.effective_chat.type not in ["group", "supergroup"]:
        return

    is_admin = update.effective_user.id == ADMIN_ID

    update.message.reply_text(
        "UC Group Bot Ready 👑",
        reply_markup=main_menu(is_admin)
    )

# ================= TEXT HANDLER =================
def text_handler(update, context):
    if update.effective_chat.type not in ["group", "supergroup"]:
        return

    user = update.effective_user
    text = update.message.text.strip()
    is_admin = user.id == ADMIN_ID

    # ===== ADD BUTTON =====
    if text == "➕ Add Codes" and is_admin:
        admin_state[user.id] = {"step": "select_package"}
        update.message.reply_text("Select package:", reply_markup=package_menu())
        return

    # ===== CANCEL =====
    if text == "🔙 Cancel":
        admin_state.pop(user.id, None)
        update.message.reply_text("Cancelled", reply_markup=main_menu(is_admin))
        return

    # ===== PACKAGE SELECT SAFE =====
    if user.id in admin_state and admin_state[user.id]["step"] == "select_package":

        selected_package = re.sub(r'\D', '', text.strip())

        if selected_package not in PACKAGES:
            update.message.reply_text("Invalid package ❌")
            return

        admin_state[user.id] = {"step": "add_codes", "package": selected_package}
        update.message.reply_text(f"Send ALL codes for {selected_package} UC")
        return

    # ===== ADD MULTIPLE CODES SAFE =====
    if user.id in admin_state and admin_state[user.id]["step"] == "add_codes":

        package = admin_state[user.id]["package"]

        # حذف پیام ادمین تا کدها دیده نشود
        try:
            update.message.delete()
        except:
            pass

        clean_text = text.replace("\u200b", "").replace("\ufeff", "")
        codes = re.split(r'\s+', clean_text)

        added = 0
        duplicate = 0

        for code in codes:
            code = code.strip()

            if len(code) < 5:
                continue

            cursor.execute(
                "INSERT OR IGNORE INTO codes (code, package, status) VALUES (?, ?, 'available')",
                (code, package)
            )

            if cursor.rowcount == 1:
                added += 1
            else:
                duplicate += 1

        conn.commit()
        admin_state.pop(user.id, None)

        context.bot.send_message(
            update.effective_chat.id,
            f"✅ {added} Codes Added Successfully",
            reply_markup=main_menu(is_admin)
        )
        return

    # ===== DELIVER CODE =====
    if text.startswith("📦"):
        package = re.sub(r'\D', '', text)
        deliver_code(update, package)
        return

    # ===== STOCK =====
    if text == "📊 Stock":
        show_stock(update)
        return

# ================= DELIVER CODE =================
def deliver_code(update, package):

    if package not in PACKAGES:
        return

    cursor.execute(
        "SELECT code FROM codes WHERE package=? AND status='available' LIMIT 1",
        (package,)
    )
    result = cursor.fetchone()

    if not result:
        update.message.reply_text("❌ Out of stock")
        return

    code = result[0]
    cursor.execute("UPDATE codes SET status='used' WHERE code=?", (code,))

    user = update.effective_user
    username = user.username if user.username else user.full_name

    cursor.execute(
        "INSERT INTO logs (user_id, username, package, code) VALUES (?, ?, ?, ?)",
        (user.id, username, package, code)
    )

    conn.commit()

    update.message.reply_text(
        f"""🎁 {package} UC Delivered

👤 User: {username}
🔑 Code: {code}
"""
    )

# ================= STOCK =================
def show_stock(update):
    message = "📦 STOCK STATUS\n\n"

    for pkg in PACKAGES:
        cursor.execute(
            "SELECT COUNT(*) FROM codes WHERE package=? AND status='available'",
            (pkg,)
        )
        count = cursor.fetchone()[0]
        message += f"{pkg} UC → {count}\n"

    update.message.reply_text(message)

# ================= MAIN =================
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, text_handler))

    updater.bot.delete_webhook(drop_pending_updates=True)
    updater.start_polling(drop_pending_updates=True)
    updater.idle()

if __name__ == "__main__":
    main()
