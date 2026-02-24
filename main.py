import os
import re
from telegram import ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 255196166

PACKAGES = ["60", "325", "660", "1800", "3850", "8100"]
DATA_FOLDER = "data"

# ساخت پوشه اگر نبود
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# ===== فایل هر پکیج =====
def file_path(pkg):
    return os.path.join(DATA_FOLDER, f"{pkg}.txt")

def load_codes(pkg):
    path = file_path(pkg)
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return [line.strip() for line in f if line.strip()]

def save_codes(pkg, codes):
    with open(file_path(pkg), "w") as f:
        for c in codes:
            f.write(c + "\n")

# ===== وضعیت =====
admin_step = None
admin_package = None
user_step = {}

# ===== منیو اصلی =====
def main_menu():
    return ReplyKeyboardMarkup(
        [["➕ Add Codes"], ["🎁 Get Code"], ["📦 Stock"]],
        resize_keyboard=True
    )

# ===== منیو پکیج =====
def package_menu():
    return ReplyKeyboardMarkup(
        [["60", "325"], ["660", "1800"], ["3850", "8100"], ["🔙 Cancel"]],
        resize_keyboard=True
    )

# ===== start =====
def start(update, context):
    update.message.reply_text("UC Manager Ready 👑", reply_markup=main_menu())

# ===== handler =====
def text_handler(update, context):
    global admin_step, admin_package

    user_id = update.effective_user.id
    text = update.message.text.strip()

    # ===== ADD BUTTON =====
    if text == "➕ Add Codes" and user_id == ADMIN_ID:
        admin_step = "select_package"
        update.message.reply_text("Select package:", reply_markup=package_menu())
        return

    # ===== ADMIN SELECT PACKAGE =====
    if admin_step == "select_package" and text in PACKAGES:
        admin_package = text
        admin_step = "add_codes"
        update.message.reply_text(f"Send codes for {text} UC")
        return

    # ===== ADMIN ADD CODES =====
    if admin_step == "add_codes" and user_id == ADMIN_ID:

        try:
            update.message.delete()
        except:
            pass

        codes = load_codes(admin_package)

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

        save_codes(admin_package, codes)

        update.message.reply_text(
            f"✅ {added} Codes Added to {admin_package}\n📦 Total: {len(codes)}",
            reply_markup=main_menu()
        )

        admin_step = None
        admin_package = None
        return

    # ===== GET CODE =====
    if text == "🎁 Get Code":
        user_step[user_id] = "select_package"
        update.message.reply_text("Select package:", reply_markup=package_menu())
        return

    # ===== USER SELECT PACKAGE =====
    if user_id in user_step and user_step[user_id] == "select_package" and text in PACKAGES:

        codes = load_codes(text)

        if not codes:
            update.message.reply_text("❌ Out of stock", reply_markup=main_menu())
            user_step.pop(user_id)
            return

        code = codes.pop(0)
        save_codes(text, codes)

        update.message.reply_text(
            f"🎁 {text} UC Code:\n{code}\n\n📦 Remaining: {len(codes)}",
            reply_markup=main_menu()
        )

        user_step.pop(user_id)
        return

    # ===== STOCK =====
    if text == "📦 Stock":
        message = "📦 STOCK STATUS\n\n"
        for pkg in PACKAGES:
            count = len(load_codes(pkg))
            message += f"{pkg} UC → {count}\n"
        update.message.reply_text(message)
        return

    # ===== CANCEL =====
    if text == "🔙 Cancel":
        admin_step = None
        admin_package = None
        user_step.pop(user_id, None)
        update.message.reply_text("Cancelled", reply_markup=main_menu())

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
