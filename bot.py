import random
import string
import sys
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# ---------- CONFIG ----------
BOT_TOKEN = "8466296023:AAGXB1dQ-WY87bBrYd5V2O1PnRmLPGXRO4M"
ADMIN_ID = 7192516189
MONGO_URI = "mongodb+srv://mohitrao83076_db_user:LugF1xwlenkWRE1F@monster.ydmmckl.mongodb.net/?retryWrites=true&w=majority&appName=MONSTER"

# ---------- INDIA TIME ----------
def get_india_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# ---------- CHECK MONGODB ----------
print("🔌 Checking MongoDB...")
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("✅ MongoDB connected!")
except (ConnectionFailure, ServerSelectionTimeoutError) as e:
    print(f"❌ MongoDB failed: {e}")
    sys.exit(1)

db = client["loader_bot"]
keys_col = db["keys"]
users_col = db["users"]
referrals_col = db["referrals"]

LOADERS = [
    "X SILENT", "DEFEND MOD", "KING ANDROID LOADER + MOD", "WAR LOADER & MOD",
    "FUNBOX PRO IMGUI JAVA & MOD", "DULUX MOD + LOADER", "MARS LOADER", "FRACTION LOADER",
    "BRAX", "TAPA TAP", "BGMI CHEAT", "ZTRX LOADER", "GPS LOADER", "RAB LOADER",
    "NUCLEAR LOADER", "BHAGWA LOADER", "1v100 LOADER & MOD", "BGMI BOX LOADER",
    "PAID LOADER", "Vex loder"
]

def parse_duration(duration_str):
    duration_str = str(duration_str).strip().lower()
    if 'h' in duration_str:
        return timedelta(hours=int(duration_str.replace('h', '')))
    else:
        return timedelta(days=int(duration_str.replace('d', '')))

def generate_referral_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def has_access(user_id):
    user = users_col.find_one({"_id": user_id})
    if not user:
        return False
    return user.get("access", False) or user.get("role") == "admin" or user_id == ADMIN_ID

def is_admin(user_id):
    user = users_col.find_one({"_id": user_id})
    return user and (user.get("role") == "admin" or user_id == ADMIN_ID)

# ---------- /help ----------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """📚 *Bot Commands*

🔹 *User:*
/start - Start bot
/help - This help
/reset <key> - Request reset

🔹 *Referral:*
/create <name> - Create referral
/redeem <code> - Redeem

🔹 *Admin:*
/grant <id> - Give access
/revoke <id> - Remove access
/blockuser <id> - Block user
/unblockuser <id> - Unblock
/blockref <code> - Block referral

🕐 IST: {}"""
    await update.message.reply_text(help_text.format(get_india_time().strftime('%Y-%m-%d %H:%M:%S')), parse_mode="Markdown")

# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    user = users_col.find_one({"_id": user_id})
    if not user:
        users_col.insert_one({"_id": user_id, "role": "user", "access": False, "blocked": False})
    
    if not has_access(user_id):
        await update.message.reply_text(f"❌ *Access Denied!*\n\nContact @Flame_AI_Support\n🕐 {get_india_time().strftime('%H:%M:%S')} IST", parse_mode="Markdown")
        return
    
    keyboard = [[InlineKeyboardButton("🎮 Get Key", callback_data="get_key")]]
    
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("➕ Add Key", callback_data="add_key_menu")])
        keyboard.append([InlineKeyboardButton("📊 Check Keys", callback_data="check_keys")])
    
    await update.message.reply_text("🤖 *Loader Key Bot*\nClick 'Get Key'", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------- ADD KEY MENU ----------
async def add_key_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Admin only!")
        return
    
    keyboard = []
    for i, loader in enumerate(LOADERS):
        keyboard.append([InlineKeyboardButton(f"📁 {loader}", callback_data=f"add_loader_{i}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Back", callback_data="back_start")])
    
    await query.edit_message_text("➕ *Select Loader to Add Keys:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------- ASK FOR KEYS ----------
async def add_key_to_loader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    loader_idx = int(query.data.split('_')[2])
    loader_name = LOADERS[loader_idx]
    context.user_data['add_loader'] = loader_name
    
    await query.edit_message_text(
        f"📁 *Loader:* {loader_name}\n\n"
        "Send keys:\n`duration | key1,key2,key3`\n\n"
        "*Examples:*\n"
        "`30d | ABC123,DEF456,GHI789`\n"
        "`7d | TEST1,TEST2`\n"
        "`5h | QUICK1`\n\n"
        "*Durations:* 5h, 1d, 7d, 14d, 30d, 60d\n\n"
        "Send /cancel",
        parse_mode="Markdown"
    )
    context.user_data['awaiting_keys'] = True

# ---------- PROCESS KEYS ----------
async def process_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_keys'):
        return
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        context.user_data['awaiting_keys'] = False
        return
    
    if update.message.text == "/cancel":
        context.user_data['awaiting_keys'] = False
        await update.message.reply_text("❌ Cancelled.")
        return
    
    try:
        parts = [p.strip() for p in update.message.text.split('|')]
        if len(parts) != 2:
            raise ValueError()
        
        duration_str = parts[0].strip()
        keys_str = parts[1].strip()
        
        keys_list = [k.strip() for k in keys_str.split(',')]
        loader_name = context.user_data.get('add_loader')
        
        if not loader_name:
            await update.message.reply_text("❌ Session expired!")
            context.user_data['awaiting_keys'] = False
            return
        
        duration = parse_duration(duration_str)
        expiry = datetime.utcnow() + duration
        
        added = 0
        skipped = 0
        
        for key in keys_list:
            if keys_col.find_one({"key": key}):
                skipped += 1
                continue
            
            keys_col.insert_one({
                "key": key, "loader": loader_name, "duration": duration_str,
                "expiry": expiry, "used": False, "used_by": None,
                "created_by": update.effective_user.id, "created_at": get_india_time()
            })
            added += 1
        
        await update.message.reply_text(
            f"✅ *Keys Added!*\n\n📦 {loader_name}\n⏳ {duration_str}\n✅ Added: {added}\n⚠️ Skipped: {skipped}\n🕐 {get_india_time().strftime('%H:%M:%S')} IST",
            parse_mode="Markdown"
        )
        
        context.user_data['awaiting_keys'] = False
        
    except:
        await update.message.reply_text("❌ *Invalid!*\nUse: `duration | key1,key2`\nExample: `30d | ABC123,DEF456`", parse_mode="Markdown")

# ---------- GET KEY (USER) ----------
async def get_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not has_access(update.effective_user.id):
        await query.edit_message_text("❌ Access Denied!")
        return
    
    keyboard = []
    for i, loader in enumerate(LOADERS):
        available = keys_col.count_documents({"loader": loader, "used": False, "expiry": {"$gt": datetime.utcnow()}})
        if available > 0:
            keyboard.append([InlineKeyboardButton(f"✅ {loader} ({available})", callback_data=f"get_loader_{i}")])
        else:
            keyboard.append([InlineKeyboardButton(f"❌ {loader} (0)", callback_data=f"no_loader_{i}")])
    
    await query.edit_message_text("📦 *Select Loader:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def no_loader_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ No keys available!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="get_key")]]))

async def show_user_durations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    loader_idx = int(query.data.split('_')[2])
    loader_name = LOADERS[loader_idx]
    context.user_data['user_loader'] = loader_name
    
    available_keys = list(keys_col.find({"loader": loader_name, "used": False, "expiry": {"$gt": datetime.utcnow()}}))
    
    if not available_keys:
        await query.edit_message_text(f"❌ No keys for {loader_name}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="get_key")]]))
        return
    
    durations = {}
    for key_data in available_keys:
        dur = key_data.get('duration', '30d')
        durations[dur] = durations.get(dur, 0) + 1
    
    keyboard = []
    for dur in sorted(durations.keys()):
        keyboard.append([InlineKeyboardButton(f"⏳ {dur} ({durations[dur]})", callback_data=f"user_dur_{dur}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Back", callback_data="get_key")])
    await query.edit_message_text(f"✅ *Loader:* {loader_name}\n\n⏳ *Select Duration:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def give_user_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not has_access(update.effective_user.id):
        await query.edit_message_text("❌ Access Denied!")
        return
    
    duration = query.data.split('_')[2]
    loader = context.user_data.get('user_loader')
    
    if not loader:
        await query.edit_message_text("Session expired!")
        return
    
    available_key = keys_col.find_one({"loader": loader, "duration": duration, "used": False, "expiry": {"$gt": datetime.utcnow()}})
    
    if not available_key:
        await query.edit_message_text("❌ No key!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Try Again", callback_data="get_key")]]))
        return
    
    keys_col.update_one({"_id": available_key["_id"]}, {"$set": {"used": True, "used_by": update.effective_user.id, "used_at": get_india_time()}})
    
    await query.edit_message_text(
        f"✅ *Your Key!*\n\n🔑 `{available_key['key']}`\n📦 {loader}\n⏳ {duration}\n\n🕐 {get_india_time().strftime('%H:%M:%S')} IST",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Get Another", callback_data="get_key")]])
    )

# ---------- CHECK KEYS ----------
async def check_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Admin only!")
        return
    
    message = "📊 *Key Statistics*\n\n"
    total = 0
    for loader in LOADERS:
        available = keys_col.count_documents({"loader": loader, "used": False, "expiry": {"$gt": datetime.utcnow()}})
        total += available
        message += f"{'✅' if available>0 else '❌'} {loader}: {available}\n"
    
    message += f"\n📊 *Total:* {total} keys\n🕐 {get_india_time().strftime('%H:%M:%S')} IST"
    
    await query.edit_message_text(message, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="back_start")]]))

# ---------- ACCESS MANAGEMENT ----------
async def grant_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /grant USER_ID")
        return
    
    try:
        user_id = int(context.args[0])
        users_col.update_one({"_id": user_id}, {"$set": {"access": True}}, upsert=True)
        await update.message.reply_text(f"✅ User {user_id} now has access!")
    except:
        await update.message.reply_text("❌ Invalid ID!")

async def revoke_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /revoke USER_ID")
        return
    
    try:
        user_id = int(context.args[0])
        users_col.update_one({"_id": user_id}, {"$set": {"access": False}})
        await update.message.reply_text(f"✅ Access revoked for {user_id}!")
    except:
        await update.message.reply_text("❌ Invalid ID!")

async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /blockuser USER_ID")
        return
    
    try:
        user_id = int(context.args[0])
        users_col.update_one({"_id": user_id}, {"$set": {"blocked": True, "access": False}})
        await update.message.reply_text(f"✅ User {user_id} blocked!")
    except:
        await update.message.reply_text("❌ Invalid ID!")

async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /unblockuser USER_ID")
        return
    
    try:
        user_id = int(context.args[0])
        users_col.update_one({"_id": user_id}, {"$set": {"blocked": False}})
        await update.message.reply_text(f"✅ User {user_id} unblocked!")
    except:
        await update.message.reply_text("❌ Invalid ID!")

# ---------- REFERRAL ----------
async def create_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        await update.message.reply_text("❌ Access Denied!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /create NAME")
        return
    
    name = context.args[0]
    code = generate_referral_code()
    
    referrals_col.insert_one({
        "code": code, "name": name, "created_by": update.effective_user.id,
        "created_at": get_india_time(), "redeemed_by": None, "blocked": False
    })
    
    await update.message.reply_text(f"✅ *Referral Created!*\n\n📛 Name: {name}\n🔗 Code: `{code}`\n\nShare: `/redeem {code}`", parse_mode="Markdown")

async def redeem_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        await update.message.reply_text("❌ Access Denied!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /redeem CODE")
        return
    
    code = context.args[0]
    ref = referrals_col.find_one({"code": code, "redeemed_by": None})
    
    if not ref:
        await update.message.reply_text("❌ Invalid or already redeemed!")
        return
    
    if ref.get("blocked", False):
        await update.message.reply_text("❌ This referral is blocked!")
        return
    
    referrals_col.update_one({"code": code}, {"$set": {"redeemed_by": update.effective_user.id, "redeemed_at": get_india_time()}})
    
    key = f"REF-{generate_referral_code()}"
    expiry = datetime.utcnow() + timedelta(days=7)
    
    keys_col.insert_one({
        "key": key, "loader": "REFERRAL REWARD", "duration": "7d",
        "expiry": expiry, "used": False, "used_by": None,
        "created_by": update.effective_user.id, "created_at": get_india_time()
    })
    
    await update.message.reply_text(f"🎉 *Referral Redeemed!*\n\n📛 Name: {ref['name']}\n🔑 Your key: `{key}`\n⏳ Valid for 7 days", parse_mode="Markdown")

async def block_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /blockref CODE")
        return
    
    code = context.args[0]
    result = referrals_col.update_one({"code": code}, {"$set": {"blocked": True}})
    
    if result.modified_count:
        await update.message.reply_text(f"✅ Referral `{code}` blocked!", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Referral not found!")

async def reset_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /reset KEY")
        return
    
    key = context.args[0]
    key_data = keys_col.find_one({"key": key})
    if not key_data:
        await update.message.reply_text("❌ Key not found!")
        return
    
    await context.bot.send_message(ADMIN_ID, f"⚠️ Reset Request\n🔑 {key}\n📦 {key_data.get('loader', 'Unknown')}")
    await update.message.reply_text("✅ Request sent to admin!")

async def back_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_keys'):
        await process_keys(update, context)
    else:
        await update.message.reply_text("Use /start or /help")

# ---------- MAIN ----------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset_key))
    app.add_handler(CommandHandler("grant", grant_access))
    app.add_handler(CommandHandler("revoke", revoke_access))
    app.add_handler(CommandHandler("blockuser", block_user))
    app.add_handler(CommandHandler("unblockuser", unblock_user))
    app.add_handler(CommandHandler("create", create_referral))
    app.add_handler(CommandHandler("redeem", redeem_referral))
    app.add_handler(CommandHandler("blockref", block_referral))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(get_key, pattern="^get_key$"))
    app.add_handler(CallbackQueryHandler(add_key_menu, pattern="^add_key_menu$"))
    app.add_handler(CallbackQueryHandler(add_key_to_loader, pattern="^add_loader_"))
    app.add_handler(CallbackQueryHandler(show_user_durations, pattern="^get_loader_"))
    app.add_handler(CallbackQueryHandler(no_loader_keys, pattern="^no_loader_"))
    app.add_handler(CallbackQueryHandler(give_user_key, pattern="^user_dur_"))
    app.add_handler(CallbackQueryHandler(check_keys, pattern="^check_keys$"))
    app.add_handler(CallbackQueryHandler(back_start, pattern="^back_start$"))
    
    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("=" * 40)
    print("🤖 Bot Started Successfully!")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"🕐 India Time: {get_india_time().strftime('%Y-%m-%d %H:%M:%S')} IST")
    print("✅ Send /start on Telegram")
    print("=" * 40)
    
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
