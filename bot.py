from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import cloudscraper
from bs4 import BeautifulSoup
import re
import asyncio

# ============= CONFIGURATION =============
BOT_TOKEN = "8466296023:AAHHz4iBpDWwZJgZABOapwlFRHn8f51uC6w"  # @BotFather se lo
USERNAME = "VIPKEY"
PASSWORD = "roxym830"
BASE_URL = "https://xsilent.shop/vip"

# ============= KEY GENERATION =============
class KeyGenerator:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        self.logged_in = False
    
    def login(self):
        try:
            # Login to panel
            login_data = {
                'username': USERNAME,
                'password': PASSWORD
            }
            response = self.scraper.post(f'{BASE_URL}/login', data=login_data)
            
            if response.status_code == 200:
                self.logged_in = True
                return True
            return False
        except Exception as e:
            print(f"Login error: {e}")
            return False
    
    def generate_key(self, duration):
        try:
            if not self.logged_in:
                if not self.login():
                    return "Login failed"
            
            # Generate key
            gen_data = {
                'duration': duration,
                'max_devices': '1'
            }
            response = self.scraper.post(f'{BASE_URL}/generate', data=gen_data)
            
            # Extract key from response
            # Pattern for license key
            patterns = [
                r'[A-Z0-9]{8}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{12}',
                r'[A-Z0-9]{16,32}',
                r'key["\']?\s*[:=]\s*["\']([A-Z0-9\-]+)',
                r'license["\']?\s*[:=]\s*["\']([A-Z0-9\-]+)',
                r'<code>([^<]+)</code>'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, response.text, re.IGNORECASE)
                if match:
                    return match.group(1) if match.groups() else match.group(0)
            
            return "Key extracted but not found in expected format"
            
        except Exception as e:
            return f"Error: {str(e)}"

# Initialize generator
key_gen = KeyGenerator()

# ============= BOT HANDLERS =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⏰ 5 Hours", callback_data="5h")],
        [InlineKeyboardButton("📅 3 Days", callback_data="3d")],
        [InlineKeyboardButton("📆 7 Days", callback_data="7d")],
        [InlineKeyboardButton("📊 14 Days", callback_data="14d")],
        [InlineKeyboardButton("🌟 30 Days", callback_data="30d")],
        [InlineKeyboardButton("💎 60 Days", callback_data="60d")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔥 *XSILENT VIP KEY GENERATOR* 🔥\n\n"
        "Select key duration:\n"
        "👇👇👇",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def generate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    duration = query.data
    duration_names = {
        '5h': '5 Hours', '3d': '3 Days', '7d': '7 Days',
        '14d': '14 Days', '30d': '30 Days', '60d': '60 Days'
    }
    
    # Send processing message
    await query.edit_message_text(
        f"🔄 Generating {duration_names[duration]} key...\n"
        f"⏳ Please wait...",
        parse_mode='Markdown'
    )
    
    # Generate the key
    key = key_gen.generate_key(duration)
    
    # Send result
    if "Error" in key or "failed" in key.lower():
        await query.message.reply_text(
            f"❌ *Generation Failed*\n\n"
            f"Duration: {duration_names[duration]}\n"
            f"Error: {key}\n\n"
            f"Try again later.",
            parse_mode='Markdown'
        )
    else:
        await query.message.reply_text(
            f"✅ *KEY GENERATED!*\n\n"
            f"🎫 *Duration:* {duration_names[duration]}\n"
            f"🔑 *Your Key:*\n"
            f"`{key}`\n\n"
            f"⚠️ Valid for {duration_names[duration]} only!",
            parse_mode='Markdown'
        )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔄 Checking...")
    
    if key_gen.login():
        await msg.edit_text(
            "✅ *Bot Status:* Online\n"
            "✅ *Panel:* Connected\n"
            "✅ Ready to generate keys!",
            parse_mode='Markdown'
        )
    else:
        await msg.edit_text(
            "⚠️ *Bot:* Online\n"
            "❌ *Panel:* Offline\n"
            "Try again later.",
            parse_mode='Markdown'
        )

# ============= MAIN - SIMPLE AND WORKING =============
def main():
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CallbackQueryHandler(generate_callback))
    
    # Print bot info (without await)
    print("=" * 40)
    print("🤖 XSILENT KEY GENERATOR BOT")
    print("=" * 40)
    print(f"✅ Bot Token: {BOT_TOKEN[:10]}...")
    print("✅ Bot is starting...")
    print("✅ Press Ctrl+C to stop")
    print("=" * 40)
    
    # Start polling
    app.run_polling()

if __name__ == "__main__":
    main()
