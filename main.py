import os
import re
import shutil
from datetime import datetime
from telegram import ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 255196166
FILE_NAME = "codes.txt"
BACKUP_FOLDER = "backups"

admin_mode = False

# ===== CREATE BACKUP =====
def create_backup():
    if not os.path.exists(FILE_NAME):
        return

    if not os.path.exists(BACKUP_FOLDER):
        os.makedirs(BACKUP_FOLDER)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = os.path.join(BACKUP_FOLDER, f"backup_{timestamp}.txt")

    shutil.copy(FILE_NAME, backup_file)

    # فقط 5 بکاپ آخر نگه دارد
    backups = sorted(os.listdir(BACKUP_FOLDER))
    if len(backups) > 5:
        os.remove(os.path.join(BACKUP_FOLDER, backups[0]))

# ===== LOAD CODES =====
def load_codes():
    if not os.path.exists(FILE_NAME):
        return []
    with open(FILE_NAME, "r") as f:
        return [line.strip() for line in f if line.strip()]

# ===== SAVE CODES =====
def save_codes(codes):
    with open(FILE_NAME, "w") as f:
        for code in codes:
            f.write(code + "\n")

    create_backup()

# ===== MENU =====
def menu():
    keyboard = [
        ["➕ Add Codes"],
        ["🎁 Get Code"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ===== START =====
def start(update, context):
    update.message.reply_text("UC Manager with Auto Backup 👑", reply_markup=menu())

# ===== TEXT HANDLER =====
def text_handler(update, context):
    global admin_mode

    user_id = update.effective_user.id
    text = update.message.text.strip()

    # ===== ADD MODE =====
    if text == "➕ Add Codes" and user_id == ADMIN_ID:
        admin_mode = True
        update.message.reply_text("Send all codes now (multi-line supported)")
        return

    if admin_mode and user_id == ADMIN_ID:

        try:
            update.message.delete()
        except:
            pass

        codes = load_codes()

        clean_text = text.replace("\u200b", "").replace("\ufeff", "")
        new_codes = re.split(r'\s+', clean_text)

        added = 0

        for code in new_codes:
            code = code.strip()
            if len(code) < 5:
                continue

            if code not in codes:
                codes.append(code)
                added += 1

        save_codes(codes)
        admin_mode = False

        context.bot.send_message(
            update.effective_chat.id,
            f"✅ {added} Codes Added\n📦 Total Stored: {len(codes)}"
        )
        return

    # ===== GET CODE =====
    if text == "🎁 Get Code":

        codes = load_codes()

        if not codes:
            update.message.reply_text("❌ No codes available")
            return

        code = codes.pop(0)
        save_codes(codes)

        update.message.reply_text(
            f"🎁 Your Code:\n{code}\n\n📦 Remaining: {len(codes)}"
        )

# ===== MAIN =====
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
