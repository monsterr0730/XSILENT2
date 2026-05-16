
import logging
import random
import string
import sys
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# ---------- CONFIG ----------
BOT_TOKEN = "8466296023:AAHHz4iBpDWwZJgZABOapwlFRHn8f51uC6w"
ADMIN_ID = 7192516189
MONGO_URI = "mongodb+srv://mohitrao83076_db_user:LugF1xwlenkWRE1F@monster.ydmmckl.mongodb.net/?retryWrites=true&w=majority&appName=MONSTER"

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

# ---------- CHECK IF ADMIN ----------
def is_admin(user_id):
    user = users_col.find_one({"_id": user_id})
    return user and user.get("role") == "admin"

# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not users_col.find_one({"_id": user_id}):
        role = "admin" if user_id == ADMIN_ID else "user"
        users_col.insert_one({"_id": user_id, "role": role, "blocked": False})
    
    keyboard = [[InlineKeyboardButton("🎮 Get Key", callback_data="get_key")]]
    
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("➕ Add Key", callback_data="add_key_admin")])
        keyboard.append([InlineKeyboardButton("📊 Check Keys", callback_data="check_keys")])
        keyboard.append([InlineKeyboardButton("👑 Make Admin", callback_data="make_admin")])
    
    await update.message.reply_text(
        "🤖 **Loader Key Bot**\n\nClick 'Get Key'",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- MAKE OTHER USER ADMIN ----------
async def make_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Only owner can make admin!")
        return
    
    await query.edit_message_text(
        "👑 **Make Admin**\n\nSend user ID:\n`/addadmin USER_ID`\n\nExample: `/addadmin 123456789`",
        parse_mode="Markdown"
    )

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id) and user_id != ADMIN_ID:
        await update.message.reply_text("❌ Only owner can make admin!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /addadmin <user_id>")
        return
    
    try:
        new_admin_id = int(context.args[0])
        users_col.update_one({"_id": new_admin_id}, {"$set": {"role": "admin"}}, upsert=True)
        await update.message.reply_text(f"✅ User {new_admin_id} is now admin!")
    except:
        await update.message.reply_text("❌ Invalid user ID!")

# ---------- GET KEY (USER) ----------
async def get_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = users_col.find_one({"_id": user_id})
    
    if user and user.get("blocked", False):
        await query.edit_message_text("❌ You are blocked! Contact admin.")
        return
    
    keyboard = []
    for i, loader in enumerate(LOADERS):
        available_count = keys_col.count_documents({
            "loader": loader, "used": False, "expiry": {"$gt": datetime.now()}
        })
        if available_count > 0:
            keyboard.append([InlineKeyboardButton(f"✅ {loader} ({available_count})", callback_data=f"loader_{i}")])
        else:
            keyboard.append([InlineKeyboardButton(f"❌ {loader} (0)", callback_data=f"noloader_{i}")])
    
    await query.edit_message_text(
        "📦 **Select Loader:**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def no_key_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ No keys!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="get_key")]]))

async def show_durations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    loader_idx = int(query.data.split('_')[1])
    loader_name = LOADERS[loader_idx]
    context.user_data['selected_loader'] = loader_name
    
    available_keys = list(keys_col.find({
        "loader": loader_name, "used": False, "expiry": {"$gt": datetime.now()}
    }))
    
    if not available_keys:
        await query.edit_message_text(f"❌ No keys for {loader_name}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="get_key")]]))
        return
    
    durations = {}
    for key_data in available_keys:
        dur = key_data.get('duration', '30d')
        durations[dur] = durations.get(dur, 0) + 1
    
    duration_order = {"5h": 1, "1d": 2, "7d": 3, "14d": 4, "30d": 5, "60d": 6}
    keyboard = []
    for dur in sorted(durations.keys(), key=lambda x: duration_order.get(x, 99)):
        keyboard.append([InlineKeyboardButton(f"⏳ {dur} ({durations[dur]} keys)", callback_data=f"dur_{dur}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Back", callback_data="get_key")])
    await query.edit_message_text(f"✅ Loader: **{loader_name}**\n\n⏳ Select Duration:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def get_final_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = users_col.find_one({"_id": user_id})
    
    if user and user.get("blocked", False):
        await query.edit_message_text("❌ You are blocked!")
        return
    
    duration = query.data.split('_')[1]
    loader = context.user_data.get('selected_loader')
    
    if not loader:
        await query.edit_message_text("❌ Session expired!")
        return
    
    available_key = keys_col.find_one({
        "loader": loader, "duration": duration, "used": False, "expiry": {"$gt": datetime.now()}
    })
    
    if not available_key:
        await query.edit_message_text("❌ No key!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Try Again", callback_data="get_key")]]))
        return
    
    keys_col.update_one({"_id": available_key["_id"]}, {"$set": {"used": True, "used_by": user_id, "used_at": datetime.now()}})
    
    await query.edit_message_text(
        f"✅ **Your Key!**\n\n🔑 `{available_key['key']}`\n📦 {loader}\n⏳ {duration}\n\n✨ Copy: `{available_key['key']}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Get Another", callback_data="get_key")]])
    )

# ---------- ADD KEY (ADMIN) - BULK SUPPORT ----------
async def add_key_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Admin only!")
        return
    
    await query.edit_message_text(
        "➕ **Add Keys**\n\n"
        "Single: `loader | duration | key`\n"
        "Bulk: `loader | duration | key1,key2,key3`\n\n"
        "Examples:\n"
        "`X SILENT | 30d | ABC123`\n"
        "`DEFEND MOD | 5h | KEY1,KEY2,KEY3`\n\n"
        "Send /cancel",
        parse_mode="Markdown"
    )
    context.user_data['awaiting_bulk_keys'] = True

async def process_add_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_bulk_keys'):
        return
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        context.user_data['awaiting_bulk_keys'] = False
        return
    
    if update.message.text == "/cancel":
        context.user_data['awaiting_bulk_keys'] = False
        await update.message.reply_text("❌ Cancelled.")
        return
    
    try:
        parts = [p.strip() for p in update.message.text.split('|')]
        if len(parts) != 3:
            raise ValueError()
        
        loader_name, duration_str, keys_str = parts
        
        if loader_name not in LOADERS:
            await update.message.reply_text(f"❌ Loader '{loader_name}' not found!")
            return
        
        keys_list = [k.strip() for k in keys_str.split(',')]
        duration = parse_duration(duration_str)
        expiry = datetime.now() + duration
        
        added = 0
        skipped = 0
        
        for key in keys_list:
            if keys_col.find_one({"key": key}):
                skipped += 1
                continue
            
            keys_col.insert_one({
                "key": key, "loader": loader_name, "duration": duration_str,
                "expiry": expiry, "used": False, "used_by": None,
                "created_by": update.effective_user.id, "created_at": datetime.now()
            })
            added += 1
        
        await update.message.reply_text(
            f"✅ **Bulk Add Complete!**\n\n"
            f"📦 Loader: {loader_name}\n"
            f"⏳ Duration: {duration_str}\n"
            f"✅ Added: {added}\n"
            f"⚠️ Skipped: {skipped}",
            parse_mode="Markdown"
        )
        
        context.user_data['awaiting_bulk_keys'] = False
        
    except Exception as e:
        await update.message.reply_text("❌ Invalid format! Use: `loader | duration | key1,key2,key3`", parse_mode="Markdown")

# ---------- CREATE REFERRAL ----------
async def create_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: `/create referral NAME`", parse_mode="Markdown")
        return
    
    name = context.args[0]
    code = generate_referral_code()
    
    referrals_col.insert_one({
        "code": code, "name": name, "created_by": update.effective_user.id,
        "created_at": datetime.now(), "redeemed_by": None, "blocked": False
    })
    
    await update.message.reply_text(
        f"✅ **Referral Created!**\n\n"
        f"📛 Name: {name}\n"
        f"🔗 Code: `{code}`\n\n"
        f"Share: `/redeem {code}`",
        parse_mode="Markdown"
    )

# ---------- REDEEM REFERRAL ----------
async def redeem_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: `/redeem CODE`", parse_mode="Markdown")
        return
    
    code = context.args[0]
    ref = referrals_col.find_one({"code": code, "redeemed_by": None})
    
    if not ref:
        await update.message.reply_text("❌ Invalid or already redeemed!")
        return
    
    if ref.get("blocked", False):
        await update.message.reply_text("❌ This referral is blocked!")
        return
    
    referrals_col.update_one({"code": code}, {"$set": {"redeemed_by": update.effective_user.id, "redeemed_at": datetime.now()}})
    
    # Give 7-day free key as reward
    expiry = datetime.now() + timedelta(days=7)
    key = f"REF-{generate_referral_code()}"
    
    keys_col.insert_one({
        "key": key, "loader": "REFERRAL REWARD", "duration": "7d",
        "expiry": expiry, "used": False, "used_by": None,
        "created_by": update.effective_user.id, "created_at": datetime.now()
    })
    
    await update.message.reply_text(
        f"🎉 **Referral Redeemed!**\n\n"
        f"📛 Name: {ref['name']}\n"
        f"🔑 Your reward key: `{key}`\n"
        f"⏳ Valid for 7 days",
        parse_mode="Markdown"
    )

# ---------- BLOCK REFERRAL ----------
async def block_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: `/block referral CODE`\nOr: `/block user USER_ID`", parse_mode="Markdown")
        return
    
    target = context.args[0]
    
    # Block by referral code
    if len(target) == 6 and target.isalnum():
        result = referrals_col.update_one({"code": target}, {"$set": {"blocked": True}})
        if result.modified_count:
            await update.message.reply_text(f"✅ Referral `{target}` blocked!")
        else:
            await update.message.reply_text("❌ Referral not found!")
    else:
        # Block user by ID
        try:
            user_id = int(target)
            users_col.update_one({"_id": user_id}, {"$set": {"blocked": True}}, upsert=True)
            await update.message.reply_text(f"✅ User `{user_id}` blocked!")
        except:
            await update.message.reply_text("❌ Invalid code or user ID!")

# ---------- CHECK KEYS (ADMIN) ----------
async def check_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Admin only!")
        return
    
    message = "📊 **Key Statistics**\n\n"
    total = 0
    
    for loader in LOADERS:
        available = keys_col.count_documents({"loader": loader, "used": False, "expiry": {"$gt": datetime.now()}})
        total += available
        if available > 0:
            message += f"✅ {loader}: {available}\n"
        else:
            message += f"❌ {loader}: 0\n"
    
    message += f"\n📊 **Total Available:** {total}"
    
    await query.edit_message_text(message, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="back_start")]]))

async def reset_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /reset <key>")
        return
    
    key = context.args[0]
    key_data = keys_col.find_one({"key": key})
    
    if not key_data:
        await update.message.reply_text("❌ Key not found!")
        return
    
    await context.bot.send_message(ADMIN_ID, f"⚠️ Reset Request\n🔑 `{key}`\n📦 {key_data.get('loader', 'Unknown')}", parse_mode="Markdown")
    await update.message.reply_text("✅ Request sent!")

async def back_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_bulk_keys'):
        await process_add_keys(update, context)
    else:
        await update.message.reply_text("⚠️ Use /start")

# ---------- MAIN ----------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset_key))
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("create", create_referral))
    app.add_handler(CommandHandler("redeem", redeem_referral))
    app.add_handler(CommandHandler("block", block_referral))
    
    app.add_handler(CallbackQueryHandler(get_key, pattern="^get_key$"))
    app.add_handler(CallbackQueryHandler(show_durations, pattern="^loader_"))
    app.add_handler(CallbackQueryHandler(no_key_handler, pattern="^noloader_"))
    app.add_handler(CallbackQueryHandler(get_final_key, pattern="^dur_"))
    app.add_handler(CallbackQueryHandler(add_key_admin, pattern="^add_key_admin$"))
    app.add_handler(CallbackQueryHandler(check_keys, pattern="^check_keys$"))
    app.add_handler(CallbackQueryHandler(make_admin_panel, pattern="^make_admin$"))
    app.add_handler(CallbackQueryHandler(back_start, pattern="^back_start$"))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot Started!")
    app.run_polling()

if __name__ == "__main__":
    main()
