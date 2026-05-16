import asyncio
import cloudscraper
import re
import json
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
        if not self.users.find_one({"user_id": user_id}):
            self.users.insert_one({
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "approved": user_id == OWNER_ID,
                "join_date": datetime.now().isoformat()
            })
    
    def is_approved(self, user_id):
        user = self.users.find_one({"user_id": user_id})
        return user.get("approved", False) if user else False
    
    def approve_user(self, user_id):
        self.users.update_one({"user_id": user_id}, {"$set": {"approved": True}})

db = Database()

# ============= REAL PANEL GENERATION =============
class RealPanel:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True},
            delay=5
        )
        self.session = None
        self.logged_in = False
    
    def login(self):
        try:
            # Get login page with CSRF
            resp = self.scraper.get('https://xsilent.shop/vip/login')
            
            # Extract CSRF token
            csrf = re.search(r'name="_token"\s+value="([^"]+)"', resp.text)
            csrf_token = csrf.group(1) if csrf else ''
            
            # Also check for other token formats
            if not csrf_token:
                csrf = re.search(r'csrf-token" content="([^"]+)"', resp.text)
                csrf_token = csrf.group(1) if csrf else ''
            
            # Login post
            login_data = {
                'username': 'VIPKEY',
                'password': 'roxym830',
                '_token': csrf_token
            }
            
            login_res = self.scraper.post('https://xsilent.shop/vip/login', data=login_data)
            
            # Check if logged in
            if login_res.status_code == 200:
                self.logged_in = True
                print("✅ Panel login successful")
                return True
            return False
            
        except Exception as e:
            print(f"Login error: {e}")
            return False
    
    def generate_key(self, duration):
        try:
            if not self.logged_in:
                if not self.login():
                    return None
            
            duration_map = {
                '5h': '5_hours', '3d': '3_days', '7d': '7_days',
                '14d': '14_days', '30d': '30_days', '60d': '60_days'
            }
            
            dur_value = duration_map.get(duration, duration)
            
            # Try multiple methods
            
            # Method 1: AJAX POST
            try:
                headers = {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
                resp = self.scraper.post(
                    'https://xsilent.shop/vip/generate',
                    json={'duration': dur_value, 'max_devices': 1},
                    headers=headers
                )
                if resp.status_code == 200:
                    data = resp.json() if resp.text else {}
                    key = data.get('key') or data.get('license') or data.get('code')
                    if key:
                        return key
            except:
                pass
            
            # Method 2: Form POST
            try:
                resp = self.scraper.post(
                    'https://xsilent.shop/vip/generate',
                    data={'duration': dur_value, 'max_devices': 1}
                )
                key = self.extract_key(resp.text)
                if key:
                    return key
            except:
                pass
            
            # Method 3: GET request
            try:
                resp = self.scraper.get(f'https://xsilent.shop/vip/generate?duration={dur_value}&max_devices=1')
                key = self.extract_key(resp.text)
                if key:
                    return key
            except:
                pass
            
            # Method 4: Check dashboard for existing keys
            try:
                dashboard = self.scraper.get('https://xsilent.shop/vip/dashboard')
                keys = re.findall(r'[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}', dashboard.text)
                if keys:
                    return keys[0]
            except:
                pass
            
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
            r'<code>([^<]+)</code>'
        ]
        for p in patterns:
            m = re.search(p, text, re.I)
            if m:
                return m.group(1) if m.groups() else m.group(0)
        return None

panel = RealPanel()

# ============= DEMO KEYS (Temporary until panel works) =============
# Ye tab tak use hoga jab tak panel fix nahi hota
DEMO_KEYS = {
    '5h': 'XSLT-5H-' + ''.join([str(i) for i in range(6)]),
    '3d': 'XSLT-3D-' + ''.join([str(i) for i in range(6)]),
    '7d': 'XSLT-7D-' + ''.join([str(i) for i in range(6)]),
    '14d': 'XSLT-14D-' + ''.join([str(i) for i in range(6)]),
    '30d': 'XSLT-30D-' + ''.join([str(i) for i in range(6)]),
    '60d': 'XSLT-60D-' + ''.join([str(i) for i in range(6)])
}

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
        keyboard.append([InlineKeyboardButton("🔧 Panel Status", callback_data="status")])
    
    status = "✅" if db.is_approved(user.id) else "⏳"
    
    await update.message.reply_text(
        f"🔥 *XSILENT VIP KEY GENERATOR* 🔥\n\n"
        f"👋 Hello {user.first_name}!\n"
        f"📌 Status: {status}\n\n"
        f"👇 Select duration:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def generate_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    duration = query.data.replace("gen_", "")
    user_id = query.from_user.id
    
    if not db.is_approved(user_id) and user_id != OWNER_ID:
        await query.message.edit_text("❌ Not approved! Contact admin.")
        return
    
    duration_names = {
        '5h': '5 Hours', '3d': '3 Days', '7d': '7 Days',
        '14d': '14 Days', '30d': '30 Days', '60d': '60 Days'
    }
    
    msg = await query.message.edit_text(
        f"🔄 Generating {duration_names[duration]} key...\n"
        f"⏳ Connecting to panel...\n\n"
        f"🔐 Bypassing Cloudflare protection...",
        parse_mode='Markdown'
    )
    
    # Try real panel first
    real_key = panel.generate_key(duration)
    
    if real_key:
        await msg.edit_text(
            f"✅ *KEY GENERATED!*\n\n"
            f"🎫 *Duration:* {duration_names[duration]}\n"
            f"🔑 `{real_key}`\n\n"
            f"⚠️ Valid for {duration_names[duration]} only!",
            parse_mode='Markdown'
        )
    else:
        # Show demo key as fallback
        await msg.edit_text(
            f"⚠️ *Panel Connection Failed*\n\n"
            f"🎫 *Duration:* {duration_names[duration]}\n"
            f"🔑 `{DEMO_KEYS[duration]}`\n\n"
            f"❌ *Note:* Panel is currently unreachable.\n"
            f"This is a demo key. Contact admin for real keys.\n\n"
            f"🔧 Panel Status: Cloudflare Blocking",
            parse_mode='Markdown'
        )

async def panel_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Test panel
    try:
        test = panel.login()
        if test:
            status_text = "✅ CONNECTED"
        else:
            status_text = "❌ BLOCKED"
    except:
        status_text = "❌ OFFLINE"
    
    await query.message.edit_text(
        f"🔧 *Panel Status*\n\n"
        f"Status: {status_text}\n"
        f"URL: xsilent.shop/vip\n\n"
        f"*If blocked:*\n"
        f"• Cloudflare protection active\n"
        f"• Waiting for fix...",
        parse_mode='Markdown'
    )

async def request_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_approved(user.id):
        await update.message.reply_text("✅ You are already approved!")
        return
    
    await update.message.reply_text(
        "✅ *Request Sent!*\n\n"
        "Admin will approve you soon.",
        parse_mode='Markdown'
    )
    
    await context.bot.send_message(
        OWNER_ID,
        f"🆕 *New Request*\n👤 {user.first_name}\n🆔 `{user.id}`\n/approve {user.id}",
        parse_mode='Markdown'
    )

async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Owner only!")
        return
    
    try:
        uid = int(context.args[0])
        db.approve_user(uid)
        await update.message.reply_text(f"✅ User {uid} approved!")
        await context.bot.send_message(uid, "✅ You are approved! Use /start")
    except:
        await update.message.reply_text("Usage: /approve user_id")

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(query, context)

# ============= MAIN =============
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("request", request_access))
    app.add_handler(CommandHandler("approve", approve_user))
    
    app.add_handler(CallbackQueryHandler(generate_key, pattern="^gen_"))
    app.add_handler(CallbackQueryHandler(panel_status, pattern="^status$"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^back$"))
    
    print("=" * 50)
    print("🤖 XSILENT KEY GENERATOR")
    print("=" * 50)
    print("✅ Bot Running")
    print("⚠️ Panel Status: Testing...")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
