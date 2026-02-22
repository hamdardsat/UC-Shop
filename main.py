import os
import sqlite3
import time
from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 255196166

PACKAGES = [60, 325, 660, 1800, 3850, 8100]

CUSTOMER_PRICES = {
    60: 0.89,
    325: 4.50,
    660: 8.99,
    1800: 22.50,
    3850: 44.50,
    8100: 89.00
}

SELLER_PRICES = {
    60: 0.87,
    325: 4.42,
    660: 8.85,
    1800: 22.12,
    3850: 44.00,
    8100: 88.00
}

# ---------------- DATABASE ----------------
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS sellers (user_id INTEGER PRIMARY KEY, approved INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS codes (code TEXT PRIMARY KEY, amount INTEGER, status TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, buyer_id INTEGER, amount INTEGER, price REAL)")
conn.commit()

last_purchase = {}

# ---------------- MENU ----------------
def menu(user_id):
    keyboard = [["🛒 Buy UC", "💰 Wallet"]]

    if user_id == ADMIN_ID:
        keyboard.append(["👑 Admin Panel"])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ---------------- START ----------------
def start(update, context):
    user_id = update.effective_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    update.message.reply_text("🔥 Welcome to UC Shop Pro", reply_markup=menu(user_id))

# ---------------- WALLET ----------------
def wallet(update, context):
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (update.effective_user.id,))
    balance = cursor.fetchone()[0]
    update.message.reply_text(f"💰 Balance: {balance} USDT")

# ---------------- BUY ----------------
def buy(update, context):
    keyboard = []

    for pkg in PACKAGES:
        price = CUSTOMER_PRICES[pkg]
        cursor.execute("SELECT COUNT(*) FROM codes WHERE amount=? AND status='available'", (pkg,))
        stock = cursor.fetchone()[0]

        keyboard.append([
            InlineKeyboardButton(
                f"{pkg} UC - {price} USDT (Stock: {stock})",
                callback_data=f"buy_{pkg}"
            )
        ])

    update.message.reply_text("Select package:", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------- BUTTONS ----------------
def buttons(update, context):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id

    if query.data.startswith("buy_"):
        pkg = int(query.data.split("_")[1])
        price = CUSTOMER_PRICES[pkg]

        cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        balance = cursor.fetchone()[0]

        if balance < price:
            query.edit_message_text("❌ Insufficient Balance")
            return

        cursor.execute("SELECT code FROM codes WHERE amount=? AND status='available' LIMIT 1", (pkg,))
        result = cursor.fetchone()

        if not result:
            query.edit_message_text("❌ Out of Stock")
            return

        code = result[0]

        cursor.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (price, user_id))
        cursor.execute("UPDATE codes SET status='sold' WHERE code=?", (code,))
        cursor.execute("INSERT INTO sales (buyer_id, amount, price) VALUES (?, ?, ?)", (user_id, pkg, price))
        conn.commit()

        query.edit_message_text(
            f"🎉 UC Delivered Successfully!\n\n📋 Your Code:\n\n`{code}`",
            parse_mode="Markdown"
        )

# ---------------- ADMIN PANEL ----------------
def admin_panel(update, context):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        update.message.reply_text("❌ Access Denied")
        return

    keyboard = [
        ["➕ Add UC Code"],
        ["📦 Stock Status"],
        ["📊 Statistics"],
        ["🔙 Main Menu"]
    ]

    update.message.reply_text(
        "👑 ADMIN PANEL",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# ---------------- ADMIN TEXT HANDLER ----------------
def text_handler(update, context):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id != ADMIN_ID:
        return

    if text == "➕ Add UC Code":
        context.user_data["step"] = "package"
        update.message.reply_text("Send package number:\n60 / 325 / 660 / 1800 / 3850 / 8100")
        return

    if context.user_data.get("step") == "package":
        package = int(text)
        if package not in PACKAGES:
            update.message.reply_text("❌ Invalid package")
            return
        context.user_data["package"] = package
        context.user_data["step"] = "code"
        update.message.reply_text("Now send the UC code:")
        return

    if context.user_data.get("step") == "code":
        package = context.user_data["package"]
        cursor.execute(
            "INSERT INTO codes (code, amount, status) VALUES (?, ?, 'available')",
            (text, package)
        )
        conn.commit()
        context.user_data.clear()
        update.message.reply_text("✅ Code Added Successfully")
        return

    if text == "📦 Stock Status":
        msg = "📦 STOCK STATUS\n\n"
        for pkg in PACKAGES:
            cursor.execute("SELECT COUNT(*) FROM codes WHERE amount=? AND status='available'", (pkg,))
            count = cursor.fetchone()[0]
            msg += f"{pkg} UC → {count}\n"
        update.message.reply_text(msg)
        return

    if text == "📊 Statistics":
        cursor.execute("SELECT COUNT(*) FROM users")
        users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM sales")
        sales = cursor.fetchone()[0]
        update.message.reply_text(f"📊 Statistics\n\nUsers: {users}\nSales: {sales}")
        return

    if text == "🔙 Main Menu":
        update.message.reply_text("Back to main menu", reply_markup=menu(user_id))

# ---------------- MAIN ----------------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.regex("🛒 Buy UC"), buy))
    dp.add_handler(MessageHandler(Filters.regex("💰 Wallet"), wallet))
    dp.add_handler(MessageHandler(Filters.regex("👑 Admin Panel"), admin_panel))
    dp.add_handler(CallbackQueryHandler(buttons))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, text_handler))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
