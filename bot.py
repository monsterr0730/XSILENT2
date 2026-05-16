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
ADMIN_ID = 7192516189  # Apna Telegram ID daalo
MONGO_URI = "mongodb+srv://mohitrao83076_db_user:LugF1xwlenkWRE1F@monster.ydmmckl.mongodb.net/?retryWrites=true&w=majority&appName=MONSTER"

# ---------- CHECK MONGODB CONNECTION FIRST ----------
print("🔌 Checking MongoDB connection...")
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("✅ MongoDB connected successfully!")
except (ConnectionFailure, ServerSelectionTimeoutError) as e:
    print(f"❌ MongoDB connection failed: {e}")
    print("\n💡 Solutions:")
    print("1. Make sure MongoDB is installed: https://www.mongodb.com/try/download/community")
    print("2. Start MongoDB service:")
    print("   - Windows: net start MongoDB")
    print("   - Linux: sudo systemctl start mongod")
    print("   - Mac: brew services start mongodb-community")
    print("3. Or use MongoDB Atlas (cloud):")
    print("   - Sign up at https://www.mongodb.com/atlas")
    print("   - Get connection string and replace MONGO_URI")
    sys.exit(1)

# ---------- MongoDB Setup ----------
db = client["loader_bot"]
keys_col = db["keys"]
users_col = db["users"]

# ---------- Create Indexes ----------
keys_col.create_index("key", unique=True)
keys_col.create_index([("loader", 1), ("used", 1), ("expiry", 1)])

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
        try:
            available_count = keys_col.count_documents({
                "loader": loader,
                "used": False,
                "expiry": {"$gt": datetime.now()}
            })
        except Exception as e:
            available_count = 0
        
        if available_count > 0:
            keyboard.append([InlineKeyboardButton(f"✅ {loader} ({available_count})", callback_data=f"loader_{i}")])
        else:
            keyboard.append([InlineKeyboardButton(f"❌ {loader} (0)", callback_data=f"noloader_{i}")])
    
    await query.edit_message_text(
        "📦 **Select Loader:**\n\n✅ = Keys available | ❌ = No keys",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- No Key Handler ----------
async def no_key_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "❌ **No keys available!**\n\n"
        "Contact admin to add keys.\n\n"
        "Try another loader:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="get_key")]])
    )

# ---------- Show Durations for Selected Loader ----------
async def show_durations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    loader_idx = int(query.data.split('_')[1])
    loader_name = LOADERS[loader_idx]
    context.user_data['selected_loader'] = loader_name
    
    try:
        # Get all available keys for this loader
        available_keys = list(keys_col.find({
            "loader": loader_name,
            "used": False,
            "expiry": {"$gt": datetime.now()}
        }))
        
        if not available_keys:
            await query.edit_message_text(
                f"❌ **No keys available for {loader_name}**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="get_key")]])
            )
            return
        
        # Group by duration
        durations = {}
        for key_data in available_keys:
            dur = key_data.get('duration', '30d')
            if dur not in durations:
                durations[dur] = 0
            durations[dur] += 1
        
        # Sort durations
        duration_order = {"5h": 1, "1d": 2, "7d": 3, "14d": 4, "30d": 5, "60d": 6}
        
        keyboard = []
        for dur in sorted(durations.keys(), key=lambda x: duration_order.get(x, 99)):
            keyboard.append([InlineKeyboardButton(f"⏳ {dur} ({durations[dur]} keys)", callback_data=f"dur_{dur}")])
        
        keyboard.append([InlineKeyboardButton("◀️ Back", callback_data="get_key")])
        
        await query.edit_message_text(
            f"✅ Loader: **{loader_name}**\n\n⏳ **Select Duration:**",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        await query.edit_message_text(
            f"❌ Error: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="get_key")]])
        )

# ---------- Get Key from Database ----------
async def get_final_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    duration = query.data.split('_')[1]
    loader = context.user_data.get('selected_loader')
    
    if not loader:
        await query.edit_message_text(
            "❌ Session expired! Please start again.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Start Over", callback_data="get_key")]])
        )
        return
    
    try:
        # Find one available key
        available_key = keys_col.find_one({
            "loader": loader,
            "duration": duration,
            "used": False,
            "expiry": {"$gt": datetime.now()}
        })
        
        if not available_key:
            # Try without duration filter (just in case)
            available_key = keys_col.find_one({
                "loader": loader,
                "used": False,
                "expiry": {"$gt": datetime.now()}
            })
        
        if not available_key:
            await query.edit_message_text(
                f"❌ **No key available!**\n\n"
                f"Loader: {loader}\n"
                f"Duration: {duration}\n\n"
                f"Contact admin to add more keys.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Try Again", callback_data="get_key")]])
            )
            return
        
        # Mark as used
        keys_col.update_one(
            {"_id": available_key["_id"]},
            {"$set": {"used": True, "used_by": update.effective_user.id, "used_at": datetime.now()}}
        )
        
        # Send key with copy button
        key_text = available_key['key']
        await query.edit_message_text(
            f"✅ **Here is your key!**\n\n"
            f"🔑 `{key_text}`\n"
            f"📦 Loader: {loader}\n"
            f"⏳ Duration: {duration}\n\n"
            f"✨ **Tap below to copy** ✨",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 Copy Key", copy_text=key_text)
            ], [
                InlineKeyboardButton("◀️ Get Another Key", callback_data="get_key")
            ]])
        )
        
    except Exception as e:
        await query.edit_message_text(
            f"❌ Error getting key: {str(e)}\n\nContact admin.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="get_key")]])
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
        "`DEFEND MOD | 5h | DEFEND-999`\n\n"
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
        
        # Check loader
        if loader_name not in LOADERS:
            await update.message.reply_text(f"❌ Loader '{loader_name}' not found!")
            return
        
        # Check duplicate
        if keys_col.find_one({"key": key}):
            await update.message.reply_text("❌ This key already exists!")
            context.user_data['awaiting_key'] = False
            return
        
        # Calculate expiry
        duration = parse_duration(duration_str)
        expiry = datetime.now() + duration
        
        # Save
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
        
        await update.message.reply_text(
            f"✅ **Key Added!**\n\n"
            f"🔑 `{key}`\n"
            f"📦 {loader_name}\n"
            f"⏳ {duration_str}",
            parse_mode="Markdown"
        )
        
        context.user_data['awaiting_key'] = False
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Invalid format!\nUse: `loader | duration | key`\nExample: `X SILENT | 30d | KEY123`",
            parse_mode="Markdown"
        )

# ---------- CHECK KEYS (Admin) ----------
async def check_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    message = "📊 **Key Statistics**\n\n"
    total_keys = 0
    total_available = 0
    
    for loader in LOADERS:
        available = keys_col.count_documents({
            "loader": loader, 
            "used": False, 
            "expiry": {"$gt": datetime.now()}
        })
        used = keys_col.count_documents({"loader": loader, "used": True})
        
        total_keys += available + used
        total_available += available
        
        if available > 0:
            message += f"✅ **{loader}** - {available} keys available\n"
        else:
            message += f"❌ **{loader}** - No keys\n"
    
    message += f"\n📊 **Total:** {total_available} keys available out of {total_keys}"
    
    keyboard = [[InlineKeyboardButton("➕ Add Key", callback_data="add_key_admin")],
                [InlineKeyboardButton("◀️ Back", callback_data="back_start")]]
    
    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- RESET KEY ----------
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
        f"Loader: {key_data.get('loader', 'Unknown')}",
        parse_mode="Markdown"
    )
    
    await update.message.reply_text(f"✅ Reset request sent to admin!")

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
            "⚠️ Use /start to get keys\n"
            "Use /reset KEY to request key reset"
        )

# ---------- MAIN ----------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset_key))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(get_key, pattern="^get_key$"))
    app.add_handler(CallbackQueryHandler(show_durations, pattern="^loader_"))
    app.add_handler(CallbackQueryHandler(no_key_handler, pattern="^noloader_"))
    app.add_handler(CallbackQueryHandler(get_final_key, pattern="^dur_"))
    app.add_handler(CallbackQueryHandler(add_key_admin, pattern="^add_key_admin$"))
    app.add_handler(CallbackQueryHandler(check_keys, pattern="^check_keys$"))
    app.add_handler(CallbackQueryHandler(back_start, pattern="^back_start$"))
    
    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot Started Successfully!")
    print(f"📊 Total keys in DB: {keys_col.count_documents({})}")
    
    app.run_polling()

if __name__ == "__main__":
    main()
