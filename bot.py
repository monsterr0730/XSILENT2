#!/usr/bin/env python3
import telebot
import requests
import time
import threading
import json
import re
from datetime import datetime, timedelta
from pymongo import MongoClient

# ========== TIMEZONE (IST) ==========
IST = timedelta(hours=5, minutes=30)

def get_current_time():
    return (datetime.now() + IST).strftime('%d %b %Y, %I:%M:%S %p')

# ========== CONFIG ==========
BOT_TOKEN = "8466296023:AAGEJjIye-5kv8rA8BX352l17Zhm4ojKRZA"
ADMIN_ID = ["7192516189"]
PANEL_URL = "https://xsilent.shop/vip"
PANEL_USER = "VIPP"
PANEL_PASS = "roxym830"

# ========== MONGODB ==========
MONGO_URI = "mongodb+srv://mohitrao83076_db_user:LugF1xwlenkWRE1F@monster.ydmmckl.mongodb.net/?retryWrites=true&w=majority&appName=MONSTER"
client = MongoClient(MONGO_URI)
db = client["panel_bot"]

users_collection = db["users"]
keys_collection = db["keys"]
broadcast_collection = db["broadcast"]
settings_collection = db["settings"]

print("✅ MongoDB Connected!")
print(f"📅 Server Time: {get_current_time()}")

# ========== DATA STRUCTURES ==========
maintenance_mode = False
panel_session = None

# ========== LOAD/SAVE FUNCTIONS ==========
def load_users():
    data = users_collection.find_one({"_id": "users"})
    if not data:
        data = {"users": ADMIN_ID, "approved": [], "pending": [], "blocked": []}
        users_collection.insert_one({"_id": "users", **data})
    return data

def save_users(data):
    users_collection.update_one({"_id": "users"}, {"$set": data}, upsert=True)

def load_keys():
    keys = {}
    for key_data in keys_collection.find():
        keys[key_data["key"]] = {
            "user_id": key_data.get("user_id"),
            "generated_by": key_data.get("generated_by"),
            "generated_at": key_data.get("generated_at"),
            "used": key_data.get("used", False),
            "used_by": key_data.get("used_by"),
            "used_at": key_data.get("used_at"),
            "blocked": key_data.get("blocked", False)
        }
    return keys

def save_keys(keys_data):
    keys_collection.delete_many({})
    for key, info in keys_data.items():
        info["key"] = key
        keys_collection.insert_one(info)

def load_broadcast():
    data = broadcast_collection.find_one({"_id": "broadcast"})
    if not data:
        data = {"users": []}
        broadcast_collection.insert_one({"_id": "broadcast", **data})
    return data

def save_broadcast(data):
    broadcast_collection.update_one({"_id": "broadcast"}, {"$set": data}, upsert=True)

def load_settings():
    data = settings_collection.find_one({"_id": "settings"})
    if not data:
        data = {"maintenance": False}
        settings_collection.insert_one({"_id": "settings", **data})
    return data

def save_settings(data):
    settings_collection.update_one({"_id": "settings"}, {"$set": data}, upsert=True)

# ========== LOAD DATA ==========
users_data = load_users()
users = users_data["users"]
approved_users = users_data.get("approved", [])
pending_users = users_data.get("pending", [])
blocked_users = users_data.get("blocked", [])

keys_data = load_keys()
broadcast_data = load_broadcast()
broadcast_users = broadcast_data.get("users", [])
settings = load_settings()
maintenance_mode = settings.get("maintenance", False)

bot = telebot.TeleBot(BOT_TOKEN)

# ========== PANEL LOGIN FUNCTION ==========
def panel_login():
    global panel_session
    try:
        session = requests.Session()
        
        # Login to panel
        login_data = {
            "username": PANEL_USER,
            "password": PANEL_PASS
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": PANEL_URL,
            "Referer": f"{PANEL_URL}/login"
        }
        
        response = session.post(f"{PANEL_URL}/api/login", data=login_data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            panel_session = session
            print("✅ Panel Login Successful!")
            return True
        else:
            print(f"❌ Panel Login Failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Panel Error: {e}")
        return False

# ========== GENERATE KEY FROM PANEL ==========
def generate_key_from_panel():
    try:
        if not panel_session:
            panel_login()
        
        response = panel_session.post(f"{PANEL_URL}/api/generate-key", timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return data.get("key")
        return None
    except:
        return None

# ========== DELETE KEY FROM PANEL ==========
def delete_key_from_panel(key):
    try:
        if not panel_session:
            panel_login()
        
        response = panel_session.post(f"{PANEL_URL}/api/delete-key", json={"key": key}, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("success", False)
        return False
    except:
        return False

# ========== GET USER KEYS FROM PANEL ==========
def get_user_keys(user_id):
    try:
        if not panel_session:
            panel_login()
        
        response = panel_session.get(f"{PANEL_URL}/api/user-keys/{user_id}", timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("keys", [])
        return []
    except:
        return []

# ========== STYLED MESSAGE ==========
def styled_msg(title, content, status="info"):
    icon = "✅" if status == "success" else "❌" if status == "error" else "⚠️" if status == "warning" else "📌"
    return f"""
┌{'─' * 45}┐
│ {icon} {title:<42} │
├{'─' * 45}┤
{content}
└{'─' * 45}┘"""

# ========== BOT COMMANDS ==========

@bot.message_handler(commands=['start'])
def start(m):
    uid = str(m.chat.id)
    chat_type = m.chat.type
    
    if uid not in broadcast_users:
        broadcast_users.append(uid)
        save_broadcast({"users": broadcast_users})
    
    if uid in ADMIN_ID:
        content = f"""│ 👑 Welcome Owner!
│
│ 📅 {get_current_time()}
│
│ 📝 COMMANDS:
│
│ 🔑 KEYS:
│   /genkey - Generate Key
│   /removekey KEY - Delete Key
│   /mykeys - Your Keys
│
│ 👥 USERS:
│   /approve USER_ID - Approve User
│   /disapprove USER_ID - Disapprove User
│   /block USER_ID - Block User
│   /unblock USER_ID - Unblock User
│   /pending - Pending Users
│   /approved - Approved Users
│   /blocked - Blocked Users
│
│ 📢 BROADCAST:
│   /broadcast MESSAGE - Send to all
│
│ 🔧 OTHER:
│   /maintenance on/off
│   /stats - Bot Stats
│   /help - Help Menu"""
        bot.reply_to(m, styled_msg("OWNER PANEL", content, "success"))
    
    elif uid in approved_users:
        content = f"""│ ✅ Welcome User!
│
│ 📅 {get_current_time()}
│
│ 📝 COMMANDS:
│
│ 🔑 KEYS:
│   /genkey - Generate Key
│   /mykeys - Your Keys
│
│ ℹ️ OTHER:
│   /help - Help Menu"""
        bot.reply_to(m, styled_msg("USER PANEL", content, "success"))
    
    elif uid in pending_users:
        content = f"""│ ⏳ PENDING APPROVAL
│
│ 📅 {get_current_time()}
│
│ Your request is pending.
│ Contact admin for approval.
│
│ 📝 COMMANDS:
│   /status - Check Status"""
        bot.reply_to(m, styled_msg("PENDING", content, "warning"))
    
    elif uid in blocked_users:
        content = f"""│ 🚫 ACCOUNT BLOCKED
│
│ 📅 {get_current_time()}
│
│ Your account has been blocked.
│ Contact admin for support."""
        bot.reply_to(m, styled_msg("BLOCKED", content, "error"))
    
    else:
        # New user - add to pending
        if uid not in pending_users and uid not in approved_users and uid not in blocked_users:
            pending_users.append(uid)
            users_data["pending"] = pending_users
            save_users(users_data)
        
        content = f"""│ 👋 Welcome!
│
│ 📅 {get_current_time()}
│
│ Your request has been sent to admin.
│ Please wait for approval.
│
│ 📝 COMMANDS:
│   /status - Check Status"""
        bot.reply_to(m, styled_msg("REQUEST SENT", content, "info"))

@bot.message_handler(commands=['status'])
def status_cmd(m):
    uid = str(m.chat.id)
    
    if uid in approved_users:
        bot.reply_to(m, styled_msg("STATUS", "│ ✅ Your account is APPROVED!\n│ You can use /genkey", "success"))
    elif uid in pending_users:
        bot.reply_to(m, styled_msg("STATUS", "│ ⏳ Your request is PENDING.\n│ Please wait for admin approval.", "warning"))
    elif uid in blocked_users:
        bot.reply_to(m, styled_msg("STATUS", "│ 🚫 Your account is BLOCKED.\n│ Contact admin for support.", "error"))
    else:
        bot.reply_to(m, styled_msg("STATUS", "│ ❌ No request found.\n│ Use /start to register.", "error"))

@bot.message_handler(commands=['genkey'])
def genkey(m):
    uid = str(m.chat.id)
    
    if maintenance_mode and uid not in ADMIN_ID:
        bot.reply_to(m, styled_msg("MAINTENANCE", "│ 🔧 Bot is under maintenance!", "warning"))
        return
    
    if uid not in ADMIN_ID and uid not in approved_users:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Your account is not approved!\n│ Contact admin.", "error"))
        return
    
    # Try to generate key from panel
    key = generate_key_from_panel()
    
    if key:
        keys_data[key] = {
            "user_id": uid,
            "generated_by": uid,
            "generated_at": time.time(),
            "used": False,
            "blocked": False
        }
        save_keys(keys_data)
        
        content = f"""│ 🔑 KEY GENERATED!
│
│ Key: `{key}`
│
│ ⚠️ Save this key safely!
│ Key will be deleted if misused."""
        bot.reply_to(m, styled_msg("SUCCESS", content, "success"), parse_mode='Markdown')
    else:
        bot.reply_to(m, styled_msg("ERROR", "│ ❌ Failed to generate key!\n│ Please try again later.", "error"))

@bot.message_handler(commands=['mykeys'])
def mykeys(m):
    uid = str(m.chat.id)
    
    if uid not in ADMIN_ID and uid not in approved_users:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Unauthorized!", "error"))
        return
    
    my_keys = []
    for key, info in keys_data.items():
        if info.get("generated_by") == uid:
            status = "✅ Active" if not info.get("blocked") else "🚫 Blocked"
            my_keys.append(f"🔑 `{key}` - {status}")
    
    if my_keys:
        content = "│ YOUR KEYS:\n│\n" + "\n".join([f"│ {k}" for k in my_keys])
        bot.reply_to(m, styled_msg("MY KEYS", content, "info"), parse_mode='Markdown')
    else:
        bot.reply_to(m, styled_msg("MY KEYS", "│ 📋 No keys found!\n│ Use /genkey to generate.", "info"))

@bot.message_handler(commands=['removekey'])
def removekey(m):
    uid = str(m.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Owner only!", "error"))
        return
    
    args = m.text.split()
    if len(args) != 2:
        bot.reply_to(m, "⚠️ Usage: /removekey KEY")
        return
    
    key = args[1]
    
    if key in keys_data:
        # Delete from panel
        if delete_key_from_panel(key):
            del keys_data[key]
            save_keys(keys_data)
            bot.reply_to(m, styled_msg("KEY REMOVED", f"│ ✅ Key `{key}` removed from panel!", "success"), parse_mode='Markdown')
        else:
            bot.reply_to(m, styled_msg("ERROR", "│ ❌ Failed to remove key from panel!", "error"))
    else:
        bot.reply_to(m, styled_msg("ERROR", "│ ❌ Key not found!", "error"))

@bot.message_handler(commands=['approve'])
def approve_user(m):
    uid = str(m.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Owner only!", "error"))
        return
    
    args = m.text.split()
    if len(args) != 2:
        bot.reply_to(m, "⚠️ Usage: /approve USER_ID")
        return
    
    target = args[1]
    
    if target in pending_users:
        pending_users.remove(target)
        if target not in approved_users:
            approved_users.append(target)
        users_data["pending"] = pending_users
        users_data["approved"] = approved_users
        save_users(users_data)
        
        bot.reply_to(m, styled_msg("USER APPROVED", f"│ ✅ User {target} approved!", "success"))
        
        try:
            bot.send_message(target, styled_msg("APPROVED", "│ ✅ Your account has been APPROVED!\n│ You can now use /genkey", "success"))
        except:
            pass
    else:
        bot.reply_to(m, styled_msg("ERROR", "│ ❌ User not found in pending list!", "error"))

@bot.message_handler(commands=['disapprove'])
def disapprove_user(m):
    uid = str(m.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Owner only!", "error"))
        return
    
    args = m.text.split()
    if len(args) != 2:
        bot.reply_to(m, "⚠️ Usage: /disapprove USER_ID")
        return
    
    target = args[1]
    
    if target in pending_users:
        pending_users.remove(target)
        users_data["pending"] = pending_users
        save_users(users_data)
        
        bot.reply_to(m, styled_msg("USER DISAPPROVED", f"│ ❌ User {target} disapproved!", "warning"))
        
        try:
            bot.send_message(target, styled_msg("DISAPPROVED", "│ ❌ Your request has been disapproved.\n│ Contact admin for more info.", "error"))
        except:
            pass
    else:
        bot.reply_to(m, styled_msg("ERROR", "│ ❌ User not found in pending list!", "error"))

@bot.message_handler(commands=['block'])
def block_user(m):
    uid = str(m.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Owner only!", "error"))
        return
    
    args = m.text.split()
    if len(args) != 2:
        bot.reply_to(m, "⚠️ Usage: /block USER_ID")
        return
    
    target = args[1]
    
    if target in approved_users:
        approved_users.remove(target)
        if target not in blocked_users:
            blocked_users.append(target)
        users_data["approved"] = approved_users
        users_data["blocked"] = blocked_users
        save_users(users_data)
        
        bot.reply_to(m, styled_msg("USER BLOCKED", f"│ 🚫 User {target} blocked!", "warning"))
        
        try:
            bot.send_message(target, styled_msg("BLOCKED", "│ 🚫 Your account has been BLOCKED!\n│ Contact admin for support.", "error"))
        except:
            pass
    else:
        bot.reply_to(m, styled_msg("ERROR", "│ ❌ User not found in approved list!", "error"))

@bot.message_handler(commands=['unblock'])
def unblock_user(m):
    uid = str(m.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Owner only!", "error"))
        return
    
    args = m.text.split()
    if len(args) != 2:
        bot.reply_to(m, "⚠️ Usage: /unblock USER_ID")
        return
    
    target = args[1]
    
    if target in blocked_users:
        blocked_users.remove(target)
        if target not in approved_users:
            approved_users.append(target)
        users_data["blocked"] = blocked_users
        users_data["approved"] = approved_users
        save_users(users_data)
        
        bot.reply_to(m, styled_msg("USER UNBLOCKED", f"│ ✅ User {target} unblocked!", "success"))
        
        try:
            bot.send_message(target, styled_msg("UNBLOCKED", "│ ✅ Your account has been UNBLOCKED!\n│ You can now use /genkey", "success"))
        except:
            pass
    else:
        bot.reply_to(m, styled_msg("ERROR", "│ ❌ User not found in blocked list!", "error"))

@bot.message_handler(commands=['pending'])
def pending_list(m):
    uid = str(m.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Owner only!", "error"))
        return
    
    if pending_users:
        content = "│ PENDING USERS:\n│\n" + "\n".join([f"│ 🟡 {u}" for u in pending_users])
        bot.reply_to(m, styled_msg("PENDING LIST", content, "warning"))
    else:
        bot.reply_to(m, styled_msg("PENDING LIST", "│ 📋 No pending users!", "info"))

@bot.message_handler(commands=['approved'])
def approved_list(m):
    uid = str(m.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Owner only!", "error"))
        return
    
    if approved_users:
        content = "│ APPROVED USERS:\n│\n" + "\n".join([f"│ ✅ {u}" for u in approved_users])
        bot.reply_to(m, styled_msg("APPROVED LIST", content, "success"))
    else:
        bot.reply_to(m, styled_msg("APPROVED LIST", "│ 📋 No approved users!", "info"))

@bot.message_handler(commands=['blocked'])
def blocked_list(m):
    uid = str(m.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Owner only!", "error"))
        return
    
    if blocked_users:
        content = "│ BLOCKED USERS:\n│\n" + "\n".join([f"│ 🚫 {u}" for u in blocked_users])
        bot.reply_to(m, styled_msg("BLOCKED LIST", content, "error"))
    else:
        bot.reply_to(m, styled_msg("BLOCKED LIST", "│ 📋 No blocked users!", "info"))

@bot.message_handler(commands=['broadcast'])
def broadcast(m):
    uid = str(m.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Owner only!", "error"))
        return
    
    if not m.reply_to_message:
        bot.reply_to(m, "⚠️ Reply to a message to broadcast!")
        return
    
    success = 0
    fail = 0
    
    for user in broadcast_users:
        try:
            bot.copy_message(user, m.chat.id, m.reply_to_message.message_id)
            success += 1
        except:
            fail += 1
    
    bot.reply_to(m, styled_msg("BROADCAST SENT", f"│ ✅ Success: {success}\n│ ❌ Failed: {fail}", "success"))

@bot.message_handler(commands=['maintenance'])
def maintenance(m):
    uid = str(m.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Owner only!", "error"))
        return
    
    args = m.text.split()
    if len(args) != 2 or args[1] not in ['on', 'off']:
        bot.reply_to(m, "⚠️ Usage: /maintenance on/off")
        return
    
    global maintenance_mode
    maintenance_mode = (args[1] == 'on')
    settings["maintenance"] = maintenance_mode
    save_settings(settings)
    
    status = "ENABLED" if maintenance_mode else "DISABLED"
    bot.reply_to(m, styled_msg("MAINTENANCE", f"│ 🔧 Maintenance mode {status}!", "warning"))

@bot.message_handler(commands=['stats'])
def stats(m):
    uid = str(m.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Owner only!", "error"))
        return
    
    content = f"""│ 📊 BOT STATISTICS
│
│ 👑 Owner: {len(ADMIN_ID)}
│ ✅ Approved: {len(approved_users)}
│ ⏳ Pending: {len(pending_users)}
│ 🚫 Blocked: {len(blocked_users)}
│ 🔑 Total Keys: {len(keys_data)}
│ 📢 Broadcast Users: {len(broadcast_users)}
│
│ 📅 {get_current_time()}"""
    
    bot.reply_to(m, styled_msg("STATS", content, "info"))

@bot.message_handler(commands=['help'])
def help_cmd(m):
    uid = str(m.chat.id)
    
    if uid in ADMIN_ID:
        content = f"""│ 👑 OWNER HELP
│
│ 🔑 KEYS:
│   /genkey - Generate Key
│   /removekey KEY - Delete Key
│   /mykeys - Your Keys
│
│ 👥 USERS:
│   /approve USER_ID - Approve User
│   /disapprove USER_ID - Disapprove User
│   /block USER_ID - Block User
│   /unblock USER_ID - Unblock User
│   /pending - Pending Users
│   /approved - Approved Users
│   /blocked - Blocked Users
│
│ 📢 BROADCAST:
│   /broadcast (reply to message)
│
│ 🔧 OTHER:
│   /maintenance on/off
│   /stats - Bot Stats
│   /help - This Menu
│
│ 📅 {get_current_time()}"""
        bot.reply_to(m, styled_msg("OWNER HELP", content))
    
    elif uid in approved_users:
        content = f"""│ ✅ USER HELP
│
│ 🔑 KEYS:
│   /genkey - Generate Key
│   /mykeys - Your Keys
│
│ ℹ️ OTHER:
│   /status - Check Status
│   /help - This Menu
│
│ 📅 {get_current_time()}"""
        bot.reply_to(m, styled_msg("USER HELP", content))
    
    elif uid in pending_users:
        bot.reply_to(m, styled_msg("PENDING", "│ ⏳ Wait for admin approval!\n│ Use /status to check.", "warning"))
    
    elif uid in blocked_users:
        bot.reply_to(m, styled_msg("BLOCKED", "│ 🚫 Your account is blocked!\n│ Contact admin.", "error"))
    
    else:
        bot.reply_to(m, styled_msg("HELP", "│ Use /start to register!", "info"))

# ========== INITIAL PANEL LOGIN ==========
print("=" * 50)
print("🔐 Logging into Panel...")
panel_login()
print("=" * 50)

print("✨ PANEL BOT STARTED ✨")
print(f"👑 Owner: {ADMIN_ID[0]}")
print(f"✅ Approved: {len(approved_users)}")
print(f"⏳ Pending: {len(pending_users)}")
print(f"📅 {get_current_time()}")
print("=" * 50)

bot.infinity_polling()
