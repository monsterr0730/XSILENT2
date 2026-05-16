from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import asyncio
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re

# ============= CONFIGURATION =============
BOT_TOKEN = "8466296023:AAHHz4iBpDWwZJgZABOapwlFRHn8f51uC6w"  # @BotFather se lo
USERNAME = "VIPKEY"
PASSWORD = "roxym830"
PANEL_URL = "https://xsilent.shop/vip"

# ============= SELENIUM KEY GENERATOR =============
class SeleniumKeyGen:
    def __init__(self):
        self.driver = None
        self.logged_in = False
    
    def setup_driver(self):
        """Setup undetected chrome driver"""
        options = uc.ChromeOptions()
        options.add_argument('--headless=new')  # Background mein chale ga
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        self.driver = uc.Chrome(options=options)
        return self.driver
    
    def login_and_generate(self, duration):
        """Login and generate key using real browser"""
        try:
            # Setup driver
            if not self.driver:
                self.setup_driver()
            
            # Open login page
            print("Opening login page...")
            self.driver.get(f"{PANEL_URL}/login")
            time.sleep(3)
            
            # Wait for Cloudflare to pass
            time.sleep(5)
            
            # Enter username
            username_input = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='username'], input[type='text']"))
            )
            username_input.clear()
            username_input.send_keys(USERNAME)
            
            # Enter password
            password_input = self.driver.find_element(By.CSS_SELECTOR, "input[name='password'], input[type='password']")
            password_input.clear()
            password_input.send_keys(PASSWORD)
            
            # Click login button
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
            login_button.click()
            
            # Wait for login to complete
            time.sleep(5)
            
            # Check if login successful
            if "dashboard" in self.driver.current_url or "home" in self.driver.current_url:
                print("Login successful!")
                self.logged_in = True
            else:
                return "Login failed - Invalid credentials or panel issue"
            
            # Now find and click menu button (three lines)
            time.sleep(2)
            
            # Try to find menu/hamburger button
            menu_selectors = [
                "button[class*='menu']",
                "div[class*='menu']",
                "i[class*='bars']",
                "svg[class*='menu']",
                ".navbar-toggler",
                "button[aria-label='Menu']"
            ]
            
            for selector in menu_selectors:
                try:
                    menu_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    menu_button.click()
                    print("Menu clicked")
                    time.sleep(2)
                    break
                except:
                    continue
            
            # Find and click generate option
            generate_selectors = [
                "a[href*='generate']",
                "button[href*='generate']",
                "div:contains('Generate')",
                "span:contains('Generate')",
                "a:contains('Generate')"
            ]
            
            for selector in generate_selectors:
                try:
                    if "contains" in selector:
                        elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), 'Generate')]")
                        if elements:
                            elements[0].click()
                            break
                    else:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        element.click()
                        break
                except:
                    continue
            
            time.sleep(2)
            
            # Select duration
            duration_map = {
                '5h': '5 Hours',
                '3d': '3 Days',
                '7d': '7 Days', 
                '14d': '14 Days',
                '30d': '30 Days',
                '60d': '60 Days'
            }
            
            duration_text = duration_map.get(duration, duration)
            
            # Find and click duration option
            duration_selectors = [
                f"button:contains('{duration_text}')",
                f"div:contains('{duration_text}')",
                f"span:contains('{duration_text}')",
                f"option[value='{duration}']",
                f"input[value='{duration}']"
            ]
            
            for selector in duration_selectors:
                try:
                    if "contains" in selector:
                        elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{duration_text}')]")
                        if elements:
                            elements[0].click()
                            break
                    else:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        element.click()
                        break
                except:
                    continue
            
            time.sleep(1)
            
            # Set max devices (usually 1)
            try:
                device_input = self.driver.find_element(By.CSS_SELECTOR, "input[name='max_devices'], input[type='number']")
                device_input.clear()
                device_input.send_keys("1")
            except:
                pass
            
            # Click generate/submit button
            gen_button_selectors = [
                "button[type='submit']",
                "button:contains('Generate')",
                "button:contains('Create')",
                "input[value='Generate']"
            ]
            
            for selector in gen_button_selectors:
                try:
                    if "contains" in selector:
                        elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), 'Generate') or contains(text(), 'Create')]")
                        if elements:
                            elements[0].click()
                            break
                    else:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        element.click()
                        break
                except:
                    continue
            
            # Wait for key to appear
            time.sleep(5)
            
            # Extract the generated key
            page_source = self.driver.page_source
            
            # Key patterns
            patterns = [
                r'([A-Z0-9]{8}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{12})',
                r'([A-Z0-9]{16,32})',
                r'key["\']?\s*[:=]\s*["\']([A-Z0-9\-]+)',
                r'license["\']?\s*[:=]\s*["\']([A-Z0-9\-]+)',
                r'<code>([^<]+)</code>',
                r'class=["\']key["\']>([^<]+)<',
                r'Your key:?\s*([A-Z0-9\-]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, page_source, re.IGNORECASE)
                if match:
                    key = match.group(1) if match.groups() else match.group(0)
                    return key
            
            # If no key found, return page snippet for debugging
            return f"Key not found. Page snippet: {page_source[:500]}"
            
        except Exception as e:
            return f"Error: {str(e)}"
        finally:
            # Don't close driver to keep session alive
            pass
    
    def close(self):
        if self.driver:
            self.driver.quit()

# Initialize generator
key_gen = SeleniumKeyGen()

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
        "Using Real Browser Method\n"
        "Select key duration:\n\n"
        "⚠️ *Wait 30-40 seconds* for generation",
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
    msg = await query.edit_message_text(
        f"🔄 Generating {duration_names[duration]} key...\n"
        f"⏳ Opening browser and logging in...\n"
        f"This may take 30-40 seconds\n\n"
        f"Please wait...",
        parse_mode='Markdown'
    )
    
    # Generate key
    key = key_gen.login_and_generate(duration)
    
    # Send result
    if "Error" in key or "failed" in key.lower():
        await msg.edit_text(
            f"❌ *Generation Failed*\n\n"
            f"Duration: {duration_names[duration]}\n"
            f"Error: {key}\n\n"
            f"Troubleshooting:\n"
            f"• Panel might have changed\n"
            f"• Try again in 1 minute\n"
            f"• Check if panel is accessible",
            parse_mode='Markdown'
        )
    else:
        await msg.edit_text(
            f"✅ *KEY GENERATED!*\n\n"
            f"🎫 *Duration:* {duration_names[duration]}\n"
            f"🔑 *Your Key:*\n"
            f"`{key}`\n\n"
            f"📋 Copy the key above\n"
            f"⚠️ Valid for {duration_names[duration]} only!\n"
            f"🔒 One time use key",
            parse_mode='Markdown'
        )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot Status*\n\n"
        "✅ Bot is running\n"
        "✅ Using Selenium real browser\n"
        "🟡 Generating keys...\n\n"
        "Use /start to generate key",
        parse_mode='Markdown'
    )

# ============= MAIN =============
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CallbackQueryHandler(generate_callback))
    
    print("=" * 50)
    print("🤖 XSILENT KEY GENERATOR BOT (SELENIUM)")
    print("=" * 50)
    print("✅ Bot started!")
    print("✅ Using real browser to bypass Cloudflare")
    print("✅ Press Ctrl+C to stop")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    main()
