# File: bot.py - UPDATED VERSION

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

class PanelAPI:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows'})
        self.cookies = None
    
    def generate_key(self, duration):
        try:
            # First get login page
            login_page = self.scraper.get('https://xsilent.shop/vip/login')
            
            # Extract CSRF token
            csrf_match = re.search(r'name="_token"\s+value="([^"]+)"', login_page.text)
            csrf_token = csrf_match.group(1) if csrf_match else ''
            
            # Login
            login_data = {
                'username': 'VIPKEY',
                'password': 'roxym830',
                '_token': csrf_token
            }
            login_res = self.scraper.post('https://xsilent.shop/vip/login', data=login_data)
            self.cookies = self.scraper.cookies
            
            # Try different generate endpoints
            endpoints = [
                'https://xsilent.shop/vip/generate',
                'https://xsilent.shop/vip/user/generate', 
                'https://xsilent.shop/vip/api/generate',
                'https://xsilent.shop/vip/key/generate'
            ]
            
            durations = {
                '5h': '5_hours', '3d': '3_days', '7d': '7_days',
                '14d': '14_days', '30d': '30_days', '60d': '60_days'
            }
            
            for endpoint in endpoints:
                try:
                    resp = self.scraper.post(endpoint, data={
                        'duration': durations.get(duration, duration),
                        'max_devices': '1'
                    })
                    
                    # Look for key in response
                    key = self.extract_key(resp.text)
                    if key:
                        return key
                except:
                    continue
            
            # Try GET request
            resp = self.scraper.get(f'https://xsilent.shop/vip/generate?duration={duration}&max_devices=1')
            key = self.extract_key(resp.text)
            if key:
                return key
            
            return None
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def extract_key(self, text):
        patterns = [
            r'[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}',
            r'[A-Z0-9]{16,32}',
            r'"key":"([^"]+)"',
            r'"license":"([^"]+)"',
            r'<code>([^<]+)</code>',
            r'<span[^>]*>([A-Z0-9\-]{16,})</span>',
            r'value="([A-Z0-9\-]{16,})"'
        ]
        for p in patterns:
            m = re.search(p, text, re.I)
            if m:
                return m.group(1) if m.groups() else m.group(0)
        return None

# Quick database
class DB:
    def __init__(self):
        self.client = MongoClient(MONGODB_URI)
        self.db = self.client["monster_bot"]
        self.users = self.db.users
    
    def add_user(self, user_id, name):
        if not self.users.find_one({"user_id": user_id}):
            self.users.insert_one({"user_id": user_id, "name": name, "approved": user_id == OWNER_ID})
    
    def is_approved(self, user_id):
        u = self.users.find_one({"user_id": user_id})
        return u["approved"] if u else False

db = DB()
panel = PanelAPI()

# Bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.first_name)
    
    keyboard = [
        [InlineKeyboardButton("⏰ 5H", callback_data="5h"), InlineKeyboardButton("📅 3D", callback_data="3d")],
        [InlineKeyboardButton("📆 7D", callback_data="7d"), InlineKeyboardButton("📊 14D", callback_data="14d")],
        [InlineKeyboardButton("🌟 30D", callback_data="30d"), InlineKeyboardButton("💎 60D", callback_data="60d")]
    ]
    
    status = "✅ Approved" if db.is_approved(user.id) else "⏳ Pending"
    await update.message.reply_text(
        f"🔥 XSILENT KEY GEN\n👋 {user.first_name}\n📌 {status}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    duration = query.data
    uid = query.from_user.id
    
    if not db.is_approved(uid) and uid != OWNER_ID:
        await query.message.edit_text("❌ Not approved! Contact admin.")
        return
    
    names = {'5h':'5H','3d':'3D','7d':'7D','14d':'14D','30d':'30D','60d':'60D'}
    
    await query.message.edit_text(f"🔄 Generating {names[duration]} key...")
    
    key = panel.generate_key(duration)
    
    if key:
        await query.message.edit_text(f"✅ KEY GENERATED!\n\n🔑 `{key}`\n\nValid: {names[duration]}", parse_mode='Markdown')
    else:
        await query.message.edit_text(f"❌ Failed!\n\nPanel might be down or changed.\nContact admin.")

async def request_acc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text("✅ Request sent to admin!")
    await context.bot.send_message(OWNER_ID, f"🆕 Request from @{user.username or user.first_name}\nID: {user.id}\n/approve {user.id}")

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("Only owner can approve!")
        return
    try:
        uid = int(context.args[0])
        db.users.update_one({"user_id": uid}, {"$set": {"approved": True}})
        await update.message.reply_text(f"✅ User {uid} approved!")
        await context.bot.send_message(uid, "✅ You are approved! Use /start")
    except:
        await update.message.reply_text("Usage: /approve user_id")

# Main
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("request", request_acc))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CallbackQueryHandler(gen, pattern="^(5h|3d|7d|14d|30d|60d)$"))
    
    print("🤖 Bot Started!")
    app.run_polling()

if __name__ == "__main__":
    main()
