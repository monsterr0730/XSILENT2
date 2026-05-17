import os
import re
import json
import sqlite3
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import cloudscraper
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

# ================= CONFIGURATION =================
BOT_TOKEN = "8466296023:AAGEJjIye-5kv8rA8BX352l17Zhm4ojKRZA"          # Get from @BotFather
OWNER_ID = 7192516189                       # Your Telegram user ID
ADMIN_IDS = [7192516189]                    # List of admin user IDs

# Panel credentials (replace with actual)
PANEL_URL = "https://xsilent.shop/vip"
PANEL_USER = "VIPP"
PANEL_PASS = "roxym830"

# Database file
DB_FILE = "monster_bot.db"

# Conversation states for broadcasting
BROADCAST_STATE = 1

# ================= DATABASE (SQLite) =================
class Database:
    def __init__(self, db_file: str):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                approved BOOLEAN DEFAULT 0,
                is_admin BOOLEAN DEFAULT 0,
                join_date TEXT,
                total_keys INTEGER DEFAULT 0,
                referred_by INTEGER DEFAULT NULL,
                balance REAL DEFAULT 0
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS keys (
                key_id TEXT PRIMARY KEY,
                duration TEXT,
                generated_for INTEGER,
                generated_by INTEGER,
                generated_date TEXT,
                status TEXT DEFAULT 'active'
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                duration TEXT,
                request_date TEXT,
                status TEXT DEFAULT 'pending'
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT,
                sent_by INTEGER,
                sent_date TEXT,
                total_received INTEGER
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                reward_given INTEGER DEFAULT 0,
                date TEXT
            )
        ''')
        self.conn.commit()

    # ---------------- User management ----------------
    def add_user(self, user_id: int, username: str, first_name: str, referred_by: int = None):
        if not self.get_user(user_id):
            is_admin = user_id == OWNER_ID or user_id in ADMIN_IDS
            self.cursor.execute('''
                INSERT INTO users (user_id, username, first_name, approved, is_admin, join_date, referred_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, is_admin, is_admin, datetime.now().isoformat(), referred_by))
            self.conn.commit()
            if referred_by and referred_by != user_id:
                self.add_referral(referred_by, user_id)

    def get_user(self, user_id: int):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone()

    def approve_user(self, user_id: int):
        self.cursor.execute("UPDATE users SET approved = 1 WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def is_approved(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        return user[3] == 1 if user else False

    def is_admin(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        return user[4] == 1 if user else (user_id == OWNER_ID or user_id in ADMIN_IDS)

    def get_all_users(self):
        self.cursor.execute("SELECT user_id, username, first_name, approved FROM users")
        return self.cursor.fetchall()

    def get_approved_users(self) -> List[int]:
        self.cursor.execute("SELECT user_id FROM users WHERE approved = 1")
        return [row[0] for row in self.cursor.fetchall()]

    # ---------------- Key management ----------------
    def save_key(self, key_id: str, duration: str, generated_for: int, generated_by: int):
        self.cursor.execute('''
            INSERT INTO keys (key_id, duration, generated_for, generated_by, generated_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (key_id, duration, generated_for, generated_by, datetime.now().isoformat()))
        self.cursor.execute("UPDATE users SET total_keys = total_keys + 1 WHERE user_id = ?", (generated_for,))
        self.conn.commit()

    def get_user_keys(self, user_id: int):
        self.cursor.execute("SELECT key_id, duration, status, generated_date FROM keys WHERE generated_for = ? ORDER BY generated_date DESC", (user_id,))
        return self.cursor.fetchall()

    def get_key(self, key_id: str):
        self.cursor.execute("SELECT * FROM keys WHERE key_id = ?", (key_id,))
        return self.cursor.fetchone()

    def update_key_status(self, key_id: str, status: str):
        self.cursor.execute("UPDATE keys SET status = ? WHERE key_id = ?", (status, key_id))
        self.conn.commit()

    def delete_key(self, key_id: str):
        self.cursor.execute("DELETE FROM keys WHERE key_id = ?", (key_id,))
        self.conn.commit()

    # ---------------- Request management ----------------
    def add_request(self, user_id: int, duration: str):
        self.cursor.execute('''
            INSERT INTO requests (user_id, duration, request_date)
            VALUES (?, ?, ?)
        ''', (user_id, duration, datetime.now().isoformat()))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_pending_requests(self):
        self.cursor.execute('''
            SELECT r.id, r.user_id, u.username, u.first_name, r.duration, r.request_date
            FROM requests r JOIN users u ON r.user_id = u.user_id
            WHERE r.status = 'pending' ORDER BY r.request_date DESC
        ''')
        return self.cursor.fetchall()

    def update_request_status(self, request_id: int, status: str):
        self.cursor.execute("UPDATE requests SET status = ? WHERE id = ?", (status, request_id))
        self.conn.commit()

    # ---------------- Broadcast ----------------
    def save_broadcast(self, message: str, sent_by: int, total_received: int):
        self.cursor.execute('''
            INSERT INTO broadcasts (message, sent_by, sent_date, total_received)
            VALUES (?, ?, ?, ?)
        ''', (message, sent_by, datetime.now().isoformat(), total_received))
        self.conn.commit()

    # ---------------- Referral ----------------
    def add_referral(self, referrer_id: int, referred_id: int):
        if not self.cursor.execute("SELECT 1 FROM referrals WHERE referred_id = ?", (referred_id,)).fetchone():
            self.cursor.execute('''
                INSERT INTO referrals (referrer_id, referred_id, date)
                VALUES (?, ?, ?)
            ''', (referrer_id, referred_id, datetime.now().isoformat()))
            # Give 5 credits reward
            self.cursor.execute("UPDATE users SET balance = balance + 5 WHERE user_id = ?", (referrer_id,))
            self.conn.commit()
            return True
        return False

    def get_referral_count(self, user_id: int) -> int:
        self.cursor.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
        return self.cursor.fetchone()[0]

    def close(self):
        self.conn.close()

# ================= PANEL COMMUNICATION =================
class PanelClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True},
            delay=15,
            interpret=True
        )
        self.logged_in = False

    def _login(self) -> bool:
        """Attempt to log in to the panel and bypass Cloudflare."""
        try:
            # 1. Get login page to retrieve CSRF token
            resp = self.scraper.get(f"{self.base_url}/login")
            if resp.status_code != 200:
                return False

            # Extract CSRF token (adjust regex based on actual panel)
            csrf_token = None
            match = re.search(r'name="_token"\s+value="([^"]+)"', resp.text)
            if match:
                csrf_token = match.group(1)
            elif re.search(r'csrf-token" content="([^"]+)"', resp.text):
                csrf_token = re.search(r'csrf-token" content="([^"]+)"', resp.text).group(1)

            # 2. Perform login
            login_data = {
                'username': self.username,
                'password': self.password,
                '_token': csrf_token or ''
            }
            login_resp = self.scraper.post(f"{self.base_url}/login", data=login_data)

            # Check for success indicators
            if login_resp.status_code == 200 and ('dashboard' in login_resp.text.lower() or 'logout' in login_resp.text.lower()):
                self.logged_in = True
                return True
            return False
        except Exception as e:
            print(f"Login error: {e}")
            return False

    def generate_key(self, duration: str) -> Optional[str]:
        """Generate a new key from the panel. Returns key string or None."""
        if not self.logged_in and not self._login():
            return None

        try:
            # Convert friendly duration to panel's expected format (customize as needed)
            duration_map = {
                '5h': '5_hours', '3d': '3_days', '7d': '7_days',
                '14d': '14_days', '30d': '30_days', '60d': '60_days'
            }
            payload = {'duration': duration_map.get(duration, duration), 'max_devices': 1}
            # Try POST to /generate endpoint
            resp = self.scraper.post(f"{self.base_url}/generate", data=payload)
            if resp.status_code == 200:
                # Attempt to extract key from JSON or HTML
                try:
                    data = resp.json()
                    return data.get('key') or data.get('license') or data.get('code')
                except:
                    # Search HTML for key patterns
                    patterns = [
                        r'([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})',
                        r'([A-Z0-9]{16,32})',
                        r'<code>(.+?)</code>'
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, resp.text, re.IGNORECASE)
                        if match:
                            return match.group(1)
            return None
        except Exception as e:
            print(f"Key generation error: {e}")
            return None

    def delete_key(self, key_id: str) -> bool:
        """Delete/revoke a key from the panel."""
        if not self.logged_in and not self._login():
            return False
        try:
            # Adjust endpoint as needed
            resp = self.scraper.post(f"{self.base_url}/key/delete", data={'key_id': key_id})
            return resp.status_code == 200 and 'success' in resp.text.lower()
        except Exception as e:
            print(f"Delete key error: {e}")
            return False

    def block_key(self, key_id: str) -> bool:
        """Block a key."""
        if not self.logged_in and not self._login():
            return False
        try:
            resp = self.scraper.post(f"{self.base_url}/key/block", data={'key_id': key_id})
            return resp.status_code == 200 and 'success' in resp.text.lower()
        except Exception as e:
            print(f"Block key error: {e}")
            return False

# ================= TELEGRAM BOT =================
db = Database(DB_FILE)
panel = PanelClient(PANEL_URL, PANEL_USER, PANEL_PASS)

# ---------- Helper functions ----------
def get_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔑 Generate Key", callback_data="generate_menu")],
        [InlineKeyboardButton("📜 My Keys", callback_data="my_keys")],
        [InlineKeyboardButton("👥 Referral", callback_data="referral")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    if db.is_admin(user_id):
        keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

# ---------- User commands ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referred_by = context.args[0] if context.args else None
    if referred_by:
        try:
            referred_by = int(referred_by)
        except:
            referred_by = None

    db.add_user(user.id, user.username, user.first_name, referred_by)

    welcome_text = (
        f"🎉 Welcome {user.first_name}!\n\n"
        f"This bot helps you generate license keys from the panel.\n"
        f"Status: {'✅ Approved' if db.is_approved(user.id) else '⏳ Pending approval'}\n\n"
        f"Use the buttons below to interact."
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard(user.id))

async def request_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if db.is_approved(user.id):
        await update.message.reply_text("You are already approved!")
        return

    # Add request to database
    db.add_request(user.id, "full_access")

    # Notify all admins
    for admin_id in ADMIN_IDS + [OWNER_ID]:
        try:
            await context.bot.send_message(
                admin_id,
                f"🆕 Access request from {user.first_name} (@{user.username})\nID: `{user.id}`\n"
                f"Use /approve {user.id} to grant access.",
                parse_mode='Markdown'
            )
        except:
            pass

    await update.message.reply_text("✅ Request sent to admin. You'll be notified once approved.")

async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ You are not authorized to approve users.")
        return

    try:
        user_id = int(context.args[0])
    except:
        await update.message.reply_text("Usage: /approve <user_id>")
        return

    db.approve_user(user_id)
    await update.message.reply_text(f"✅ User {user_id} approved.")
    try:
        await context.bot.send_message(user_id, "✅ Congratulations! Your access has been approved. Use /start to generate keys.")
    except:
        pass

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📚 *Help*\n\n"
        "/start - Show main menu\n"
        "/request - Request access to use the bot\n"
        "/help - Show this message\n\n"
        "*Generating keys:*\n"
        "1. Use the 'Generate Key' button\n"
        "2. Choose duration\n"
        "3. Your key will appear\n\n"
        "*Admin commands:*\n"
        "/approve <user_id> - Approve a user\n"
        "/broadcast - Send message to all approved users\n"
        "/addkey <duration> <key> - Manually add a key (backup)\n"
        "/delkey <key_id> - Delete a key from panel\n"
        "/blockkey <key_id> - Block a key"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ---------- Callback handlers ----------
async def generate_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not db.is_approved(query.from_user.id):
        await query.edit_message_text("❌ You are not approved. Use /request to get access.")
        return

    keyboard = [
        [InlineKeyboardButton("⏰ 5 Hours", callback_data="gen_5h")],
        [InlineKeyboardButton("📅 3 Days", callback_data="gen_3d")],
        [InlineKeyboardButton("📆 7 Days", callback_data="gen_7d")],
        [InlineKeyboardButton("📊 14 Days", callback_data="gen_14d")],
        [InlineKeyboardButton("🌟 30 Days", callback_data="gen_30d")],
        [InlineKeyboardButton("💎 60 Days", callback_data="gen_60d")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ]
    await query.edit_message_text("🔑 Select key duration:", reply_markup=InlineKeyboardMarkup(keyboard))

async def generate_key_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    duration = query.data.split('_')[1]
    user_id = query.from_user.id
    duration_names = {'5h':'5 Hours', '3d':'3 Days', '7d':'7 Days', '14d':'14 Days', '30d':'30 Days', '60d':'60 Days'}
    name = duration_names[duration]

    msg = await query.edit_message_text(f"🔄 Generating {name} key...\nPlease wait ⏳")

    # Attempt to generate key from panel
    key = panel.generate_key(duration)

    if key:
        db.save_key(key, name, user_id, user_id)
        await msg.edit_text(
            f"✅ *Key generated successfully!*\n\n"
            f"🎫 *Duration:* {name}\n"
            f"🔑 `{key}`\n\n"
            f"⚠️ Valid for {name} only.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
        )
    else:
        await msg.edit_text(
            f"❌ Failed to generate {name} key.\n"
            f"The panel might be blocking the request. Please try again later or contact admin.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
        )

async def my_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    keys = db.get_user_keys(user_id)

    if not keys:
        await query.edit_message_text("📭 You have no keys yet.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
        return

    text = "🔑 *Your keys:*\n\n"
    for k_id, dur, status, date in keys[:10]:
        status_emoji = "✅" if status == "active" else "❌"
        text += f"{status_emoji} `{k_id}` – {dur} (generated {date[:10]})\n"

    if len(keys) > 10:
        text += f"\n... and {len(keys)-10} more."
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={user_id}"
    count = db.get_referral_count(user_id)
    text = (
        f"👥 *Referral program*\n\n"
        f"Share your link and earn 5 credits per referral!\n\n"
        f"🔗 `{link}`\n\n"
        f"📊 Referrals: {count}\n"
        f"💰 Balance: {db.get_user(user_id)[7] if db.get_user(user_id) else 0} credits"
    )
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))

# ---------- Admin panel ----------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not db.is_admin(query.from_user.id):
        await query.edit_message_text("❌ Admin access only.")
        return

    keyboard = [
        [InlineKeyboardButton("👥 Pending Approvals", callback_data="admin_approvals")],
        [InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔑 Manage Keys", callback_data="admin_manage_keys")],
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]
    await query.edit_message_text("⚙️ *Admin Panel*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def admin_approvals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pending = db.get_pending_requests()
    if not pending:
        await query.edit_message_text("No pending approvals.")
        return

    for req in pending:
        req_id, uid, username, first_name, duration, date = req
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Approve", callback_data=f"approve_user_{uid}")],
            [InlineKeyboardButton("❌ Reject", callback_data=f"reject_req_{req_id}")]
        ])
        await query.message.reply_text(
            f"Request from {first_name} (@{username})\nID: `{uid}`\nDate: {date[:10]}",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    await query.delete_message()

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📢 Send the message you want to broadcast to all approved users.\n\nType /cancel to abort.")
    return BROADCAST_STATE

async def broadcast_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "/cancel":
        await update.message.reply_text("Broadcast cancelled.")
        return ConversationHandler.END

    message = update.message.text
    users = db.get_approved_users()
    sent = 0
    for uid in users:
        try:
            await context.bot.send_message(uid, f"📢 *Announcement*\n\n{message}", parse_mode='Markdown')
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    db.save_broadcast(message, update.effective_user.id, sent)
    await update.message.reply_text(f"✅ Broadcast sent to {sent} users.")
    return ConversationHandler.END

async def admin_manage_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Simple list of keys (can be extended)
    keys = db.cursor.execute("SELECT key_id, status FROM keys LIMIT 20").fetchall()
    if not keys:
        await query.edit_message_text("No keys in database.")
        return
    text = "🔑 *Keys in DB:*\n"
    for key_id, status in keys:
        text += f"`{key_id}` – {status}\n"
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]))

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    total_users = len(db.get_all_users())
    approved = len(db.get_approved_users())
    total_keys = db.cursor.execute("SELECT COUNT(*) FROM keys").fetchone()[0]
    active_keys = db.cursor.execute("SELECT COUNT(*) FROM keys WHERE status='active'").fetchone()[0]
    text = (
        f"📊 *Statistics*\n\n"
        f"👥 Users: {total_users}\n"
        f"✅ Approved: {approved}\n"
        f"🔑 Total keys generated: {total_keys}\n"
        f"🟢 Active keys: {active_keys}"
    )
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]))

async def approve_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = int(query.data.split('_')[2])
    db.approve_user(uid)
    await query.message.edit_text(f"✅ User {uid} approved.")
    try:
        await context.bot.send_message(uid, "✅ Your access has been approved! Use /start to generate keys.")
    except:
        pass

async def reject_request_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    req_id = int(query.data.split('_')[2])
    db.update_request_status(req_id, 'rejected')
    await query.message.edit_text(f"Request {req_id} rejected.")

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🏠 *Main Menu*",
        reply_markup=get_main_keyboard(query.from_user.id),
        parse_mode='Markdown'
    )

# ---------- Manual key commands (admin) ----------
async def add_key_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only.")
        return
    try:
        duration = context.args[0]
        key_id = context.args[1]
        user_id = update.effective_user.id
        db.save_key(key_id, duration, user_id, user_id)
        await update.message.reply_text(f"✅ Key `{key_id}` added to DB.", parse_mode='Markdown')
    except:
        await update.message.reply_text("Usage: /addkey <duration> <key_id>")

async def delete_key_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only.")
        return
    try:
        key_id = context.args[0]
        # Delete from panel
        if panel.delete_key(key_id):
            db.delete_key(key_id)
            await update.message.reply_text(f"✅ Key `{key_id}` deleted from panel and DB.", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ Failed to delete key from panel.", parse_mode='Markdown')
    except:
        await update.message.reply_text("Usage: /delkey <key_id>")

async def block_key_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not db.is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only.")
        return
    try:
        key_id = context.args[0]
        if panel.block_key(key_id):
            db.update_key_status(key_id, 'blocked')
            await update.message.reply_text(f"✅ Key `{key_id}` blocked.", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ Failed to block key from panel.", parse_mode='Markdown')
    except:
        await update.message.reply_text("Usage: /blockkey <key_id>")

# ================= MAIN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("request", request_access))
    app.add_handler(CommandHandler("approve", approve_user))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("addkey", add_key_command))
    app.add_handler(CommandHandler("delkey", delete_key_command))
    app.add_handler(CommandHandler("blockkey", block_key_command))

    # Callback handlers
    app.add_handler(CallbackQueryHandler(generate_menu, pattern="^generate_menu$"))
    app.add_handler(CallbackQueryHandler(generate_key_callback, pattern="^gen_"))
    app.add_handler(CallbackQueryHandler(my_keys, pattern="^my_keys$"))
    app.add_handler(CallbackQueryHandler(referral, pattern="^referral$"))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_approvals, pattern="^admin_approvals$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast, pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(admin_manage_keys, pattern="^admin_manage_keys$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(approve_user_callback, pattern="^approve_user_"))
    app.add_handler(CallbackQueryHandler(reject_request_callback, pattern="^reject_req_"))
    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))

    # Conversation handler for broadcast
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast, pattern="^admin_broadcast$")],
        states={BROADCAST_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_receive)]},
        fallbacks=[CommandHandler("cancel", lambda u,c: ConversationHandler.END)]
    )
    app.add_handler(broadcast_conv)

    print("🤖 Bot started. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
