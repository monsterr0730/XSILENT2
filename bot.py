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

# ---------- CHECK MONGODB CONNECTION ----------
print("🔌 Checking MongoDB connection...")
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print("✅ MongoDB connected successfully!")
except (ConnectionFailure, ServerSelectionTimeoutError) as e:
    print(f"❌ MongoDB connection failed: {e}")
    sys.exit(1)

# ---------- MongoDB Setup ----------
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

def parse_duration(duration_str):
    duration_str = str(duration_str).strip().lower()
    if 'h' in duration_str:
        hours = int(duration_str.replace('h', ''))
        return timedelta(hours=hours)
    else:
        days = int(duration_str.replace('d', ''))
        return timedelta(days=days)

# ---------- /start ----------
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
        "🤖 **Loader Key Bot**\n\nClick 'Get Key' to get your key",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- GET KEY ----------
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
        except:
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

async def no_key_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "❌ **No keys available!**\n\nContact admin.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="get_key")]])
    )

# ---------- SHOW DURATIONS ----------
async def show_durations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    loader_idx = int(query.data.split('_')[1])
    loader_name = LOADERS[loader_idx]
    context.user_data['selected_loader'] = loader_name
    
    try:
        available_keys = list(keys_col.find({
            "loader": loader_name,
            "used": False,
            "expiry": {"$gt": datetime.now()}
        }))
        
        if not available_keys:
            await query.edit_message_text(
                f"❌ **No keys for {loader_name}**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="get_key")]])
            )
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
        
        await query.edit_message_text(
            f"✅ Loader: **{loader_name}**\n\n⏳ **Select Duration:**",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {str(e)}")

# ---------- GET FINAL KEY (FIXED - NO copy_text) ----------
async def get_final_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    duration = query.data.split('_')[1]
    loader = context.user_data.get('selected_loader')
    
    if not loader:
        await query.edit_message_text("❌ Session expired! Start over.")
        return
    
    try:
        available_key = keys_col.find_one({
            "loader": loader,
            "duration": duration,
            "used": False,
            "expiry": {"$gt": datetime.now()}
        })
        
        if not available_key:
            available_key = keys_col.find_one({
                "loader": loader,
                "used": False,
                "expiry": {"$gt": datetime.now()}
            })
        
        if not available_key:
            await query.edit_message_text(
                f"❌ **No key available!**\n\nLoader: {loader}\nDuration: {duration}\n\nContact admin.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Try Again", callback_data="get_key")]])
            )
            return
        
        # Mark as used
        keys_col.update_one(
            {"_id": available_key["_id"]},
            {"$set": {"used": True, "used_by": update.effective_user.id, "used_at": datetime.now()}}
        )
        
        key_text = available_key['key']
        
        # FIXED: No copy_text parameter - using message with selectable text
        await query.edit_message_text(
            f"✅ **Here is your key!**\n\n"
            f"🔑 `{key_text}`\n"
            f"📦 Loader: {loader}\n"
            f"⏳ Duration: {duration}\n\n"
            f"✨ **Copy this key** ✨\n"
            f"👉 `{key_text}` 👈\n\n"
            f"Tap and hold to copy, or select the text.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Get Another Key", callback_data="get_key")
            ]])
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {str(e)}\n\nContact admin.")

# ---------- ADD KEY (ADMIN) ----------
async def add_key_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "➕ **Add New Key**\n\nSend:\n`loader | duration | key`\n\nExamples:\n`X SILENT | 30d | VEX-ABC123`\n`DEFEND MOD | 5h | DEFEND-999`\n\nDurations: 1d, 5h, 7d, 14d, 30d, 60d\n\nSend /cancel",
        parse_mode="Markdown"
    )
    context.user_data['awaiting_key'] = True

async def process_add_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_key'):
        return
    
    user_id = update.effective_user.id
    user = users_col.find_one({"_id": user_id})
    
    if not user or user["role"] != "admin":
        await update.message.reply_text("❌ Only admin.")
        context.user_data['awaiting_key'] = False
        return
    
    if update.message.text == "/cancel":
        context.user_data['awaiting_key'] = False
        await update.message.reply_text("❌ Cancelled.")
        return
    
    try:
        parts = [p.strip() for p in update.message.text.split('|')]
        if len(parts) != 3:
            raise ValueError()
        
        loader_name, duration_str, key = parts
        
        if loader_name not in LOADERS:
            await update.message.reply_text(f"❌ Loader not found!")
            return
        
        if keys_col.find_one({"key": key}):
            await update.message.reply_text("❌ Key exists!")
            context.user_data['awaiting_key'] = False
            return
        
        duration = parse_duration(duration_str)
        expiry = datetime.now() + duration
        
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
        
        await update.message.reply_text(f"✅ **Key Added!**\n🔑 `{key}`\n📦 {loader_name}\n⏳ {duration_str}", parse_mode="Markdown")
        context.user_data['awaiting_key'] = False
        
    except:
        await update.message.reply_text("❌ Invalid! Use: `loader | duration | key`", parse_mode="Markdown")

# ---------- CHECK KEYS ----------
async def check_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    message = "📊 **Key Statistics**\n\n"
    total_available = 0
    
    for loader in LOADERS:
        available = keys_col.count_documents({
            "loader": loader, 
            "used": False, 
            "expiry": {"$gt": datetime.now()}
        })
        total_available += available
        
        if available > 0:
            message += f"✅ **{loader}** - {available} keys\n"
        else:
            message += f"❌ **{loader}** - 0 keys\n"
    
    message += f"\n📊 **Total Available:** {total_available} keys"
    
    keyboard = [[InlineKeyboardButton("➕ Add Key", callback_data="add_key_admin")],
                [InlineKeyboardButton("◀️ Back", callback_data="back_start")]]
    
    await query.edit_message_text(message, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def reset_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /reset <key>")
        return
    
    key = context.args[0]
    key_data = keys_col.find_one({"key": key})
    
    if not key_data:
        await update.message.reply_text("❌ Key not found!")
        return
    
    await context.bot.send_message(ADMIN_ID, f"⚠️ **Reset Request**\n🔑 `{key}`\n📦 {key_data.get('loader', 'Unknown')}", parse_mode="Markdown")
    await update.message.reply_text(f"✅ Reset request sent!")

async def back_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_key'):
        await process_add_key(update, context)
    else:
        await update.message.reply_text("⚠️ Use /start to get keys")

# ---------- MAIN ----------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset_key))
    
    app.add_handler(CallbackQueryHandler(get_key, pattern="^get_key$"))
    app.add_handler(CallbackQueryHandler(show_durations, pattern="^loader_"))
    app.add_handler(CallbackQueryHandler(no_key_handler, pattern="^noloader_"))
    app.add_handler(CallbackQueryHandler(get_final_key, pattern="^dur_"))
    app.add_handler(CallbackQueryHandler(add_key_admin, pattern="^add_key_admin$"))
    app.add_handler(CallbackQueryHandler(check_keys, pattern="^check_keys$"))
    app.add_handler(CallbackQueryHandler(back_start, pattern="^back_start$"))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot Started!")
    print(f"📊 Total keys: {keys_col.count_documents({})}")
    
    app.run_polling()

if __name__ == "__main__":
    main()
