import os
import sqlite3
import time
from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 255196166  # 👈 آیدی عددی خودت

CUSTOMER_PRICES = {
    "60": 0.89,
    "325": 4.50,
    "660": 8.99,
    "1800": 22.50,
    "3850": 44.50,
    "8100": 89.00
}

SELLER_PRICES = {
    "60": 0.87,
    "325": 4.42,
    "660": 8.85,
    "1800": 22.12,
    "3850": 44.00,
    "8100": 88.00
}

# ---------------- DATABASE ----------------
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)")
cursor.execute("""CREATE TABLE IF NOT EXISTS sellers (
    user_id INTEGER PRIMARY KEY,
    approved INTEGER DEFAULT 0,
    balance REAL DEFAULT 0,
    total_sales INTEGER DEFAULT 0,
    total_profit REAL DEFAULT 0
)""")
cursor.execute("CREATE TABLE IF NOT EXISTS codes (code TEXT PRIMARY KEY, amount TEXT, status TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, buyer_id INTEGER, amount TEXT, price REAL)")
cursor.execute("CREATE TABLE IF NOT EXISTS charge_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, status TEXT)")
conn.commit()

state = {}
last_purchase = {}

# ---------------- MENU ----------------
def menu(user_id):
    keyboard = [["🛒 Buy UC", "💰 Wallet"],
                ["💳 Charge Wallet", "👥 Become Seller"]]

    if user_id == ADMIN_ID:
        keyboard.append(["👑 Admin Panel"])

    cursor.execute("SELECT approved FROM sellers WHERE user_id=?", (user_id,))
    s = cursor.fetchone()
    if s and s[0] == 1:
        keyboard.append(["📦 Seller Panel"])

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

# ---------------- CHARGE ----------------
def charge(update, context):
    state[update.effective_user.id] = "charge"
    update.message.reply_text("Send amount to charge:")

# ---------------- BUY MENU ----------------
def buy(update, context):
    keyboard = []
    user_id = update.effective_user.id

    cursor.execute("SELECT approved FROM sellers WHERE user_id=?", (user_id,))
    seller = cursor.fetchone()

    for pkg in CUSTOMER_PRICES:
        price = CUSTOMER_PRICES[pkg]
        if seller and seller[0] == 1:
            price = SELLER_PRICES[pkg]

        cursor.execute("SELECT COUNT(*) FROM codes WHERE amount=? AND status='available'", (pkg,))
        stock = cursor.fetchone()[0]

        keyboard.append([
            InlineKeyboardButton(
                f"{pkg} UC - {price} USDT (Stock: {stock})",
                callback_data=f"buy_{pkg}"
            )
        ])

    update.message.reply_text("Select package:", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------- BUTTON HANDLER ----------------
def buttons(update, context):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id

    # جلوگیری از اسپم
    if user_id in last_purchase and time.time() - last_purchase[user_id] < 3:
        query.edit_message_text("⏳ Please wait before next purchase")
        return

    if query.data.startswith("buy_"):
        pkg = query.data.split("_")[1]

        cursor.execute("SELECT approved FROM sellers WHERE user_id=?", (user_id,))
        seller = cursor.fetchone()

        price = CUSTOMER_PRICES[pkg]
        if seller and seller[0] == 1:
            price = SELLER_PRICES[pkg]

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

        if seller and seller[0] == 1:
            profit = CUSTOMER_PRICES[pkg] - SELLER_PRICES[pkg]
            cursor.execute("""
                UPDATE sellers
                SET balance=balance+?,
                    total_sales=total_sales+1,
                    total_profit=total_profit+?
                WHERE user_id=?
            """, (profit, profit, user_id))

        conn.commit()
        last_purchase[user_id] = time.time()

        keyboard = [
            [
                InlineKeyboardButton("🔁 Buy Again", callback_data="back_buy"),
                InlineKeyboardButton("📞 Support", url="https://t.me/YOUR_SUPPORT")
            ]
        ]

        query.edit_message_text(
            f"""
━━━━━━━━━━━━━━━
🎁 *UC Delivered Successfully*
━━━━━━━━━━━━━━━
━━━━━━━━━━━━━━━
✅ Tap the code to copy
""",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "back_buy":
        buy(update, context)

# ---------------- TEXT HANDLER ----------------
def text(update, context):
    user_id = update.effective_user.id

    if user_id in state and state[user_id] == "charge":
        amount = float(update.message.text)

        cursor.execute("INSERT INTO charge_requests (user_id, amount, status) VALUES (?, ?, 'pending')",
                       (user_id, amount))
        conn.commit()

        keyboard = [[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}_{amount}")]]
        context.bot.send_message(
            ADMIN_ID,
            f"New Charge Request\nUser: {user_id}\nAmount: {amount}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        update.message.reply_text("⏳ Waiting for admin approval")
        state.pop(user_id)

# ---------------- MAIN ----------------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.regex("🛒 Buy UC"), buy))
    dp.add_handler(MessageHandler(Filters.regex("💰 Wallet"), wallet))
    dp.add_handler(MessageHandler(Filters.regex("💳 Charge Wallet"), charge))
    dp.add_handler(CallbackQueryHandler(buttons))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, text))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()

