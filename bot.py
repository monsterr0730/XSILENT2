import asyncio
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
import time
import threading

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

# ============= SELENIUM PANEL (BYPASS CLOUDFLARE) =============
class PanelBot:
    def __init__(self):
        self.driver = None
        self.lock = threading.Lock()
        
    def get_driver(self):
        """Get or create driver instance"""
        if self.driver is None:
            options = uc.ChromeOptions()
            options.add_argument('--headless=new')  # Background mein chale ga
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0')
            
            self.driver = uc.Chrome(options=options)
            self.driver.implicitly_wait(10)
        return self.driver
    
    def generate_key(self, duration):
        """Generate key using real browser"""
        with self.lock:
            try:
                driver = self.get_driver()
                
                # Duration mapping
                duration_map = {
                    '5h': '5 Hours',
                    '3d': '3 Days',
                    '7d': '7 Days',
                    '14d': '14 Days',
                    '30d': '30 Days',
                    '60d': '60 Days'
                }
                duration_text = duration_map.get(duration, duration)
                
                print(f"🔄 Opening panel...")
                driver.get('https://xsilent.shop/vip/login')
                time.sleep(5)  # Wait for Cloudflare
                
                # Login
                print("🔐 Logging in...")
                wait = WebDriverWait(driver, 20)
                
                # Find username field
                username_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='username'], input[type='text']")))
                username_input.clear()
                username_input.send_keys('VIPKEY')
                
                # Find password field
                password_input = driver.find_element(By.CSS_SELECTOR, "input[name='password'], input[type='password']")
                password_input.clear()
                password_input.send_keys('roxym830')
                
                # Find and click login button
                login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
                login_btn.click()
                
                time.sleep(5)
                
                # Click menu (three lines)
                print("📁 Opening menu...")
                menu_selectors = [
                    "button.navbar-toggler",
                    ".menu-toggle",
                    "i.fa-bars",
                    "svg[class*='menu']",
                    "button[class*='menu']"
                ]
                
                for selector in menu_selectors:
                    try:
                        menu = driver.find_element(By.CSS_SELECTOR, selector)
                        menu.click()
                        time.sleep(1)
                        break
                    except:
                        continue
                
                # Click Generate option
                print("⚙️ Going to generate...")
                gen_selectors = [
                    "a[href*='generate']",
                    "button:contains('Generate')",
                    "span:contains('Generate')",
                    "div:contains('Generate')"
                ]
                
                for selector in gen_selectors:
                    try:
                        if 'contains' in selector:
                            elem = driver.find_element(By.XPATH, f"//*[contains(text(), 'Generate')]")
                        else:
                            elem = driver.find_element(By.CSS_SELECTOR, selector)
                        elem.click()
                        time.sleep(2)
                        break
                    except:
                        continue
                
                # Select duration
                print(f"⏰ Selecting {duration_text}...")
                duration_selectors = [
                    f"button:contains('{duration_text}')",
                    f"span:contains('{duration_text}')",
                    f"option[value='{duration}']",
                    f"input[value='{duration}']"
                ]
                
                for selector in duration_selectors:
                    try:
                        if 'contains' in selector:
                            elem = driver.find_element(By.XPATH, f"//*[contains(text(), '{duration_text}')]")
                        else:
                            elem = driver.find_element(By.CSS_SELECTOR, selector)
                        elem.click()
                        time.sleep(1)
                        break
                    except:
                        continue
                
                # Set max devices (default 1)
                try:
                    device_input = driver.find_element(By.CSS_SELECTOR, "input[name='max_devices'], input[type='number']")
                    device_input.clear()
                    device_input.send_keys('1')
                except:
                    pass
                
                # Click generate button
                print("🔑 Generating key...")
                gen_btn_selectors = [
                    "button:contains('Generate')",
                    "button:contains('Create')",
                    "button[type='submit']",
                    "input[value='Generate']"
                ]
                
                for selector in gen_btn_selectors:
                    try:
                        if 'contains' in selector:
                            btn = driver.find_element(By.XPATH, f"//*[contains(text(), 'Generate') or contains(text(), 'Create')]")
                        else:
                            btn = driver.find_element(By.CSS_SELECTOR, selector)
                        btn.click()
                        time.sleep(3)
                        break
                    except:
                        continue
                
                # Extract key from page
                page_source = driver.page_source
                
                # Key patterns
                patterns = [
                    r'[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}',
                    r'[A-Z0-9]{16,32}',
                    r'<code>([^<]+)</code>',
                    r'class="key"[^>]*>([^<]+)<',
                    r'value="([A-Z0-9\-]{16,})"'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, page_source, re.IGNORECASE)
                    if match:
                        key = match.group(1) if match.groups() else match.group(0)
                        if len(key) >= 8:
                            print(f"✅ Key found: {key}")
                            return key
                
                print("❌ No key found in page")
                return None
                
            except Exception as e:
                print(f"❌ Error: {e}")
                return None
    
    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

panel = PanelBot()

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
        keyboard.append([InlineKeyboardButton("🔧 Status", callback_data="status")])
    
    status = "✅" if db.is_approved(user.id) else "⏳ Pending"
    
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
        await query.message.edit_text("❌ Not approved! Send /request")
        return
    
    duration_names = {
        '5h': '5 Hours', '3d': '3 Days', '7d': '7 Days',
        '14d': '14 Days', '30d': '30 Days', '60d': '60 Days'
    }
    
    msg = await query.message.edit_text(
        f"🔄 *Generating {duration_names[duration]} Key...*\n\n"
        f"⏳ Opening browser...\n"
        f"🔐 Bypassing Cloudflare...\n"
        f"🔑 Generating license...\n\n"
        f"*Please wait 30-40 seconds*",
        parse_mode='Markdown'
    )
    
    # Run in thread to avoid blocking
    key = await asyncio.to_thread(panel.generate_key, duration)
    
    if key:
        await msg.edit_text(
            f"✅ *KEY GENERATED SUCCESSFULLY!*\n\n"
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
            f"Reasons:\n"
            f"• Cloudflare blocking\n"
            f"• Panel structure changed\n"
            f"• Try again in 2 minutes\n\n"
            f"Contact @admin for help.",
            parse_mode='Markdown'
        )

async def panel_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        f"🔧 *Panel Status*\n\n"
        f"🤖 Browser: Ready\n"
        f"☁️ Cloudflare: Bypass Active\n"
        f"🔑 Key Gen: Working\n\n"
        f"✅ Bot is using real browser\n"
        f"✅ Can bypass any protection\n\n"
        f"*Note:* Takes 30-40 seconds per key",
        parse_mode='Markdown'
    )

async def request_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if db.is_approved(user.id):
        await update.message.reply_text("✅ You are already approved!")
        return
    
    await update.message.reply_text("✅ Request sent to admin!")
    await context.bot.send_message(OWNER_ID, f"🆕 Request from {user.first_name}\nID: {user.id}\n/approve {user.id}")

async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Owner only!")
        return
    
    try:
        uid = int(context.args[0])
        db.approve_user(uid)
        await update.message.reply_text(f"✅ User {uid} approved!")
        await context.bot.send_message(uid, "✅ Approved! Use /start")
    except:
        await update.message.reply_text("Usage: /approve user_id")

# ============= MAIN =============
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("request", request_access))
    app.add_handler(CommandHandler("approve", approve_user))
    
    app.add_handler(CallbackQueryHandler(generate_key, pattern="^gen_"))
    app.add_handler(CallbackQueryHandler(panel_status, pattern="^status$"))
    
    print("=" * 50)
    print("🤖 XSILENT KEY GENERATOR (SELENIUM MODE)")
    print("=" * 50)
    print("✅ Bot Running")
    print("✅ Using Real Browser to Bypass Cloudflare")
    print("⏳ Key generation takes 30-40 seconds")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
