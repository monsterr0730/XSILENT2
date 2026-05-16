import asyncio
import cloudscraper
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient

# ============= CONFIGURATION =============
BOT_TOKEN = "8466296023:AAF98OCsdXnaN2x6CMEQN3L4TBxpvkUI2pM"
OWNER_ID = 7192516189
ADMIN_IDS = [7192516189]

# MongoDB
MONGODB_URI = "mongodb+srv://mohitrao83076_db_user:LugF1xwlenkWRE1F@monster.ydmmckl.mongodb.net/?retryWrites=true&w=majority&appName=MONSTER"

# Panel
PANEL_URL = "https://xsilent.shop/vip"
PANEL_USERNAME = "VIPKEY"
PANEL_PASSWORD = "roxym830"

# ============= DATABASE CLASS =============
class Database:
    def __init__(self):
        self.client = MongoClient(MONGODB_URI)
        self.db = self.client["monster_bot"]
        self.users = self.db.users
        self.keys = self.db.keys
        self.requests = self.db.requests
        self.broadcasts = self.db.broadcasts
        self.referrals = self.db.referrals
        
        self.users.create_index("user_id", unique=True)
        self.keys.create_index("key_code", unique=True)
    
    def add_user(self, user_id, username, first_name, referred_by=None):
        try:
            if not self.users.find_one({"user_id": user_id}):
                self.users.insert_one({
                    "user_id": user_id,
                    "username": username,
                    "first_name": first_name,
                    "is_approved": user_id == OWNER_ID or user_id in ADMIN_IDS,
                    "is_admin": user_id == OWNER_ID or user_id in ADMIN_IDS,
                    "join_date": datetime.now().isoformat(),
                    "total_keys": 0,
                    "balance": 0,
                    "referred_by": referred_by
                })
                return True
            return False
        except:
            return False
    
    def get_user(self, user_id):
        return self.users.find_one({"user_id": user_id})
    
    def approve_user(self, user_id):
        self.users.update_one({"user_id": user_id}, {"$set": {"is_approved": True}})
    
    def is_approved(self, user_id):
        user = self.get_user(user_id)
        return user["is_approved"] if user else False
    
    def is_admin(self, user_id):
        return user_id == OWNER_ID or user_id in ADMIN_IDS
    
    def get_all_users(self):
        return list(self.users.find({}, {"user_id": 1, "username": 1, "first_name": 1, "is_approved": 1}))
    
    def get_approved_users(self):
        return [user["user_id"] for user in self.users.find({"is_approved": True}, {"user_id": 1})]
    
    def save_key(self, key_code, duration, generated_by, generated_for):
        try:
            self.keys.insert_one({
                "key_code": key_code,
                "duration": duration,
                "generated_by": generated_by,
                "generated_for": generated_for,
                "generated_date": datetime.now().isoformat(),
                "status": "active"
            })
            self.users.update_one({"user_id": generated_for}, {"$inc": {"total_keys": 1}})
            return True
        except:
            return False
    
    def get_user_keys(self, user_id, limit=10):
        return list(self.keys.find({"generated_for": user_id}).sort("generated_date", -1).limit(limit))
    
    def add_request(self, user_id, duration):
        result = self.requests.insert_one({
            "user_id": user_id,
            "duration": duration,
            "request_date": datetime.now().isoformat(),
            "status": "pending"
        })
        return result.inserted_id
    
    def get_pending_requests(self):
        return list(self.requests.aggregate([
            {"$match": {"status": "pending"}},
            {"$lookup": {"from": "users", "localField": "user_id", "foreignField": "user_id", "as": "user"}},
            {"$unwind": "$user"},
            {"$sort": {"request_date": -1}}
        ]))
    
    def save_broadcast(self, message, sent_by, total_received):
        self.broadcasts.insert_one({
            "message": message,
            "sent_by": sent_by,
            "sent_date": datetime.now().isoformat(),
            "total_received": total_received
        })
    
    def add_referral(self, referrer_id, referred_id):
        if self.referrals.find_one({"referred_id": referred_id}):
            return False
        self.referrals.insert_one({
            "referrer_id": referrer_id,
            "referred_id": referred_id,
            "date": datetime.now().isoformat()
        })
        self.users.update_one({"user_id": referrer_id}, {"$inc": {"balance": 5}})
        return True
    
    def get_referral_count(self, user_id):
        return self.referrals.count_documents({"referrer_id": user_id})
    
    def get_stats(self):
        return {
            "total_users": self.users.count_documents({}),
            "approved_users": self.users.count_documents({"is_approved": True}),
            "total_keys": self.keys.count_documents({}),
            "active_keys": self.keys.count_documents({"status": "active"}),
            "pending_requests": self.requests.count_documents({"status": "pending"})
        }

# ============= PANEL CLASS =============
class PanelAPI:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True},
            delay=10
        )
        self.logged_in = False
        self.scraper.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        })
    
    def login(self):
        try:
            login_page = self.scraper.get(f'{PANEL_URL}/login')
            csrf_match = re.search(r'name="_token"\s+value="([^"]+)"', login_page.text)
            csrf_token = csrf_match.group(1) if csrf_match else ''
            
            response = self.scraper.post(f'{PANEL_URL}/login', data={
                'username': PANEL_USERNAME,
                'password': PANEL_PASSWORD,
                '_token': csrf_token
            })
            
            if response.status_code == 200:
                self.logged_in = True
                return True
            return False
        except:
            return False
    
    def generate_key(self, duration):
        try:
            if not self.logged_in:
                if not self.login():
                    return None
            
            duration_map = {'5h':'5_hours','3d':'3_days','7d':'7_days','14d':'14_days','30d':'30_days','60d':'60_days'}
            duration_value = duration_map.get(duration, duration)
            
            response = self.scraper.post(f'{PANEL_URL}/generate', data={
                'duration': duration_value,
                'max_devices': '1'
            })
            
            patterns = [
                r'[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}',
                r'[A-Z0-9]{16,32}',
                r'"key":"([^"]+)"',
                r'<code>([^<]+)</code>'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, response.text, re.IGNORECASE)
                if match:
                    return match.group(1) if match.groups() else match.group(0)
            return None
        except:
            return None

# ============= INITIALIZE =============
db = Database()
panel = PanelAPI()

# ============= BOT HANDLERS =============
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
    
    if db.is_admin(user.id):
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin")])
    
    user_data = db.get_user(user.id)
    status = "✅ Approved" if (user_data and user_data.get("is_approved")) else "⏳ Pending"
    
    await update.message.reply_text(
        f"🔥 *XSILENT KEY GENERATOR* 🔥\n\n"
        f"👋 Welcome {user.first_name}!\n"
        f"📌 Status: {status}\n\n"
        f"👇 *Select an option:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def request_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_approved(user.id):
        await update.message.reply_text("✅ You are already approved!")
        return
    
    db.add_request(user.id, "access_request")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}")]
    ])
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"🆕 *New Request!*\n👤 {user.first_name}\n🆔 `{user.id}`",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except:
            pass
    
    await update.message.reply_text("✅ Request sent to admin!")

async def generate_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    if not db.is_approved(user_id) and not db.is_admin(user_id):
        await query.answer("Not approved! Use /request", show_alert=True)
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
        "🔑 *Select Duration:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def generate_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    duration = query.data.replace("gen_", "")
    user_id = query.from_user.id
    
    names = {'5h':'5H','3d':'3D','7d':'7D','14d':'14D','30d':'30D','60d':'60D'}
    
    await query.message.edit_text(f"🔄 Generating {names[duration]} key...\n⏳ Please wait...")
    
    key = panel.generate_key(duration)
    
    if key:
        db.save_key(key, names[duration], user_id, user_id)
        await query.message.edit_text(
            f"✅ *KEY GENERATED!*\n\n🔑 `{key}`\n\nValid for {names[duration]}",
            parse_mode='Markdown'
        )
    else:
        await query.message.edit_text("❌ Failed! Try again.")

async def my_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keys = db.get_user_keys(query.from_user.id)
    
    if not keys:
        await query.message.edit_text("📭 No keys found.")
        return
    
    msg = "🔑 *Your Keys:*\n\n"
    for k in keys:
        msg += f"✅ `{k['key_code']}` - {k['duration']}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
    await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def referral_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    bot = await context.bot.get_me()
    link = f"https://t.me/{bot.username}?start={user_id}"
    count = db.get_referral_count(user_id)
    
    await query.message.edit_text(
        f"👥 *Referral Program*\n\n🔗 `{link}`\n📊 Referrals: {count}\n\nShare and earn!",
        parse_mode='Markdown'
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not db.is_admin(query.from_user.id):
        await query.answer("Access Denied!")
        return
    
    keyboard = [
        [InlineKeyboardButton("👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton("✅ Pending", callback_data="admin_pending")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Back", callback_data="back")]
    ]
    
    await query.message.edit_text("👑 *Admin Panel*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    users = db.get_all_users()
    
    msg = "👥 *Users:*\n\n"
    for u in users[:20]:
        status = "✅" if u['is_approved'] else "⏳"
        msg += f"{status} `{u['user_id']}` - {u.get('first_name', '?')}\n"
    
    await query.message.edit_text(msg, parse_mode='Markdown')

async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pending = db.get_pending_requests()
    
    if not pending:
        await query.message.edit_text("No pending requests!")
        return
    
    for req in pending:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{req['user_id']}")]
        ])
        await query.message.reply_text(
            f"📋 Request from {req['user']['first_name']}\nID: `{req['user_id']}`",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.message.edit_text("Send your broadcast message:")
    context.user_data['broadcast_mode'] = True

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    stats = db.get_stats()
    
    msg = f"📊 *Stats:*\n\n👥 Users: {stats['total_users']}\n✅ Approved: {stats['approved_users']}\n🔑 Keys: {stats['total_keys']}\n⏳ Pending: {stats['pending_requests']}"
    await query.message.edit_text(msg, parse_mode='Markdown')

async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = int(query.data.split("_")[1])
    
    db.approve_user(user_id)
    await query.message.edit_text(f"✅ User {user_id} approved!")
    
    try:
        await context.bot.send_message(user_id, "✅ You've been approved! Use /start")
    except:
        pass

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('broadcast_mode'):
        return
    
    msg = update.message.text
    users = db.get_approved_users()
    sent = 0
    
    status_msg = await update.message.reply_text(f"🔄 Sending to {len(users)} users...")
    
    for uid in users:
        try:
            await context.bot.send_message(uid, f"📢 *Announcement*\n\n{msg}", parse_mode='Markdown')
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    
    db.save_broadcast(msg, update.effective_user.id, sent)
    await status_msg.edit_text(f"✅ Sent to {sent} users")
    context.user_data['broadcast_mode'] = False

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query if update.callback_query else None
    text = "📚 *Commands:*\n/start - Menu\n/request - Get access\n/help - This help"
    
    if query:
        await query.message.edit_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, parse_mode='Markdown')

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await start(query, context)

# ============= MAIN =============
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("request", request_access))
    app.add_handler(CommandHandler("help", help_command))
    
    app.add_handler(CallbackQueryHandler(generate_menu, pattern="^generate$"))
    app.add_handler(CallbackQueryHandler(my_keys, pattern="^mykeys$"))
    app.add_handler(CallbackQueryHandler(referral_system, pattern="^referral$"))
    app.add_handler(CallbackQueryHandler(generate_key, pattern="^gen_"))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin$"))
    app.add_handler(CallbackQueryHandler(admin_users, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_pending, pattern="^admin_pending$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast, pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(handle_approval, pattern="^approve_"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back$"))
    app.add_handler(CallbackQueryHandler(help_command, pattern="^help$"))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast))
    
    print("=" * 50)
    print("🤖 MONSTER BOT RUNNING")
    print("=" * 50)
    print("✅ Bot Token: Set")
    print("✅ MongoDB: Connected")
    print("✅ Panel: Ready")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
