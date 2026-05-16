import asyncio
import cloudscraper
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient

# ============= CONFIGURATION (UPDATED TOKEN) =============
BOT_TOKEN = "8466296023:AAGgTRre3Y_NL7kvNAvDsdomJo6-p_1Vu80"  # <-- NAYA TOKEN
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
        try:
            self.client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            self.db = self.client["monster_bot"]
            self.users = self.db.users
            self.keys = self.db.keys
            self.requests = self.db.requests
            self.broadcasts = self.db.broadcasts
            self.referrals = self.db.referrals
            
            self.users.create_index("user_id", unique=True)
            self.keys.create_index("key_code", unique=True)
            print("✅ MongoDB Connected!")
        except Exception as e:
            print(f"❌ MongoDB Error: {e}")
    
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
        except Exception as e:
            print(f"Add user error: {e}")
            return False
    
    def get_user(self, user_id):
        try:
            return self.users.find_one({"user_id": user_id})
        except:
            return None
    
    def approve_user(self, user_id):
        try:
            self.users.update_one({"user_id": user_id}, {"$set": {"is_approved": True}})
        except:
            pass
    
    def is_approved(self, user_id):
        user = self.get_user(user_id)
        return user["is_approved"] if user else (user_id == OWNER_ID)
    
    def is_admin(self, user_id):
        return user_id == OWNER_ID or user_id in ADMIN_IDS
    
    def get_all_users(self):
        try:
            return list(self.users.find({}, {"user_id": 1, "username": 1, "first_name": 1, "is_approved": 1}))
        except:
            return []
    
    def get_approved_users(self):
        try:
            return [user["user_id"] for user in self.users.find({"is_approved": True}, {"user_id": 1})]
        except:
            return []
    
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
        try:
            return list(self.keys.find({"generated_for": user_id}).sort("generated_date", -1).limit(limit))
        except:
            return []
    
    def add_request(self, user_id, duration):
        try:
            result = self.requests.insert_one({
                "user_id": user_id,
                "duration": duration,
                "request_date": datetime.now().isoformat(),
                "status": "pending"
            })
            return result.inserted_id
        except:
            return None
    
    def get_pending_requests(self):
        try:
            return list(self.requests.aggregate([
                {"$match": {"status": "pending"}},
                {"$lookup": {"from": "users", "localField": "user_id", "foreignField": "user_id", "as": "user"}},
                {"$unwind": "$user"},
                {"$sort": {"request_date": -1}}
            ]))
        except:
            return []
    
    def save_broadcast(self, message, sent_by, total_received):
        try:
            self.broadcasts.insert_one({
                "message": message,
                "sent_by": sent_by,
                "sent_date": datetime.now().isoformat(),
                "total_received": total_received
            })
        except:
            pass
    
    def add_referral(self, referrer_id, referred_id):
        try:
            if self.referrals.find_one({"referred_id": referred_id}):
                return False
            self.referrals.insert_one({
                "referrer_id": referrer_id,
                "referred_id": referred_id,
                "date": datetime.now().isoformat()
            })
            self.users.update_one({"user_id": referrer_id}, {"$inc": {"balance": 5}})
            return True
        except:
            return False
    
    def get_referral_count(self, user_id):
        try:
            return self.referrals.count_documents({"referrer_id": user_id})
        except:
            return 0
    
    def get_stats(self):
        try:
            return {
                "total_users": self.users.count_documents({}),
                "approved_users": self.users.count_documents({"is_approved": True}),
                "total_keys": self.keys.count_documents({}),
                "active_keys": self.keys.count_documents({"status": "active"}),
                "pending_requests": self.requests.count_documents({"status": "pending"})
            }
        except:
            return {"total_users": 0, "approved_users": 0, "total_keys": 0, "active_keys": 0, "pending_requests": 0}

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
            print("🔄 Logging to panel...")
            login_page = self.scraper.get(f'{PANEL_URL}/login', timeout=30)
            csrf_match = re.search(r'name="_token"\s+value="([^"]+)"', login_page.text)
            csrf_token = csrf_match.group(1) if csrf_match else ''
            
            response = self.scraper.post(f'{PANEL_URL}/login', data={
                'username': PANEL_USERNAME,
                'password': PANEL_PASSWORD,
                '_token': csrf_token
            }, timeout=30)
            
            if response.status_code == 200:
                self.logged_in = True
                print("✅ Panel login successful!")
                return True
            return False
        except Exception as e:
            print(f"❌ Panel login error: {e}")
            return False
    
    def generate_key(self, duration):
        try:
            if not self.logged_in:
                if not self.login():
                    return None
            
            print(f"🔄 Generating {duration} key...")
            
            duration_map = {'5h':'5_hours','3d':'3_days','7d':'7_days','14d':'14_days','30d':'30_days','60d':'60_days'}
            duration_value = duration_map.get(duration, duration)
            
            response = self.scraper.post(f'{PANEL_URL}/generate', data={
                'duration': duration_value,
                'max_devices': '1'
            }, timeout=30)
            
            patterns = [
                r'[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}',
                r'[A-Z0-9]{16,32}',
                r'"key":"([^"]+)"',
                r'"license":"([^"]+)"',
                r'<code>([^<]+)</code>',
                r'Key:\s*([A-Z0-9\-]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, response.text, re.IGNORECASE)
                if match:
                    key = match.group(1) if match.groups() else match.group(0)
                    print(f"✅ Key generated: {key}")
                    return key
            
            print("❌ No key found in response")
            return None
        except Exception as e:
            print(f"❌ Generation error: {e}")
            return None

# ============= INITIALIZE =============
print("=" * 50)
print("🤖 STARTING MONSTER BOT...")
print("=" * 50)

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
    await query.answer()
    user_id = query.from_user.id
    
    if not db.is_approved(user_id) and not db.is_admin(user_id):
        await query.message.edit_text("❌ Not approved! Use /request")
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
    
    names = {'5h':'5 Hours', '3d':'3 Days', '7d':'7 Days', '14d':'14 Days', '30d':'30 Days', '60d':'60 Days'}
    
    await query.message.edit_text(f"🔄 Generating {names[duration]} key...\n⏳ Please wait 10-15 seconds...")
    
    key = panel.generate_key(duration)
    
    if key:
        db.save_key(key, names[duration], user_id, user_id)
        await query.message.edit_text(
            f"✅ *KEY GENERATED!*\n\n"
            f"🎫 *Duration:* {names[duration]}\n"
            f"🔑 `{key}`\n\n"
            f"⚠️ Valid for {names[duration]} only!",
            parse_mode='Markdown'
        )
    else:
        await query.message.edit_text(
            f"❌ *Generation Failed!*\n\n"
            f"Could not generate {names[duration]} key.\n"
            f"Please try again later.",
            parse_mode='Markdown'
        )

async def my_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keys = db.get_user_keys(query.from_user.id)
    
    if not keys:
        await query.message.edit_text("📭 No keys found. Generate one first!")
        return
    
    msg = "🔑 *Your Keys:*\n\n"
    for k in keys:
        msg += f"✅ `{k['key_code']}` - {k['duration']}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
    await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def referral_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    bot = await context.bot.get_me()
    link = f"https://t.me/{bot.username}?start={user_id}"
    count = db.get_referral_count(user_id)
    
    await query.message.edit_text(
        f"👥 *Referral Program*\n\n"
        f"🔗 `{link}`\n"
        f"📊 Referrals: {count}\n\n"
        f"Share this link with friends!",
        parse_mode='Markdown'
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not db.is_admin(query.from_user.id):
        await query.message.edit_text("❌ Access Denied!")
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
    await query.answer()
    users = db.get_all_users()
    
    msg = "👥 *Users:*\n\n"
    for u in users[:20]:
        status = "✅" if u['is_approved'] else "⏳"
        msg += f"{status} `{u['user_id']}` - {u.get('first_name', '?')}\n"
    
    await query.message.edit_text(msg, parse_mode='Markdown')

async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
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
    await query.answer()
    await query.message.edit_text("📢 Send your broadcast message:")
    context.user_data['broadcast_mode'] = True

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    stats = db.get_stats()
    
    msg = f"📊 *Statistics:*\n\n"
    msg += f"👥 Total Users: {stats['total_users']}\n"
    msg += f"✅ Approved: {stats['approved_users']}\n"
    msg += f"🔑 Total Keys: {stats['total_keys']}\n"
    msg += f"📋 Pending: {stats['pending_requests']}"
    
    await query.message.edit_text(msg, parse_mode='Markdown')

async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
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
    text = "📚 *Commands:*\n/start - Main menu\n/request - Get access\n/help - This help"
    
    if update.callback_query:
        await update.callback_query.message.edit_text(text, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, parse_mode='Markdown')

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(query, context)

# ============= MAIN =============
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("request", request_access))
    app.add_handler(CommandHandler("help", help_command))
    
    # Callbacks
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
    
    # Broadcast handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast))
    
    print("=" * 50)
    print("🤖 MONSTER BOT IS RUNNING!")
    print(f"✅ Bot Token: {BOT_TOKEN[:10]}...")
    print(f"✅ Owner ID: {OWNER_ID}")
    print("=" * 50)
    print("👉 Bot: https://t.me/{(app.bot.get_me())}")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
