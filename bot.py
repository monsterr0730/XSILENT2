import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config
from database import Database
from panel import PanelAPI

# Initialize
db = Database()
panel = PanelAPI(config.PANEL_URL, config.PANEL_USERNAME, config.PANEL_PASSWORD)

def is_admin(user_id):
    return user_id == config.OWNER_ID or user_id in config.ADMIN_IDS

# ============= USER COMMANDS =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referred_by = context.args[0] if context.args else None
    
    if referred_by and int(referred_by) != user.id:
        db.add_referral(int(referred_by), user.id)
    
    db.add_user(user.id, user.username, user.first_name, referred_by)
    
    keyboard = [
        [InlineKeyboardButton("🔑 Generate Key", callback_data="generate")],
        [InlineKeyboardButton("📊 My Keys", callback_data="mykeys")],
        [InlineKeyboardButton("👥 Referral", callback_data="referral")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]
    
    if is_admin(user.id):
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin")])
    
    user_data = db.get_user(user.id)
    status = "✅ Approved" if (user_data and user_data.get("is_approved")) else "⏳ Pending"
    
    await update.message.reply_text(
        f"🔥 *XSILENT KEY GENERATOR* 🔥\n\n"
        f"👋 Welcome {user.first_name}!\n"
        f"📌 Status: {status}\n\n"
        f"✨ *Features:*\n"
        f"• Generate License Keys\n"
        f"• View Your Keys\n"
        f"• Referral Program\n\n"
        f"👇 *Select an option:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def request_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_approved(user.id):
        await update.message.reply_text("✅ You are already approved! Use /start to generate keys.")
        return
    
    request_id = db.add_request(user.id, "access_request")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}")]
    ])
    
    for admin_id in config.ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"🆕 *New Access Request!*\n\n"
                f"👤 User: {user.first_name}\n"
                f"🆔 ID: `{user.id}`\n"
                f"📛 Username: @{user.username or 'N/A'}\n"
                f"📅 Request ID: #{request_id}\n\n"
                f"Click approve to grant access.",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except:
            pass
    
    await update.message.reply_text(
        "✅ *Request Sent!*\n\n"
        "Your request has been sent to admin.\n"
        "You will be notified once approved.",
        parse_mode='Markdown'
    )

async def generate_key_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    if not db.is_approved(user_id) and not is_admin(user_id):
        await query.answer("❌ You are not approved! Use /request", show_alert=True)
        return
    
    keyboard = [
        [InlineKeyboardButton("⏰ 5 Hours", callback_data="gen_5h")],
        [InlineKeyboardButton("📅 3 Days", callback_data="gen_3d")],
        [InlineKeyboardButton("📆 7 Days", callback_data="gen_7d")],
        [InlineKeyboardButton("📊 14 Days", callback_data="gen_14d")],
        [InlineKeyboardButton("🌟 30 Days", callback_data="gen_30d")],
        [InlineKeyboardButton("💎 60 Days", callback_data="gen_60d")],
        [InlineKeyboardButton("🔙 Back", callback_data="back")]
    ]
    
    await query.message.edit_text(
        "🔑 *Select Key Duration*\n\nChoose the validity period:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def generate_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    duration = query.data.replace("gen_", "")
    user_id = query.from_user.id
    
    duration_names = {
        '5h': '5 Hours', '3d': '3 Days', '7d': '7 Days',
        '14d': '14 Days', '30d': '30 Days', '60d': '60 Days'
    }
    
    await query.message.edit_text(
        f"🔄 *Generating {duration_names[duration]} Key...*\n\n"
        f"⏳ Connecting to panel...\n"
        f"🔐 Bypassing Cloudflare...\n\n"
        f"*Please wait 10-15 seconds*",
        parse_mode='Markdown'
    )
    
    key = panel.generate_key(duration)
    
    if key:
        db.save_key(key, duration_names[duration], user_id, user_id)
        await query.message.edit_text(
            f"✅ *KEY GENERATED SUCCESSFULLY!*\n\n"
            f"🎫 *Duration:* {duration_names[duration]}\n"
            f"🔑 *Your Key:*\n"
            f"`{key}`\n\n"
            f"📋 Copy and use in XSilent app.\n"
            f"⚠️ Valid for {duration_names[duration]} only!",
            parse_mode='Markdown'
        )
    else:
        await query.message.edit_text(
            f"❌ *Generation Failed!*\n\n"
            f"Could not generate {duration_names[duration]} key.\n\n"
            f"Possible issues:\n"
            f"• Panel is down\n"
            f"• Cloudflare blocking\n"
            f"• Try again later",
            parse_mode='Markdown'
        )

async def my_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    keys = db.get_user_keys(user_id)
    
    if not keys:
        await query.message.edit_text(
            "📭 *No Keys Found*\n\n"
            "You haven't generated any keys yet.\n"
            "Use 'Generate Key' to create one.",
            parse_mode='Markdown'
        )
        return
    
    message = "🔑 *Your Generated Keys*\n\n"
    for key in keys:
        status_emoji = "✅" if key['status'] == 'active' else "❌"
        message += f"{status_emoji} `{key['key_code']}`\n"
        message += f"   📆 {key['duration']} | {key['generated_date'][:10]}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
    await query.message.edit_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def referral_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    bot_info = await context.bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={user_id}"
    referral_count = db.get_referral_count(user_id)
    user_data = db.get_user(user_id)
    balance = user_data.get("balance", 0) if user_data else 0
    
    message = f"""
👥 *Referral Program*

🎁 *Earn 5 credits per referral!*

🔗 *Your Referral Link:*
`{referral_link}`

📊 *Total Referrals:* {referral_count}

💎 *Your Balance:* {balance} credits

✨ *How it works:*
1. Share your link with friends
2. They join using your link
3. You get 5 credits automatically
4. Use credits for premium keys

*Coming Soon:* Exchange credits for keys!
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
    await query.message.edit_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query if update.callback_query else None
    
    help_text = """
📚 *Help & Guide*

*Commands:*
/start - Show main menu
/request - Request access
/help - Show this help

*How to get key:*
1. Click 'Generate Key'
2. Select duration
3. Wait 10 seconds
4. Copy your key

*Available Durations:*
⏰ 5 Hours - Quick trial
📅 3 Days - Weekend access
📆 7 Days - Weekly pass
📊 14 Days - Two weeks
🌟 30 Days - Monthly
💎 60 Days - Best value

*Troubleshooting:*
• If generation fails, try again
• Wait 1 minute between attempts
• Contact admin for issues
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
    
    if query:
        await query.message.edit_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(help_text, parse_mode='Markdown')

# ============= ADMIN COMMANDS =============
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await query.answer("❌ Access Denied!", show_alert=True)
        return
    
    stats = db.get_stats()
    
    keyboard = [
        [InlineKeyboardButton("👥 Users List", callback_data="admin_users")],
        [InlineKeyboardButton("✅ Pending Approvals", callback_data="admin_pending")],
        [InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔑 Manage Keys", callback_data="admin_keys")],
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Back", callback_data="back")]
    ]
    
    await query.message.edit_text(
        f"👑 *Admin Panel*\n\n"
        f"📊 *Statistics:*\n"
        f"• Total Users: {stats['total_users']}\n"
        f"• Approved Users: {stats['approved_users']}\n"
        f"• Total Keys: {stats['total_keys']}\n"
        f"• Active Keys: {stats['active_keys']}\n"
        f"• Pending Requests: {stats['pending_requests']}\n\n"
        f"Select an option:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    users = db.get_all_users()
    
    if not users:
        await query.message.edit_text("No users found.")
        return
    
    message = "👥 *User List*\n\n"
    for user in users[:20]:
        status = "✅" if user.get("is_approved") else "⏳"
        message += f"{status} `{user['user_id']}` - {user.get('first_name', 'Unknown')} (@{user.get('username', 'N/A')})\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin")]]
    await query.message.edit_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pending = db.get_pending_requests()
    
    if not pending:
        await query.message.edit_text("✅ No pending requests!")
        return
    
    for req in pending:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{req['user_id']}")]
        ])
        
        await query.message.reply_text(
            f"📋 *Request #{str(req['_id'])[-6:]}*\n"
            f"👤 User: {req['user']['first_name']} (@{req['user'].get('username', 'N/A')})\n"
            f"🆔 ID: `{req['user_id']}`\n"
            f"📅 Date: {req['request_date'][:10]}\n",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.edit_text(
        "📢 *Broadcast Mode*\n\n"
        "Send me the message you want to broadcast to all approved users.\n\n"
        "Type /cancel to cancel.",
        parse_mode='Markdown'
    )
    context.user_data['broadcast_mode'] = True

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    stats = db.get_stats()
    
    message = f"""
📊 *Bot Statistics*

👥 *Users:*
• Total: {stats['total_users']}
• Approved: {stats['approved_users']}
• Pending: {stats['total_users'] - stats['approved_users']}

🔑 *Keys:*
• Total Generated: {stats['total_keys']}
• Active Keys: {stats['active_keys']}
• Blocked Keys: {stats['total_keys'] - stats['active_keys']}

📋 *Requests:*
• Total: {stats['total_requests']}
• Pending: {stats['pending_requests']}
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin")]]
    await query.message.edit_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def admin_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keys = db.get_all_keys()
    
    if not keys:
        await query.message.edit_text("No keys found.")
        return
    
    message = "🔑 *All Keys*\n\n"
    for key in keys[:10]:
        status = "✅" if key['status'] == 'active' else "❌"
        message += f"{status} `{key['key_code']}` - {key['duration']}\n"
        message += f"   👤 User: `{key['generated_for']}`\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin")]]
    await query.message.edit_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data.startswith("approve_"):
        user_id = int(data.split("_")[1])
        db.approve_user(user_id)
        
        await query.message.edit_text(f"✅ User `{user_id}` approved successfully!", parse_mode='Markdown')
        
        try:
            await context.bot.send_message(
                user_id,
                "✅ *Congratulations!*\n\n"
                "Your access has been approved!\n"
                "Use /start to generate keys.",
                parse_mode='Markdown'
            )
        except:
            pass

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('broadcast_mode'):
        return
    
    message = update.message.text
    user_id = update.effective_user.id
    
    if message == "/cancel":
        context.user_data['broadcast_mode'] = False
        await update.message.reply_text("❌ Broadcast cancelled.")
        return
    
    users = db.get_approved_users()
    sent = 0
    failed = 0
    
    status_msg = await update.message.reply_text(f"🔄 Broadcasting to {len(users)} users...")
    
    for uid in users:
        try:
            await context.bot.send_message(
                uid,
                f"📢 *Announcement*\n\n{message}",
                parse_mode='Markdown'
            )
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    db.save_broadcast(message, user_id, sent)
    
    await status_msg.edit_text(
        f"✅ *Broadcast Complete*\n\n"
        f"📤 Sent: {sent} users\n"
        f"❌ Failed: {failed} users",
        parse_mode='Markdown'
    )
    
    context.user_data['broadcast_mode'] = False

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await start(query, context)

# ============= MAIN FUNCTION =============
def main():
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("request", request_access))
    app.add_handler(CommandHandler("help", help_command))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(generate_key_menu, pattern="^generate$"))
    app.add_handler(CallbackQueryHandler(my_keys, pattern="^mykeys$"))
    app.add_handler(CallbackQueryHandler(referral_system, pattern="^referral$"))
    app.add_handler(CallbackQueryHandler(help_command, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(generate_key, pattern="^gen_"))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin$"))
    app.add_handler(CallbackQueryHandler(admin_users, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_pending, pattern="^admin_pending$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast, pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_keys, pattern="^admin_keys$"))
    app.add_handler(CallbackQueryHandler(handle_approval, pattern="^approve_"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back$"))
    
    # Message handler for broadcast
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast))
    
    print("=" * 50)
    print("🤖 MONSTER BOT - XSILENT KEY GENERATOR")
    print("=" * 50)
    print("✅ Bot Started!")
    print(f"✅ Owner ID: {config.OWNER_ID}")
    print(f"✅ MongoDB: Connected")
    print(f"✅ Panel: {config.PANEL_URL}")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
