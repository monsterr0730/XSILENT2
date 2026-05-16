import logging
import random
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient

# ---------- CONFIG ----------
BOT_TOKEN = "8466296023:AAHHz4iBpDWwZJgZABOapwlFRHn8f51uC6w"
ADMIN_ID = 7192516189
MONGO_URI = "mongodb+srv://mohitrao83076_db_user:LugF1xwlenkWRE1F@monster.ydmmckl.mongodb.net/?retryWrites=true&w=majority&appName=MONSTER"

# ---------- MongoDB Setup ----------
client = MongoClient(MONGO_URI)
db = client["loader_bot"]
keys_col = db["keys"]
users_col = db["users"]

# ---------- Loader List ----------
LOADERS = [
    "X SILENT", "DEFEND MOD", "KING ANDROID LOADER + MOD", "WAR LOADER & MOD",
    "FUNBOX PRO IMGUI JAVA & MOD", "DULUX MOD + LOADER", "MARS LOADER", "FRACTION LOADER",
    "BRAX", "TAPA TAP", "BGMI CHEAT", "ZTRX LOADER", "GPS LOADER", "RAB LOADER",
    "NUCLEAR LOADER", "BHAGWA LOADER", "1v100 LOADER & MOD", "BGMI BOX LOADER",
    "PAID LOADER", "Vex loder"
]

# ---------- Helper Functions ----------
def parse_duration(duration_str):
    duration_str = str(duration_str).strip().lower()
    if 'h' in duration_str:
        hours = int(duration_str.replace('h', ''))
        return timedelta(hours=hours)
    else:
        days = int(duration_str.replace('d', ''))
        return timedelta(days=days)

# ---------- /start Command ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not users_col.find_one({"_id": user_id}):
        role = "admin" if user_id == ADMIN_ID else "user"
        users_col.insert_one({"_id": user_id, "role": role})
    
    keyboard = [[InlineKeyboardButton("🎮 Get Key", callback_data="get_key")]]
    
    if users_col.find_one({"_id": user_id})["role"] == "admin":
        keyboard.append([InlineKeyboardButton("➕ Add Key", callback_data="add_key_admin")])
        keyboard.append([InlineKeyboardButton("📊 Check Keys", callback_data="check_keys")])
    
    await update.message.reply_text(
        "🤖 **Loader Key Bot**\n\n"
        "Click 'Get Key' to get your key",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- GET KEY - Show Loaders with Available Count ----------
async def get_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for i, loader in enumerate(LOADERS):
        # Count available keys for this loader
        available_count = keys_col.count_documents({
            "loader": loader,
            "used": False,
            "expiry": {"$gt": datetime.now()}
        })
        
        # Show loader name with available count
        if available_count > 0:
            keyboard.append([InlineKeyboardButton(f"✅ {loader} ({available_count} keys)", callback_data=f"select_loader_{i}")])
        else:
            keyboard.append([InlineKeyboardButton(f"❌ {loader} (0 keys)", callback_data=f"no_key_{i}")])
    
    await query.edit_message_text(
        "📦 **Select Loader:**\n\n✅ = Keys available | ❌ = No keys",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- No Key Handler ----------
async def no_key_available(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "❌ **No keys available in this loader!**\n\n"
        "Please contact admin to add keys.\n\n"
        "Try another loader:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back to Loaders", callback_data="get_key")]])
    )

# ---------- Select Duration (Only if keys available) ----------
async def select_loader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    loader_idx = int(query.data.split('_')[2])
    loader_name = LOADERS[loader_idx]
    context.user_data['selected_loader'] = loader_name
    
    # Debug: Print to console
    print(f"Selected loader: {loader_name}")
    
    # Get available durations for this loader
    durations = keys_col.distinct("duration", {
        "loader": loader_name,
        "used": False,
        "expiry": {"$gt": datetime.now()}
    })
    
    print(f"Found durations: {durations}")
    
    if not durations:
        await query.edit_message_text(
            f"❌ **No keys available for {loader_name}**\n\nContact admin",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="get_key")]])
        )
        return
    
    # Sort durations
    duration_order = {"5h": 1, "1d": 2, "7d": 3, "14d": 4, "30d": 5, "60d": 6}
    durations.sort(key=lambda x: duration_order.get(x, 99))
    
    keyboard = []
    for dur in durations:
        # Count how many keys available for this duration
        count = keys_col.count_documents({
            "loader": loader_name,
            "duration": dur,
            "used": False,
            "expiry": {"$gt": datetime.now()}
        })
        keyboard.append([InlineKeyboardButton(f"⏳ {dur} ({count} keys)", callback_data=f"duration_{dur}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Back", callback_data="get_key")])
    
    await query.edit_message_text(
        f"✅ Loader: **{loader_name}**\n\n⏳ **Select Duration:**\n(Showing available keys count)",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- Get Key from Database ----------
async def get_key_from_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    duration = query.data.split('_')[1]
    loader = context.user_data['selected_loader']
    
    print(f"Looking for key - Loader: {loader}, Duration: {duration}")
    
    # Find available key
    available_key = keys_col.find_one({
        "loader": loader,
        "duration": duration,
        "used": False,
        "expiry": {"$gt": datetime.now()}
    })
    
    print(f"Found key: {available_key}")
    
    if not available_key:
        await query.edit_message_text(
            f"❌ **No Key Available!**\n\n"
            f"Loader: {loader}\n"
            f"Duration: {duration}\n\n"
            f"📢 Keys might be out of stock. Contact admin.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Try Again", callback_data="get_key")]])
        )
        return
    
    # Mark key as used
    keys_col.update_one(
        {"_id": available_key["_id"]},
        {"$set": {"used": True, "used_by": update.effective_user.id, "used_at": datetime.now()}}
    )
    
    # Show key with copy button
    await query.edit_message_text(
        f"✅ **Key Found!**\n\n"
        f"🔑 `{available_key['key']}`\n"
        f"📦 Loader: {loader}\n"
        f"⏳ Duration: {duration}\n"
        f"⏰ Expires: {available_key['expiry'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"✨ **Tap the key to copy** ✨",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 Copy Key", copy_text=available_key['key'])
        ], [
            InlineKeyboardButton("◀️ Get Another Key", callback_data="get_key")
        ]])
    )

# ---------- ADD KEY (Admin Only) ----------
async def add_key_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "➕ **Add New Key**\n\n"
        "Send key in this format:\n"
        "`loader | duration | key`\n\n"
        "**Examples:**\n"
        "`X SILENT | 30d | VEX-ABC123`\n"
        "`DEFEND MOD | 5h | DEFEND-999`\n"
        "`Vex loder | 7d | VEX-777`\n\n"
        "**Durations:** 1d, 5h, 7d, 14d, 30d, 60d\n\n"
        "Send /cancel to cancel",
        parse_mode="Markdown"
    )
    context.user_data['awaiting_key'] = True

# ---------- Process Add Key ----------
async def process_add_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_key'):
        return
    
    user_id = update.effective_user.id
    user = users_col.find_one({"_id": user_id})
    
    if not user or user["role"] != "admin":
        await update.message.reply_text("❌ Only admin can add keys.")
        context.user_data['awaiting_key'] = False
        return
    
    if update.message.text == "/cancel":
        context.user_data['awaiting_key'] = False
        await update.message.reply_text("❌ Cancelled.")
        return
    
    try:
        parts = [p.strip() for p in update.message.text.split('|')]
        if len(parts) != 3:
            raise ValueError("Invalid format")
        
        loader_name, duration_str, key = parts
        
        # Check if loader exists
        if loader_name not in LOADERS:
            await update.message.reply_text(f"❌ Loader '{loader_name}' not found!\nAvailable loaders: {', '.join(LOADERS[:5])}...")
            return
        
        # Check if key already exists
        if keys_col.find_one({"key": key}):
            await update.message.reply_text("❌ This key already exists!")
            context.user_data['awaiting_key'] = False
            return
        
        # Calculate expiry
        duration = parse_duration(duration_str)
        expiry = datetime.now() + duration
        
        # Save to database
        keys_col.insert_one({
            "key": key,
            "loader": loader_name,
            "duration": duration_str,
            "expiry": expiry,
            "used": False,
            "used_by": None,
            "created_by": user_id,
            "created_at": datetime.now()
        })
        
        # Show how many keys now available for this loader
        total_available = keys_col.count_documents({
            "loader": loader_name,
            "used": False,
            "expiry": {"$gt": datetime.now()}
        })
        
        await update.message.reply_text(
            f"✅ **Key Added Successfully!**\n\n"
            f"🔑 `{key}`\n"
            f"📦 Loader: {loader_name}\n"
            f"⏳ Duration: {duration_str}\n"
            f"⏰ Expires: {expiry.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"📊 Now {total_available} keys available in {loader_name}",
            parse_mode="Markdown"
        )
        
        context.user_data['awaiting_key'] = False
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ **Invalid Format!**\n\n"
            f"Use: `loader | duration | key`\n"
            f"Example: `X SILENT | 30d | VEX-ABC123`\n\n"
            f"Send /cancel to cancel",
            parse_mode="Markdown"
        )

# ---------- CHECK KEYS (Admin Only) ----------
async def check_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for loader in LOADERS:
        total = keys_col.count_documents({"loader": loader})
        available = keys_col.count_documents({
            "loader": loader, 
            "used": False, 
            "expiry": {"$gt": datetime.now()}
        })
        used = keys_col.count_documents({"loader": loader, "used": True})
        expired = keys_col.count_documents({"loader": loader, "expiry": {"$lt": datetime.now()}})
        
        keyboard.append([InlineKeyboardButton(
            f"📁 {loader} - ✅{available} | ❌{used} | ⏰{expired}", 
            callback_data=f"view_keys_{loader}"
        )])
    
    keyboard.append([InlineKeyboardButton("◀️ Back", callback_data="back_start")])
    
    await query.edit_message_text(
        "📊 **Key Statistics**\n\nClick any loader to see all keys:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- View Keys of Specific Loader ----------
async def view_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    loader_name = query.data.split('_', 2)[2]
    
    # Get all keys for this loader
    all_keys = list(keys_col.find({"loader": loader_name}).sort("created_at", -1).limit(50))
    
    if not all_keys:
        await query.edit_message_text(
            f"📁 **{loader_name}**\n\nNo keys found.\nUse 'Add Key' to add keys.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="check_keys")]])
        )
        return
    
    message = f"📁 **{loader_name}**\n\n"
    available_count = 0
    for key_data in all_keys[:20]:
        if not key_data['used'] and key_data['expiry'] > datetime.now():
            status = "✅ Available"
            available_count += 1
        elif key_data['used']:
            status = "❌ Used"
        else:
            status = "⏰ Expired"
        message += f"🔑 `{key_data['key']}`\n   ⏳ {key_data['duration']} | {status}\n\n"
    
    message = f"📁 **{loader_name}** (✅ Available: {available_count})\n\n" + message.split('\n\n', 1)[1] if available_count > 0 else message
    
    if len(all_keys) > 20:
        message += f"\n*Showing last 20 of {len(all_keys)} keys*"
    
    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="check_keys")]])
    )

# ---------- RESET KEY Command ----------
async def reset_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /reset <key>")
        return
    
    key = context.args[0]
    key_data = keys_col.find_one({"key": key})
    
    if not key_data:
        await update.message.reply_text("❌ Key not found!")
        return
    
    await context.bot.send_message(
        ADMIN_ID,
        f"⚠️ **Reset Request**\n"
        f"Key: `{key}`\n"
        f"Loader: {key_data['loader']}\n"
        f"Requested by: {update.effective_user.id}",
        parse_mode="Markdown"
    )
    
    await update.message.reply_text(f"✅ Reset request sent to admin for key: `{key}`", parse_mode="Markdown")

# ---------- Back to Start ----------
async def back_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

# ---------- Handle Messages ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_key'):
        await process_add_key(update, context)
    else:
        await update.message.reply_text(
            "⚠️ Use /start to get keys"
        )

# ---------- Main ----------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset_key))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(get_key, pattern="^get_key$"))
    app.add_handler(CallbackQueryHandler(select_loader, pattern="^select_loader_"))
    app.add_handler(CallbackQueryHandler(no_key_available, pattern="^no_key_"))
    app.add_handler(CallbackQueryHandler(get_key_from_db, pattern="^duration_"))
    app.add_handler(CallbackQueryHandler(add_key_admin, pattern="^add_key_admin$"))
    app.add_handler(CallbackQueryHandler(check_keys, pattern="^check_keys$"))
    app.add_handler(CallbackQueryHandler(view_keys, pattern="^view_keys_"))
    app.add_handler(CallbackQueryHandler(back_start, pattern="^back_start$"))
    
    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot Started! Debug mode ON...")
    print(f"Total keys in DB: {keys_col.count_documents({})}")
    
    # Show all keys for debugging
    all_keys = list(keys_col.find({}))
    for k in all_keys:
        print(f"Key: {k['key']}, Loader: {k['loader']}, Duration: {k['duration']}, Used: {k['used']}, Expiry: {k['expiry']}")
    
    app.run_polling()

if __name__ == "__main__":
    main()
