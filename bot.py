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
BOT_TOKEN = "8466296023:AAH8v_ZE4jsZ_hiI0szcA8e9ljA004mbx4Q"
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

# ---------- CHECK ACCESS ----------
def has_access(user_id):
    user = users_col.find_one({"_id": user_id})
    if not user:
        return False
    return user.get("access", False) or user.get("role") == "admin" or user_id == ADMIN_ID

def is_admin(user_id):
    user = users_col.find_one({"_id": user_id})
    return user and (user.get("role") == "admin" or user_id == ADMIN_ID)

# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check if user exists
    user = users_col.find_one({"_id": user_id})
    if not user:
        users_col.insert_one({"_id": user_id, "role": "user", "access": False, "blocked": False})
    
    # Check access
    if not has_access(user_id):
        await update.message.reply_text(
            "❌ **Access Denied!**\n\n"
            "You don't have permission to use this bot.\n"
            "Contact admin to get access.\n\n"
            f"👑 Admin: @Flame_AI_Support",
            parse_mode="Markdown"
        )
        return
    
    keyboard = [[InlineKeyboardButton("🎮 Get Key", callback_data="get_key")]]
    
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("➕ Add Key", callback_data="add_key_admin")])
        keyboard.append([InlineKeyboardButton("📊 Check Keys", callback_data="check_keys")])
        keyboard.append([InlineKeyboardButton("👑 Give Access", callback_data="give_access")])
        keyboard.append([InlineKeyboardButton("🚫 Block User", callback_data="block_user")])
    
    await update.message.reply_text(
        "🤖 **Loader Key Bot**\n\nClick 'Get Key' to get your key",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- GIVE ACCESS PANEL ----------
async def give_access_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Admin only!")
        return
    
    await query.edit_message_text(
        "👑 **Give User Access**\n\n"
        "Send user ID:\n"
        "`/grant USER_ID`\n\n"
        "Example: `/grant 123456789`\n\n"
        "To remove access:\n"
        "`/revoke USER_ID`",
        parse_mode="Markdown"
    )

async def grant_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: `/grant USER_ID`", parse_mode="Markdown")
        return
    
    try:
        user_id = int(context.args[0])
        users_col.update_one({"_id": user_id}, {"$set": {"access": True, "role": "user"}}, upsert=True)
        await update.message.reply_text(f"✅ User `{user_id}` now has access!", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Invalid user ID!")

async def revoke_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: `/revoke USER_ID`", parse_mode="Markdown")
        return
    
    try:
        user_id = int(context.args[0])
        users_col.update_one({"_id": user_id}, {"$set": {"access": False}})
        await update.message.reply_text(f"✅ Access revoked for `{user_id}`!", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Invalid user ID!")

# ---------- BLOCK USER PANEL ----------
async def block_user_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("❌ Admin only!")
        return
    
    await query.edit_message_text(
        "🚫 **Block User**\n\n"
        "Send user ID:\n"
        "`/blockuser USER_ID`\n\n"
        "Example: `/blockuser 123456789`\n\n"
        "To unblock:\n"
        "`/unblockuser USER_ID`",
        parse_mode="Markdown"
    )

async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: `/blockuser USER_ID`", parse_mode="Markdown")
        return
    
    try:
        user_id = int(context.args[0])
        users_col.update_one({"_id": user_id}, {"$set": {"blocked": True, "access": False}})
        await update.message.reply_text(f"✅ User `{user_id}` blocked!", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Invalid user ID!")

async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: `/unblockuser USER_ID`", parse_mode="Markdown")
        return
    
    try:
        user_id = int(context.args[0])
        users_col.update_one({"_id": user_id}, {"$set": {"blocked": False}})
        await update.message.reply_text(f"✅ User `{user_id}` unblocked!", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Invalid user ID!")

# ---------- GET KEY (USER) ----------
async def get_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if not has_access(user_id):
        await query.edit_message_text("❌ Access Denied! Contact admin.")
        return
    
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
    
    user_id = update.effective_user.id
    if not has_access(user_id):
        await query.edit_message_text("❌ Access Denied!")
        return
    
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
    
    if not has_access(user_id):
        await query.edit_message_text("❌ Access Denied!")
        return
    
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

# ---------- ADD KEY (ADMIN) - BULK ----------
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
    
    # Show users with access
    users_with_access = users_col.count_documents({"access": True})
    message += f"\n👥 **Users with access:** {users_with_access}"
    message += f"\n📊 **Total Available Keys:** {total}"
    
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

# ---------- REFERRAL ----------
async def create_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        await update.message.reply_text("❌ Access Denied!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: `/create NAME`", parse_mode="Markdown")
        return
    
    name = context.args[0]
    code = generate_referral_code()
    
    referrals_col.insert_one({
        "code": code, "name": name, "created_by": update.effective_user.id,
        "created_at": datetime.now(), "redeemed_by": None, "blocked": False
    })
    
    await update.message.reply_text(
        f"✅ **Referral Created!**\n\n📛 Name: {name}\n🔗 Code: `{code}`\n\nShare: `/redeem {code}`",
        parse_mode="Markdown"
    )

async def redeem_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_access(update.effective_user.id):
        await update.message.reply_text("❌ Access Denied!")
        return
    
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
    
    # Give 7-day free key
    expiry = datetime.now() + timedelta(days=7)
    key = f"REF-{generate_referral_code()}"
    
    keys_col.insert_one({
        "key": key, "loader": "REFERRAL REWARD", "duration": "7d",
        "expiry": expiry, "used": False, "used_by": None,
        "created_by": update.effective_user.id, "created_at": datetime.now()
    })
    
    await update.message.reply_text(
        f"🎉 **Referral Redeemed!**\n\n📛 Name: {ref['name']}\n🔑 Your key: `{key}`\n⏳ Valid for 7 days",
        parse_mode="Markdown"
    )

async def block_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only!")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: `/blockref CODE`", parse_mode="Markdown")
        return
    
    code = context.args[0]
    result = referrals_col.update_one({"code": code}, {"$set": {"blocked": True}})
    
    if result.modified_count:
        await update.message.reply_text(f"✅ Referral `{code}` blocked!")
    else:
        await update.message.reply_text("❌ Referral not found!")

async def back_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_bulk_keys'):
        await process_add_keys(update, context)
    else:
        if not has_access(update.effective_user.id):
            await update.message.reply_text("❌ Access Denied! Contact @Flame_AI_Support")
        else:
            await update.message.reply_text("⚠️ Use /start")

# ---------- MAIN ----------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset_key))
    app.add_handler(CommandHandler("grant", grant_access))
    app.add_handler(CommandHandler("revoke", revoke_access))
    app.add_handler(CommandHandler("blockuser", block_user))
    app.add_handler(CommandHandler("unblockuser", unblock_user))
    app.add_handler(CommandHandler("create", create_referral))
    app.add_handle
