
import asyncio
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import cloudscraper
from bs4 import BeautifulSoup
import re

# ============= CONFIGURATION =============
BOT_TOKEN = "8466296023:AAHHz4iBpDWwZJgZABOapwlFRHn8f51uC6w"  # @BotFather se lo
ADMIN_ID = "7192516189"    # @userinfobot se lo

# XSilent Credentials
USERNAME = "VIPKEY"
PASSWORD = "roxym830"
BASE_URL = "https://xsilent.shop/vip"

# ============= KEY GENERATION CLASS =============
class XSilentKeyGen:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            },
            delay=15
        )
        self.logged_in = False
        
    def login(self):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': BASE_URL,
                'Referer': f'{BASE_URL}/login'
            }
            
            login_page = self.scraper.get(f'{BASE_URL}/login', headers=headers)
            soup = BeautifulSoup(login_page.text, 'html.parser')
            csrf_token = None
            
            meta_token = soup.find('meta', {'name': 'csrf-token'})
            if meta_token:
                csrf_token = meta_token.get('content')
            
            if not csrf_token:
                token_input = soup.find('input', {'name': '_token'})
                if token_input:
                    csrf_token = token_input.get('value')
            
            login_data = {
                'username': USERNAME,
                'password': PASSWORD,
                '_token': csrf_token if csrf_token else ''
            }
            
            login_response = self.scraper.post(f'{BASE_URL}/login', data=login_data, headers=headers)
            
            if 'dashboard' in login_response.text.lower() or 'redirect' in login_response.text.lower():
                self.logged_in = True
                return True
                
            if login_response.status_code == 200 and 'logout' in login_response.text.lower():
                self.logged_in = True
                return True
                
            return False
            
        except Exception as e:
            print(f"Login error: {e}")
            return False
    
    def generate_key(self, duration):
        if not self.logged_in:
            if not self.login():
                return "❌ Login failed! Panel might be down."
        
        try:
            duration_map = {
                '5h': '5_hours',
                '3d': '3_days', 
                '7d': '7_days',
                '14d': '14_days',
                '30d': '30_days',
                '60d': '60_days'
            }
            
            panel_duration = duration_map.get(duration, duration)
            generate_url = f'{BASE_URL}/generate'
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': generate_url
            }
            
            gen_data = {
                'duration': panel_duration,
                'max_devices': '1',
                'action': 'generate_key'
            }
            
            response = self.scraper.post(generate_url, data=gen_data, headers=headers)
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    if 'key' in result:
                        return result['key']
                    if 'license' in result:
                        return result['license']
                    if 'code' in result:
                        return result['code']
                except:
                    pass
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                patterns = [
                    r'<div[^>]*key[^>]*>([A-Z0-9\-]{16,})</div>',
                    r'<code>([A-Z0-9\-]{16,})</code>',
                    r'value="([A-Z0-9\-]{16,})"',
                    r'Your key:?\s*([A-Z0-9\-]{16,})',
                    r'License key:?\s*([A-Z0-9\-]{16,})',
                    r'([A-Z0-9]{8}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{12})',
                    r'([A-Z0-9]{16,32})'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, response.text, re.IGNORECASE)
                    if match:
                        return match.group(1)
                
                if 'success' in response.text.lower():
                    return "✅ Key generated but extraction failed. Check panel manually."
                else:
                    return f"⚠️ Generation response: {response.text[:200]}"
            else:
                return f"❌ HTTP {response.status_code}: Generation failed"
                
        except Exception as e:
            return f"❌ Error: {str(e)}"

key_gen = XSilentKeyGen()

# ============= TELEGRAM BOT HANDLERS =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⏰ 5 Hours", callback_data="gen_5h")],
        [InlineKeyboardButton("📅 3 Days", callback_data="gen_3d")],
        [InlineKeyboardButton("📆 7 Days", callback_data="gen_7d")],
        [InlineKeyboardButton("📊 14 Days", callback_data="gen_14d")],
        [InlineKeyboardButton("🌟 30 Days", callback_data="gen_30d")],
        [InlineKeyboardButton("💎 60 Days", callback_data="gen_60d")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔥 *XSILENT VIP KEY GENERATOR* 🔥\n\n"
        "Select key duration to generate:\n"
        "👇👇👇",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def generate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    duration = query.data.replace("gen_", "")
    duration_names = {
        '5h': '5 Hours', '3d': '3 Days', '7d': '7 Days',
        '14d': '14 Days', '30d': '30 Days', '60d': '60 Days'
    }
    
    msg = await query.edit_message_text(
        f"🔄 Generating {duration_names[duration]} key...\n"
        f"⏳ Please wait 10-15 seconds\n\n"
        f"🔐 Logging into panel...",
        parse_mode='Markdown'
    )
    
    key = key_gen.generate_key(duration)
    
    if key.startswith("✅") or "key" in key.lower() or len(key) > 10:
        response = (
            f"✅ *KEY GENERATED SUCCESSFULLY!*\n\n"
            f"🎫 *Duration:* {duration_names[duration]}\n"
            f"🔑 *Your Key:*\n"
            f"`{key}`\n\n"
            f"📋 Copy this key and use in XSilent app.\n"
            f"⚠️ Valid for {duration_names[duration]} only!"
        )
        await msg.edit_text(response, parse_mode='Markdown')
        
        await query.message.reply_text(
            f"🔐 `{key}`",
            parse_mode='Markdown'
        )
    else:
        await msg.edit_text(
            f"❌ *Generation Failed*\n\n"
            f"Duration: {duration_names[duration]}\n"
            f"Error: {key}\n\n"
            f"Possible issues:\n"
            f"• Panel Cloudflare blocking\n"
            f"• Session expired\n"
            f"• Key limit reached\n\n"
            f"Try /start again or contact admin",
            parse_mode='Markdown'
        )

async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    help_text = (
        "📚 *How to use:*\n\n"
        "1️⃣ Click on any duration button\n"
        "2️⃣ Wait 10-15 seconds\n"
        "3️⃣ Your key will appear\n"
        "4️⃣ Copy and use in XSilent\n\n"
        "*Available durations:*\n"
        "⏰ 5 Hours - Quick trial\n"
        "📅 3 Days - Weekend\n"
        "📆 7 Days - Weekly\n"
        "📊 14 Days - 2 weeks\n"
        "🌟 30 Days - Monthly\n"
        "💎 60 Days - Best value\n\n"
        "⚠️ One key per request\n"
        "⚠️ Keys are unique and non-transferable"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(help_text, parse_mode='Markdown', reply_markup=reply_markup)

async def back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("⏰ 5 Hours", callback_data="gen_5h")],
        [InlineKeyboardButton("📅 3 Days", callback_data="gen_3d")],
        [InlineKeyboardButton("📆 7 Days", callback_data="gen_7d")],
        [InlineKeyboardButton("📊 14 Days", callback_data="gen_14d")],
        [InlineKeyboardButton("🌟 30 Days", callback_data="gen_30d")],
        [InlineKeyboardButton("💎 60 Days", callback_data="gen_60d")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🔥 *XSILENT VIP KEY GENERATOR* 🔥\n\nSelect duration:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔄 Checking panel status...")
    
    if key_gen.login():
        await msg.edit_text(
            "✅ *Bot Status:* Online\n"
            "✅ *Panel Status:* Connected\n"
            "✅ *Ready to generate keys*\n\n"
            "Use /start to begin",
            parse_mode='Markdown'
        )
    else:
        await msg.edit_text(
            "⚠️ *Bot Status:* Online\n"
            "❌ *Panel Status:* Connection failed\n\n"
            "Panel might be down or Cloudflare blocking.\n"
            "Try again in few minutes.",
            parse_mode='Markdown'
        )

# ============= MAIN =============
def main():
    """Start the bot"""
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CallbackQueryHandler(generate_callback, pattern="^gen_"))
    app.add_handler(CallbackQueryHandler(help_callback, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(back_callback, pattern="^back$"))
    
    # Get bot info
    bot_info = app.bot.get_me()
    print("🤖 Bot Started! 100% Working Mode")
    print(f"👉 Bot: https://t.me/{bot_info.username}")
    print("Press Ctrl+C to stop")
    
    # Start polling (this will block)
    app.run_polling()

if __name__ == "__main__":
    main()
