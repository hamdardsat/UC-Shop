import os
import re
import shutil
from datetime import datetime
from telegram import ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 255196166

PACKAGES = ["60", "325", "660", "1800", "3850", "8100"]

DATA_FOLDER = "data"
BACKUP_FOLDER = "backups"

admin_mode = False
selected_package = None

# ===== SETUP FOLDERS =====
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

if not os.path.exists(BACKUP_FOLDER):
    os.makedirs(BACKUP_FOLDER)

# ===== FILE PATH =====
def file_path(pkg):
    return os.path.join(DATA_FOLDER, f"{pkg}.txt")

# ===== LOAD =====
def load_codes(pkg):
    path = file_path(pkg)
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return [line.strip() for line in f if line.strip()]

# ===== SAVE =====
def save_codes(pkg, codes):
    path = file_path(pkg)
    with open(path, "w") as f:
        for code in codes:
            f.write(code + "\n")
    create_backup(pkg)

# ===== BACKUP =====
def create_backup(pkg):
    src = file_path(pkg)
    if not os.path.exists(src):
        return

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dst = os.path.join(BACKUP_FOLDER, f"{pkg}_{timestamp}.txt")
    shutil.copy(src, dst)

# ===== MENUS =====
def main_menu():
    keyboard = [
        ["➕ Add Codes"],
        ["🎁 Get Code"],
        ["📦 Stock"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def package_menu():
    keyboard = []
    row = []
    for pkg in PACKAGES:
        row.append(pkg)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append(["🔙 Cancel"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ===== START =====
def start(update, context):
    update.message.reply_text("UC Package Manager 👑", reply_markup=main_menu())

# ===== TEXT HANDLER =====
def text_handler(update, context):
    global admin_mode, selected_package

    user_id = update.effective_user.id
    text = update.message.text.strip()

    # ===== ADD =====
    if text == "➕ Add Codes" and user_id == ADMIN_ID:
        admin_mode = True
        update.message.reply_text("Select package:", reply_markup=package_menu())
        return

    if admin_mode and text in PACKAGES:
        selected_package = text
        update.message.reply_text(f"Send codes for {text} UC")
        return

    if admin_mode and selected_package and user_id == ADMIN_ID:

        try:
            update.message.delete()
        except:
            pass

        codes = load_codes(selected_package)

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

        save_codes(selected_package, codes)

        update.message.reply_text(
            f"✅ {added} Codes Added to {selected_package}\n📦 Total: {len(codes)}",
            reply_markup=main_menu()
        )

        admin_mode = False
        selected_package = None
        return

    # ===== GET CODE =====
    if text == "🎁 Get Code":
        update.message.reply_text("Select package:", reply_markup=package_menu())
        return

    if text in PACKAGES:
        codes = load_codes(text)

        if not codes:
            update.message.reply_text("❌ Out of stock", reply_markup=main_menu())
            return

        code = codes.pop(0)
        save_codes(text, codes)

        update.message.reply_text(
            f"🎁 {text} UC Code:\n{code}\n\n📦 Remaining: {len(codes)}",
            reply_markup=main_menu()
        )
        return

    # ===== STOCK =====
    if text == "📦 Stock":
        message = "📦 STOCK STATUS\n\n"
        for pkg in PACKAGES:
            count = len(load_codes(pkg))
            message += f"{pkg} UC → {count}\n"
        update.message.reply_text(message)
        return

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
