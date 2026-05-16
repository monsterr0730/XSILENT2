import asyncio
import cloudscraper
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from pymongo import MongoClient

# ============= CONFIG =============
BOT_TOKEN = "8466296023:AAGgTRre3Y_NL7kvNAvDsdomJo6-p_1Vu80"
OWNER_ID = 7192516189
MONGODB_URI = "mongodb+srv://mohitrao83076_db_user:LugF1xwlenkWRE1F@monster.ydmmckl.mongodb.net/?retryWrites=true&w=majority&appName=MONSTER"

# ============= DATABASE =============
class Database:
    def __init__(self):
        self.client = MongoClient(MONGODB_URI)
        self.db = self.client["monster_bot"]
        self.users = self.db.users
        
    def add_user(self, user_id, username, first_name):
        try:
            existing = self.users.find_one({"user_id": user_id})
            if not existing:
                self.users.insert_one({
                    "user_id": user_id,
                    "username": username,
                    "first_name": first_name,
                    "approved": True if user_id == OWNER_ID else False,
                    "join_date": datetime.now().isoformat(),
                    "keys": 0
                })
                return True
            return False
        except Exception as e:
            print(f"Add user error: {e}")
            return False
    
    def is_approved(self, user_id):
        try:
            user = self.users.find_one({"user_id": user_id})
            if user:
                return user.get("approved", False)
            return False
        except:
            return False
    
    def approve_user(self, user_id):
        try:
            self.users.update_one({"user_id": user_id}, {"$set": {"approved": True}})
            return True
        except:
            return False
    
    def get_all_users(self):
        try:
            return list(self.users.find({}, {"user_id": 1, "first_name": 1, "approved": 1}))
        except:
            return []

# ============= PANEL API =============
class PanelAPI:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True},
            delay=5
        )
        self.logged_in = False
    
    def generate_key(self, duration):
        try:
            # First get login page
            print("Getting login page...")
            login_page = self.scraper.get('https://xsilent.shop/vip/login')
            
            # Get CSRF token
            csrf_token = None
            csrf_match = re.search(r'name="_token"\s+value="([^"]+)"', login_page.text)
            if csrf_match:
                csrf_token = csrf_match.group(1)
            
            # Login
            print("Logging in...")
            login_data = {
                'username': 'VIPKEY',
                'password': 'roxym830',
                '_token': csrf_token if csrf_token else ''
            }
            login_res = self.scraper.post('https://xsilent.shop/vip/login', data=login_data)
            
            # Duration mapping
            duration_map = {
                '5h': '5_hours',
                '3d': '3_days', 
                '7d': '7_days',
                '14d': '14_days',
                '30d': '30_days',
                '60d': '60_days'
            }
            
            # Try to generate
            print(f"Generating {duration} key...")
            gen_data = {
                'duration': duration_map.get(duration, duration),
                'max_devices': '1'
            }
            
            # Try different endpoints
            endpoints = [
                'https://xsilent.shop/vip/generate',
                'https://xsilent.shop/vip/user/generate',
                'https://xsilent.shop/vip/api/generate'
            ]
            
            for endpoint in endpoints:
                try:
                    response = self.scraper.post(endpoint, data=gen_data)
                    
                    # Extract key
                    key = self.extract_key(response.text)
                    if key:
                        print(f"Key found: {key}")
                        return key
                except:
                    continue
            
            # If no key found, try to get from page source
            dashboard = self.scraper.get('https://xsilent.shop/vip/dashboard')
            key = self.extract_key(dashboard.text)
            if key:
                return key
            
            return None
            
        except Exception as e:
            print(f"Generate error: {e}")
            return None
    
    def extract_key(self, text):
        patterns = [
            r'[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}',
            r'[A-Z0-9]{16,32}',
            r'"key":"([^"]+)"',
            r'"license":"([^"]+)"',
            r'<code>([^<]+)</code>',
            r'<span[^>]*>([A-Z0-9\-]{16,})</span>',
            r'value="([A-Z0-9\-]{16,})"',
            r'Key:\s*([A-Z0-9\-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                result = match.group(1) if match.groups() else match.group(0)
                if len(result) >= 8:
                    return result.strip()
        return None

# ============= INIT =============
db = Database()
panel = PanelAPI()

# ============= BOT HANDLERS =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    
    keyboard = [
        [InlineKeyboardButton("⏰ 5 Hours", callback_data="gen_5h")],
        [InlineKeyboardButton("📅 3 Days", callback_data="gen_3d")],
        [InlineKeyboardButton("📆 7 Days", callback_data="gen_7d")],
        [InlineKeyboardButton("📊 14 Days", callback_data="gen_14d")],
        [InlineKeyboardButton("🌟 30 Days", callback_data="gen_30d")],
        [InlineKeyboardButton("💎 60 Days", callback_data="gen_60d")]
    ]
    
    if user.id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("👑 Admin", callback_data="admin")])
    
    status = "✅ Approved" if db.is_approved(user.id) else "⏳ Pending (Use /request)"
    
    await update.message.reply_text(
        f"🔥 *XSILENT KEY GENERATOR* 🔥\n\n"
        f"👋 Hello {user.first_name}!\n"
        f"📌 Status: {status}\n\n"
        f"👇 Select duration to generate key:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def generate_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    duration = query.data.replace("gen_", "")
    user_id = query.from_user.id
    
    if not db.is_approved(user_id) and user_id != OWNER_ID:
        await query.message.edit_text("❌ Not approved! Send /request to get access.")
        return
    
    duration_names = {
        '5h': '5 Hours', '3d': '3 Days', '7d': '7 Days',
        '14d': '14 Days', '30d': '30 Days', '60d': '60 Days'
    }
    
    msg = await query.message.edit_text(
        f"🔄 Generating {duration_names[duration]} key...\n"
        f"⏳ Please wait 10-20 seconds...\n\n"
        f"🔐 Bypassing Cloudflare...",
        parse_mode='Markdown'
    )
    
    key = panel.generate_key(duration)
    
    if key:
        await msg.edit_text(
            f"✅ *KEY GENERATED!*\n\n"
            f"🎫 *Duration:* {duration_names[duration]}\n"
            f"🔑 *Your Key:*\n"
            f"`{key}`\n\n"
            f"⚠️ Valid for {duration_names[duration]} only!\n"
            f"📋 Copy and use in XSilent app.",
            parse_mode='Markdown'
        )
    else:
        await msg.edit_text(
            f"❌ *Generation Failed!*\n\n"
            f"Duration: {duration_names[duration]}\n\n"
            f"Possible issues:\n"
            f"• Panel Cloudflare blocking\n"
            f"• Panel API changed\n"
            f"• Try again later\n\n"
            f"Contact admin if issue persists.",
            parse_mode='Markdown'
        )

async def request_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_approved(user.id):
        await update.message.reply_text("✅ You are already approved!")
        return
    
    # Add to pending (you can store in DB)
    await update.message.reply_text(
        "✅ *Request Sent!*\n\n"
        "Your request has been sent to admin.\n"
        "You will be notified once approved.\n\n"
        "Please wait...",
        parse_mode='Markdown'
    )
    
    # Notify owner
    await context.bot.send_message(
        OWNER_ID,
        f"🆕 *New Access Request!*\n\n"
        f"👤 User: {user.first_name}\n"
        f"🆔 ID: `{user.id}`\n"
        f"📛 Username: @{user.username or 'N/A'}\n\n"
        f"Send: `/approve {user.id}` to approve.",
        parse_mode='Markdown'
    )

async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Only owner can use this command!")
        return
    
    try:
        user_id = int(context.args[0])
        db.approve_user(user_id)
        await update.message.reply_text(f"✅ User `{user_id}` approved successfully!", parse_mode='Markdown')
        
        # Notify user
        try:
            await context.bot.send_message(
                user_id,
                "✅ *Congratulations!*\n\nYour access has been approved!\nUse /start to generate keys.",
                parse_mode='Markdown'
            )
        except:
            pass
    except:
        await update.message.reply_text("❌ Usage: `/approve user_id`", parse_mode='Markdown')

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != OWNER_ID:
        await query.message.edit_text("❌ Admin only!")
        return
    
    users = db.get_all_users()
    msg = "👥 *Users List:*\n\n"
    for u in users:
        status = "✅" if u.get("approved") else "⏳"
        msg += f"{status} `{u['user_id']}` - {u.get('first_name', '?')}\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
    await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(query, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 *Commands:*\n\n"
        "/start - Main menu\n"
        "/request - Request access\n"
        "/help - This help\n\n"
        "*How to get key:*\n"
        "1. Send /request\n"
        "2. Wait for admin approval\n"
        "3. Use /start and select duration\n"
        "4. Copy your key",
        parse_mode='Markdown'
    )

# ============= MAIN =============
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("request", request_access))
    app.add_handler(CommandHandler("approve", approve_user))
    app.add_handler(CommandHandler("help", help_command))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(generate_key, pattern="^gen_"))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin$"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back$"))
    
    print("=" * 50)
    print("🤖 XSILENT KEY GENERATOR BOT")
    print("=" * 50)
    print(f"✅ Bot Token: {BOT_TOKEN[:15]}...")
    print(f"✅ Owner ID: {OWNER_ID}")
    print(f"✅ MongoDB: Connected")
    print("=" * 50)
    print("Bot is running! Press Ctrl+C to stop")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
