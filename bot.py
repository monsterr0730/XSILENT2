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
loaders_col = db["loaders"]
keys_col = db["keys"]
referrals_col = db["referrals"]
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
    elif 'd' in duration_str:
        days = int(duration_str.replace('d', ''))
        return timedelta(days=days)
    else:
        days = int(duration_str)
        return timedelta(days=days)

def generate_referral_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

# ---------- /start Command ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not users_col.find_one({"_id": user_id}):
        role = "admin" if user_id == ADMIN_ID else "user"
        users_col.insert_one({"_id": user_id, "role": role})
    
    keyboard = [[InlineKeyboardButton("🎮 Select Loader", callback_data="select_loader")]]
    
    if users_col.find_one({"_id": user_id})["role"] == "admin":
        keyboard.append([InlineKeyboardButton("➕ Add Bulk Keys", callback_data="bulk_add_menu")])
        keyboard.append([InlineKeyboardButton("📊 Manage Loaders", callback_data="manage_loaders")])
    
    await update.message.reply_text(
        "🎮 Welcome to Loader Key Bot!\n\n"
        "🔑 Users: Select loader to get key\n"
        "👑 Admin: Add keys & manage loaders",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- Select Loader (For Users) ----------
async def select_loader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for i, loader in enumerate(LOADERS):
        # Count available keys for this loader
        available_count = keys_col.count_documents({
            "loader": loader,
            "used_by": None,
            "expiry": {"$gt": datetime.now()}
        })
        keyboard.append([InlineKeyboardButton(f"{loader} (📦 {available_count})", callback_data=f"user_loader_{i}")])
    
    await query.edit_message_text(
        "📦 Select Loader to Get Key:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- Duration Selection (For Users) ----------
async def user_loader_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    loader_idx = int(query.data.split('_')[2])
    context.user_data['selected_loader'] = LOADERS[loader_idx]
    
    # Get available durations for this loader
    durations = keys_col.distinct("duration", {
        "loader": LOADERS[loader_idx],
        "used_by": None,
        "expiry": {"$gt": datetime.now()}
    })
    
    if not durations:
        await query.edit_message_text(
            f"❌ No keys available for {LOADERS[loader_idx]}\n\n"
            f"📢 Please DM to @OwnerUsername",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="select_loader")]])
        )
        return
    
    keyboard = []
    for dur in sorted(durations):
        keyboard.append([InlineKeyboardButton(f"⏳ {dur}", callback_data=f"user_duration_{dur}")])
    keyboard.append([InlineKeyboardButton("◀️ Back", callback_data="select_loader")])
    
    await query.edit_message_text(
        f"✅ Loader: {LOADERS[loader_idx]}\n⏳ Select Duration:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- Get Key (For Users) ----------
async def user_get_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    duration_str = query.data.split('_')[2]
    selected_loader = context.user_data['selected_loader']
    
    available_key = keys_col.find_one({
        "loader": selected_loader,
        "duration": duration_str,
        "used_by": None,
        "expiry": {"$gt": datetime.now()}
    })
    
    if not available_key:
        await query.edit_message_text(
            f"❌ Key not found for:\n📦 {selected_loader}\n⏳ {duration_str}\n\n"
            f"📢 Please DM to @OwnerUsername",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="select_loader")]])
        )
        return
    
    keys_col.update_one(
        {"_id": available_key["_id"]},
        {"$set": {"used_by": update.effective_user.id, "used_at": datetime.now()}}
    )
    
    keyboard = [[InlineKeyboardButton("📋 Copy Key", copy_text=available_key["key"])]]
    
    await query.edit_message_text(
        f"✅ Key Found!\n\n"
        f"🔑 `{available_key['key']}`\n"
        f"📦 Loader: {selected_loader}\n"
        f"⏳ Validity: {duration_str}\n"
        f"⏰ Expires: {available_key['expiry'].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"✨ Tap below to copy key:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- MANAGE LOADERS (Admin) ----------
async def manage_loaders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for i, loader in enumerate(LOADERS):
        total_keys = keys_col.count_documents({"loader": loader})
        available_keys = keys_col.count_documents({
            "loader": loader,
            "used_by": None,
            "expiry": {"$gt": datetime.now()}
        })
        expired_keys = keys_col.count_documents({
            "loader": loader,
            "expiry": {"$lt": datetime.now()}
        })
        
        keyboard.append([InlineKeyboardButton(
            f"📁 {loader}", 
            callback_data=f"view_loader_{i}"
        )])
        keyboard.append([InlineKeyboardButton(
            f"   📊 Total: {total_keys} | ✅ Available: {available_keys} | ⏰ Expired: {expired_keys}",
            callback_data="ignore"
        )])
    
    keyboard.append([InlineKeyboardButton("➕ Add Bulk Keys", callback_data="bulk_add_menu")])
    keyboard.append([InlineKeyboardButton("◀️ Back to Start", callback_data="back_start")])
    
    await query.edit_message_text(
        "👑 **Admin Panel - Manage Loaders**\n\nClick on any loader to view its keys:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- View Specific Loader Keys (Admin) ----------
async def view_loader_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    loader_idx = int(query.data.split('_')[2])
    loader_name = LOADERS[loader_idx]
    context.user_data['viewing_loader'] = loader_name
    
    # Pagination setup
    page = context.user_data.get('page', 0)
    per_page = 10
    
    keys_list = list(keys_col.find({"loader": loader_name}).sort("created_at", -1).skip(page * per_page).limit(per_page))
    total_keys = keys_col.count_documents({"loader": loader_name})
    
    if not keys_list:
        await query.edit_message_text(
            f"📁 **{loader_name}**\n\nNo keys found in this loader.\n\nUse 'Add Bulk Keys' to add keys.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Keys", callback_data="bulk_add_menu")],
                [InlineKeyboardButton("◀️ Back", callback_data="manage_loaders")]
            ])
        )
        return
    
    message = f"📁 **{loader_name}**\n\n"
    for key_data in keys_list:
        status = "✅ Available" if key_data['used_by'] is None and key_data['expiry'] > datetime.now() else "❌ Used" if key_data['used_by'] else "⏰ Expired"
        message += f"🔑 `{key_data['key']}`\n   ⏳ {key_data['duration']} | {status}\n"
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"loader_page_{page-1}"))
    if (page + 1) * per_page < total_keys:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"loader_page_{page+1}"))
    
    keyboard = [nav_buttons] if nav_buttons else []
    keyboard.append([InlineKeyboardButton("➕ Add Keys to This Loader", callback_data=f"bulk_add_to_{loader_idx}")])
    keyboard.append([InlineKeyboardButton("◀️ Back to Loaders", callback_data="manage_loaders")])
    
    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- Bulk Add Menu (Admin) ----------
async def bulk_add_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for i, loader in enumerate(LOADERS):
        keyboard.append([InlineKeyboardButton(loader, callback_data=f"bulk_loader_{i}")])
    keyboard.append([InlineKeyboardButton("◀️ Back", callback_data="manage_loaders")])
    
    await query.edit_message_text(
        "➕ **Bulk Add Keys**\n\nSelect loader to add keys:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- Bulk Add to Specific Loader ----------
async def bulk_add_to_loader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    loader_idx = int(query.data.split('_')[2])
    loader_name = LOADERS[loader_idx]
    context.user_data['bulk_loader'] = loader_name
    
    await query.edit_message_text(
        f"➕ **Add Keys to: {loader_name}**\n\n"
        f"Send keys in this format:\n"
        f"`duration|key1,key2,key3`\n\n"
        f"**Example:**\n"
        f"`30d|Vex-5hisksj,Vex-5hisksjc,Vex-5hisksjv`\n\n"
        f"**Duration formats:** 1d, 5h, 7d, 14d, 30d, 60d\n\n"
        f"Send /cancel to cancel",
        parse_mode="Markdown"
    )
    context.user_data['awaiting_bulk_keys'] = True

# ---------- Process Bulk Keys ----------
async def process_bulk_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_bulk_keys'):
        return
    
    user_id = update.effective_user.id
    user = users_col.find_one({"_id": user_id})
    if not user or user["role"] != "admin":
        await update.message.reply_text("❌ Only admin can add keys.")
        context.user_data['awaiting_bulk_keys'] = False
        return
    
    if update.message.text == "/cancel":
        context.user_data['awaiting_bulk_keys'] = False
        await update.message.reply_text("❌ Cancelled bulk add.")
        return
    
    try:
        parts = update.message.text.split('|')
        if len(parts) != 2:
            raise ValueError("Invalid format")
        
        duration_str = parts[0].strip()
        keys_list = [k.strip() for k in parts[1].split(',')]
        
        # Validate duration
        duration = parse_duration(duration_str)
        expiry = datetime.now() + duration
        loader_name = context.user_data['bulk_loader']
        
        added = 0
        skipped = 0
        
        for key in keys_list:
            if keys_col.find_one({"key": key}):
                skipped += 1
                continue
            
            keys_col.insert_one({
                "key": key,
                "loader": loader_name,
                "duration": duration_str,
                "expiry": expiry,
                "used_by": None,
                "created_by": user_id,
                "created_at": datetime.now()
            })
            added += 1
        
        await update.message.reply_text(
            f"✅ **Bulk Add Complete!**\n\n"
            f"📦 Loader: {loader_name}\n"
            f"⏳ Duration: {duration_str}\n"
            f"✅ Added: {added} keys\n"
            f"⚠️ Skipped (duplicate): {skipped} keys",
            parse_mode="Markdown"
        )
        
        context.user_data['awaiting_bulk_keys'] = False
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Invalid format!\n\n"
            f"Use: `duration|key1,key2,key3`\n"
            f"Example: `30d|Vex-1,Vex-2,Vex-3`\n\n"
            f"Send /cancel to cancel",
            parse_mode="Markdown"
        )

# ---------- /reset key (Admin ko message) ----------
async def reset_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /reset <key>")
        return
    
    key = context.args[0]
    key_data = keys_col.find_one({"key": key})
    
    if not key_data:
        await update.message.reply_text("❌ Key not found.")
        return
    
    await context.bot.send_message(
        ADMIN_ID,
        f"⚠️ **KEY RESET REQUEST**\n"
        f"🔑 Key: `{key}`\n"
        f"📦 Loader: {key_data['loader']}\n"
        f"👤 Requested by: {update.effective_user.id}\n"
        f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        parse_mode="Markdown"
    )
    
    await update.message.reply_text(f"✅ Reset request sent to admin for key: `{key}`", parse_mode="Markdown")

# ---------- /refer & /redeem ----------
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
        "redeemed_by": None,
        "created_at": datetime.now()
    })
    
    await update.message.reply_text(
        f"✅ **Referral Code Created!**\n\n"
        f"🔗 Code: `{code}`\n"
        f"📛 Name: {name}\n\n"
        f"Share: /redeem {code}",
        parse_mode="Markdown"
    )

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /redeem <referral_code>")
        return
    
    code = context.args[0]
    ref = referrals_col.find_one({"code": code, "redeemed_by": None})
    
    if not ref:
        await update.message.reply_text("❌ Invalid or already redeemed code!")
        return
    
    referrals_col.update_one(
        {"code": code},
        {"$set": {"redeemed_by": update.effective_user.id, "redeemed_at": datetime.now()}}
    )
    
    await update.message.reply_text(f"🎉 Referral Redeemed! Name: {ref['name']}")

# ---------- Handle Other Messages ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_bulk_keys'):
        await process_bulk_keys(update, context)
    else:
        await update.message.reply_text(
            "⚠️ Use /start to get keys\n"
            "Use /redeem <code> to redeem referral"
        )

# ---------- Pagination Handler ----------
async def loader_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    page = int(query.data.split('_')[2])
    context.user_data['page'] = page
    await view_loader_keys(update, context)

# ---------- Back to Start ----------
async def back_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)

# ---------- Ignore Callback ----------
async def ignore_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

# ---------- Main ----------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset_key))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("redeem", redeem))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(select_loader, pattern="^select_loader$"))
    app.add_handler(CallbackQueryHandler(user_loader_selected, pattern="^user_loader_"))
    app.add_handler(CallbackQueryHandler(user_get_key, pattern="^user_duration_"))
    app.add_handler(CallbackQueryHandler(manage_loaders, pattern="^manage_loaders$"))
    app.add_handler(CallbackQueryHandler(view_loader_keys, pattern="^view_loader_"))
    app.add_handler(CallbackQueryHandler(loader_page, pattern="^loader_page_"))
    app.add_handler(CallbackQueryHandler(bulk_add_menu, pattern="^bulk_add_menu$"))
    app.add_handler(CallbackQueryHandler(bulk_add_to_loader, pattern="^bulk_loader_"))
    app.add_handler(CallbackQueryHandler(bulk_add_to_loader, pattern="^bulk_add_to_"))
    app.add_handler(CallbackQueryHandler(back_start, pattern="^back_start$"))
    app.add_handler(CallbackQueryHandler(ignore_callback, pattern="^ignore$"))
    
    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
