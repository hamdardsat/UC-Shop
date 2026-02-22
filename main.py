import os
import sqlite3
from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 255196166

CUSTOMER_PRICES = {
    "60": 0.89,
    "325": 4.50,
    "660": 8.99,
    "1800": 22.50,
    "3850": 44.50,
    "8100": 89.00
}

# ================= DATABASE =================
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS codes (code TEXT PRIMARY KEY, amount TEXT, status TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, buyer_id INTEGER, amount TEXT, price REAL)")
cursor.execute("CREATE TABLE IF NOT EXISTS charge_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, status TEXT)")
conn.commit()

state = {}

# ================= MENU =================
def menu(user_id):
    keyboard = [["🛒 Buy UC", "💰 Wallet"],
                ["💳 Charge Wallet"]]

    if user_id == ADMIN_ID:
        keyboard.append(["👑 Admin Panel"])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ================= START =================
def start(update, context):
    user_id = update.effective_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    update.message.reply_text("🔥 Welcome to UC Shop Pro", reply_markup=menu(user_id))

# ================= WALLET =================
def wallet(update, context):
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (update.effective_user.id,))
    balance = cursor.fetchone()[0]
    update.message.reply_text(f"💰 Balance: {balance} USDT")

# ================= CHARGE =================
def charge(update, context):
    state[update.effective_user.id] = "charge"
    update.message.reply_text("Send amount to charge:")

# ================= BUY =================
def buy(update, context):
    keyboard = []

    for pkg in CUSTOMER_PRICES:
        cursor.execute("SELECT COUNT(*) FROM codes WHERE amount=? AND status='available'", (pkg,))
        stock = cursor.fetchone()[0]

        keyboard.append([
            InlineKeyboardButton(
                f"{pkg} UC - {CUSTOMER_PRICES[pkg]} USDT (Stock: {stock})",
                callback_data=f"buy_{pkg}"
            )
        ])

    update.message.reply_text("Select package:", reply_markup=InlineKeyboardMarkup(keyboard))

# ================= BUTTONS =================
def buttons(update, context):
    query = update.callback_query
    query.answer()

    # APPROVE CHARGE
    if query.data.startswith("approve_"):
        uid = int(query.data.split("_")[1])

        cursor.execute("SELECT amount FROM charge_requests WHERE user_id=? AND status='pending'", (uid,))
        data = cursor.fetchone()
        if not data:
            query.edit_message_text("Already processed ❌")
            return

        amount = data[0]

        cursor.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid))
        cursor.execute("UPDATE charge_requests SET status='approved' WHERE user_id=?", (uid,))
        conn.commit()

        query.edit_message_text("✅ Charge Approved")
        return

    # BUY UC
    if query.data.startswith("buy_"):
        pkg = query.data.split("_")[1]
        user_id = query.from_user.id
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

        query.edit_message_text(f"🎁 UC Code:\n\n`{code}`", parse_mode="Markdown")

# ================= ADMIN PANEL =================
def admin_panel(update, context):
    if update.effective_user.id != ADMIN_ID:
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

# ================= TEXT HANDLER =================
def text_handler(update, context):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # ===== ADMIN SECTION =====
    if user_id == ADMIN_ID:

        if text == "➕ Add UC Code":
            context.user_data["step"] = "package"
            update.message.reply_text("Send package number (60,325,660,1800,3850,8100)")
            return

        if context.user_data.get("step") == "package":
            if text not in CUSTOMER_PRICES:
                update.message.reply_text("❌ Invalid package")
                return
            context.user_data["package"] = text
            context.user_data["step"] = "code"
            update.message.reply_text("Send codes now (new line / space / comma supported)")
            return

        if context.user_data.get("step") == "code":
            pkg = context.user_data["package"]

            codes_list = text.replace(",", " ").split()

            added = 0
            duplicate = 0

            for code in codes_list:
                code = code.strip()
                if not code:
                    continue
                cursor.execute(
                    "INSERT OR IGNORE INTO codes (code, amount, status) VALUES (?, ?, 'available')",
                    (code, pkg)
                )
                if cursor.rowcount == 1:
                    added += 1
                else:
                    duplicate += 1

            conn.commit()
            context.user_data.clear()

            cursor.execute("SELECT COUNT(*) FROM codes WHERE amount=? AND status='available'", (pkg,))
            stock = cursor.fetchone()[0]

            update.message.reply_text(
                f"✅ Added: {added}\n⚠️ Duplicate: {duplicate}\n📦 Stock ({pkg} UC): {stock}"
            )
            return

        if text == "📦 Stock Status":
            msg = "📦 STOCK STATUS\n\n"
            for pkg in CUSTOMER_PRICES:
                cursor.execute("SELECT COUNT(*) FROM codes WHERE amount=? AND status='available'", (pkg,))
                count = cursor.fetchone()[0]
                msg += f"{pkg} UC → {count}\n"
            update.message.reply_text(msg)
            return

        if text == "📊 Statistics":
            cursor.execute("SELECT COUNT(*) FROM users")
            users = cursor.fetchone()[0]
            cursor.execute("SELECT SUM(price) FROM sales")
            income = cursor.fetchone()[0] or 0
            update.message.reply_text(f"Users: {users}\nIncome: {income} USDT")
            return

        if text == "🔙 Main Menu":
            update.message.reply_text("Back", reply_markup=menu(user_id))
            return

    # ===== CHARGE REQUEST =====
    if state.get(user_id) == "charge":
        try:
            amount = float(text)
            cursor.execute("INSERT INTO charge_requests (user_id, amount, status) VALUES (?, ?, 'pending')", (user_id, amount))
            conn.commit()

            keyboard = [[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}")]]
            context.bot.send_message(
                ADMIN_ID,
                f"New Charge Request\nUser: {user_id}\nAmount: {amount}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

            update.message.reply_text("⏳ Waiting for approval")
            state.pop(user_id)
        except:
            update.message.reply_text("Send valid number ❌")

# ================= MAIN =================
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.regex("🛒 Buy UC"), buy))
    dp.add_handler(MessageHandler(Filters.regex("💰 Wallet"), wallet))
    dp.add_handler(MessageHandler(Filters.regex("💳 Charge Wallet"), charge))
    dp.add_handler(MessageHandler(Filters.regex("👑 Admin Panel"), admin_panel))
    dp.add_handler(CallbackQueryHandler(buttons))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, text_handler))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
