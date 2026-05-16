import logging
import random
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient

# ---------- CONFIG ----------
BOT_TOKEN = "8466296023:AAHHz4iBpDWwZJgZABOapwlFRHn8f51uC6w"  # @BotFather se lo
ADMIN_ID = 7192516189  # Apna Telegram ID daalo
MONGO_URI = "mongodb+srv://mohitrao83076_db_user:LugF1xwlenkWRE1F@monster.ydmmckl.mongodb.net/?retryWrites=true&w=majority&appName=MONSTER"  # MongoDB URI (Atlas bhi use kar sakte ho)

# ---------- MongoDB Setup ----------
client = MongoClient(MONGO_URI)
db = client["loader_bot"]
loaders_col = db["loaders"]
keys_col = db["keys"]
referrals_col = db["referrals"]
users_col = db["users"]

# ---------- Loader List (Tumhare diye hisaab se) ----------
LOADERS = [
    "X SILENT", "DEFEND MOD", "KING ANDROID LOADER + MOD", "WAR LOADER & MOD",
    "FUNBOX PRO IMGUI JAVA & MOD", "DULUX MOD + LOADER", "MARS LOADER", "FRACTION LOADER",
    "BRAX", "TAPA TAP", "BGMI CHEAT", "ZTRX LOADER", "GPS LOADER", "RAB LOADER",
    "NUCLEAR LOADER", "BHAGWA LOADER", "1v100 LOADER & MOD", "BGMI BOX LOADER",
    "PAID LOADER", "Vex loder"
]

# ---------- Helper Functions ----------
def parse_duration(duration_str):
    """Convert 1, 5h, 7d, 30, 60 into days/hours"""
    duration_str = str(duration_str).strip().lower()
    if 'h' in duration_str:
        hours = int(duration_str.replace('h', ''))
        return timedelta(hours=hours)
    else:
        days = int(duration_str)
        return timedelta(days=days)

def generate_referral_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

# ---------- /start Command ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not users_col.find_one({"_id": user_id}):
        users_col.insert_one({"_id": user_id, "role": "admin" if user_id == ADMIN_ID else "user"})
    
    keyboard = [[InlineKeyboardButton("🎮 Select Loader", callback_data="select_loader")]]
    if users_col.find_one({"_id": user_id})["role"] == "admin":
        keyboard.append([InlineKeyboardButton("➕ Add Key", callback_data="add_key")])
        keyboard.append([InlineKeyboardButton("🔁 Reset Key", callback_data="reset_key")])
    
    await update.message.reply_text(
        "🎮 Welcome to Loader Key Bot!\nChoose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- Loader Selection ----------
async def select_loader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for i, loader in enumerate(LOADERS):
        keyboard.append([InlineKeyboardButton(loader, callback_data=f"loader_{i}")])
    
    await query.edit_message_text(
        "📦 Select Loader:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- Duration Selection ----------
async def loader_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    loader_idx = int(query.data.split('_')[1])
    context.user_data['selected_loader'] = LOADERS[loader_idx]
    
    keyboard = [
        [InlineKeyboardButton("1 Day", callback_data="duration_1d")],
        [InlineKeyboardButton("5 Hours", callback_data="duration_5h")],
        [InlineKeyboardButton("7 Days", callback_data="duration_7d")],
        [InlineKeyboardButton("30 Days", callback_data="duration_30d")],
        [InlineKeyboardButton("14 Days", callback_data="duration_14d")],
        [InlineKeyboardButton("60 Days", callback_data="duration_60d")]
    ]
    await query.edit_message_text(
        f"✅ Loader: {context.user_data['selected_loader']}\n⏳ Select Duration:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- Generate Key After Duration ----------
async def duration_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    duration_str = query.data.split('_')[1]
    duration = parse_duration(duration_str)
    
    # Generate unique key
    key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
    expiry = datetime.now() + duration
    
    keys_col.insert_one({
        "key": key,
        "loader": context.user_data['selected_loader'],
        "expiry": expiry,
        "used_by": None,
        "created_by": update.effective_user.id
    })
    
    await query.edit_message_text(
        f"✅ Key Generated!\n🔑 `{key}`\n📦 Loader: {context.user_data['selected_loader']}\n⏳ Expires: {expiry.strftime('%Y-%m-%d %H:%M:%S')}",
        parse_mode="Markdown"
    )

# ---------- /add loader days/hours (Admin only) ----------
async def add_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = users_col.find_one({"_id": user_id})
    if not user or user["role"] != "admin":
        await update.message.reply_text("❌ Only admin can add keys.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /add <loader_name> <duration>\nExample: /add 'X SILENT' 1,5h,30")
        return
    
    loader_name = context.args[0]
    durations = context.args[1].split(',')
    
    keys = []
    for dur in durations:
        duration = parse_duration(dur)
        expiry = datetime.now() + duration
        key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        keys_col.insert_one({
            "key": key,
            "loader": loader_name,
            "expiry": expiry,
            "used_by": None,
            "created_by": user_id
        })
        keys.append(f"{key} -> {dur}")
    
    await update.message.reply_text(f"✅ Added {len(keys)} keys for {loader_name}:\n" + "\n".join(keys))

# ---------- /reset key (Admin gets message) ----------
async def reset_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = users_col.find_one({"_id": user_id})
    if not user:
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /reset <key>")
        return
    
    key = context.args[0]
    key_data = keys_col.find_one({"key": key})
    if not key_data:
        await update.message.reply_text("❌ Key not found.")
        return
    
    # Admin ko message bhejo
    await context.bot.send_message(
        ADMIN_ID,
        f"⚠️ Key Reset Request\n🔑 {key}\n📦 Loader: {key_data['loader']}\n👤 By: {user_id}"
    )
    await update.message.reply_text("✅ Reset request sent to admin.")

# ---------- /refer <name> ----------
async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /refer <name>")
        return
    
    name = context.args[0]
    code = generate_referral_code()
    referrals_col.insert_one({
        "code": code,
        "name": name,
        "created_by": update.effective_user.id,
        "redeemed_by": None
    })
    await update.message.reply_text(f"✅ Referral Code: `{code}`\nShare this with others.", parse_mode="Markdown")

# ---------- /redeem <code> ----------
async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /redeem <referral_code>")
        return
    
    code = context.args[0]
    ref = referrals_col.find_one({"code": code, "redeemed_by": None})
    if not ref:
        await update.message.reply_text("❌ Invalid or already redeemed code.")
        return
    
    # Generate 1-day free key for redeemer
    key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
    expiry = datetime.now() + timedelta(days=1)
    keys_col.insert_one({
        "key": key,
        "loader": "FREE REFERRAL",
        "expiry": expiry,
        "used_by": update.effective_user.id,
        "created_by": ref["created_by"]
    })
    referrals_col.update_one({"code": code}, {"$set": {"redeemed_by": update.effective_user.id}})
    
    await update.message.reply_text(f"🎉 Redeemed! Your key: `{key}`\nExpires in 1 day.", parse_mode="Markdown")

# ---------- Handle all other messages (only redeem reply) ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚠️ Use /redeem <code> to redeem referral code.\nUse /start to get keys.")

# ---------- Main ----------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_key))
    app.add_handler(CommandHandler("reset", reset_key))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("redeem", redeem))
    app.add_handler(CallbackQueryHandler(select_loader, pattern="^select_loader$"))
    app.add_handler(CallbackQueryHandler(loader_selected, pattern="^loader_"))
    app.add_handler(CallbackQueryHandler(duration_selected, pattern="^duration_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
