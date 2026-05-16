import os
import re
import time
import cloudscraper
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ============= BAS YE EK LINE CHANGE KARO =============
BOT_TOKEN = "8466296023:AAHHz4iBpDWwZJgZABOapwlFRHn8f51uC6w"  # <-- YAHAN APNA TOKEN DALO
# ====================================================

USERNAME = "VIPKEY"
PASSWORD = "roxym830"
BASE_URL = "https://xsilent.shop/vip"

class XSilentBot:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True},
            delay=15
        )
        self.scraper.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        })
    
    def login(self):
        try:
            login_page = self.scraper.get(f'{BASE_URL}/login')
            csrf_match = re.search(r'name="_token"\s+value="([^"]+)"', login_page.text)
            csrf_token = csrf_match.group(1) if csrf_match else ''
            
            response = self.scraper.post(f'{BASE_URL}/login', data={
                'username': USERNAME,
                'password': PASSWORD,
                '_token': csrf_token
            })
            
            if response.status_code == 200:
                return True
            return False
        except:
            return False
    
    def generate_key(self, duration):
        try:
            if not self.login():
                return "Login failed"
            
            duration_map = {'5h':'5_hours','3d':'3_days','7d':'7_days','14d':'14_days','30d':'30_days','60d':'60_days'}
            response = self.scraper.post(f'{BASE_URL}/generate', data={
                'duration': duration_map.get(duration, duration),
                'max_devices': '1'
            })
            
            patterns = [
                r'[A-Z0-9]{8}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{12}',
                r'[A-Z0-9]{16,32}',
                r'"key":"([^"]+)"',
                r'<code>([^<]+)</code>'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, response.text, re.IGNORECASE)
                if match:
                    return match.group(1) if match.groups() else match.group(0)
            return "Key not found"
        except Exception as e:
            return f"Error: {str(e)}"

bot = XSilentBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⏰ 5 Hours", callback_data="5h")],
        [InlineKeyboardButton("📅 3 Days", callback_data="3d")],
        [InlineKeyboardButton("📆 7 Days", callback_data="7d")],
        [InlineKeyboardButton("📊 14 Days", callback_data="14d")],
        [InlineKeyboardButton("🌟 30 Days", callback_data="30d")],
        [InlineKeyboardButton("💎 60 Days", callback_data="60d")]
    ]
    await update.message.reply_text(
        "🔥 *XSILENT KEY GENERATOR* 🔥\n\nSelect Duration:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    duration = query.data
    names = {'5h':'5 Hours','3d':'3 Days','7d':'7 Days','14d':'14 Days','30d':'30 Days','60d':'60 Days'}
    
    msg = await query.edit_message_text(f"🔄 Generating {names[duration]} key...\n⏳ Please wait...")
    key = bot.generate_key(duration)
    
    if "Error" in key or "failed" in key.lower():
        await msg.edit_text(f"❌ Failed: {key}\n\nTry again")
    else:
        await msg.edit_text(f"✅ *Key Generated!*\n\n🔑 `{key}`\n\nValid for {names[duration]}", parse_mode='Markdown')

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(generate))
    print("🤖 Bot Started!")
    app.run_polling()

if __name__ == "__main__":
    main()
