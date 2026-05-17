#!/usr/bin/env python3
import telebot
import requests
import time
import threading
import json
import re
import random
import string
from datetime import datetime, timedelta
from pymongo import MongoClient
import cloudscraper

# ========== TIMEZONE (IST) ==========
IST = timedelta(hours=5, minutes=30)

def get_current_time():
    return (datetime.now() + IST).strftime('%d %b %Y, %I:%M:%S %p')

# ========== CONFIG ==========
BOT_TOKEN = "8466296023:AAGEJjIye-5kv8rA8BX352l17Zhm4ojKRZA"
ADMIN_ID = ["7192516189"]
PANEL_URL = "https://xsilent.shop/vip"
PANEL_USER = "VIPPP"
PANEL_PASS = "roxym830"

# ========== MONGODB ==========
MONGO_URI = "mongodb+srv://mohitrao83076_db_user:LugF1xwlenkWRE1F@monster.ydmmckl.mongodb.net/?retryWrites=true&w=majority&appName=MONSTER"
client = MongoClient(MONGO_URI)
db = client["panel_bot"]

users_collection = db["users"]
keys_collection = db["keys"]
broadcast_collection = db["broadcast"]
settings_collection = db["settings"]
resellers_collection = db["resellers"]
referrals_collection = db["referrals"]

print("✅ MongoDB Connected!")
print(f"📅 Server Time: {get_current_time()}")

# ========== DATA STRUCTURES ==========
maintenance_mode = False
panel_scraper = None

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

def load_resellers():
    data = resellers_collection.find_one({"_id": "resellers"})
    if not data:
        data = {"resellers": []}
        resellers_collection.insert_one({"_id": "resellers", **data})
    return data

def save_resellers(data):
    resellers_collection.update_one({"_id": "resellers"}, {"$set": data}, upsert=True)

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

resellers_data = load_resellers()
resellers = resellers_data.get("resellers", [])

bot = telebot.TeleBot(BOT_TOKEN)

# ========== PANEL CONNECTION WITH CLOUDSCRAPER ==========
def panel_login():
    global panel_scraper
    try:
        # Create cloudscraper to bypass Cloudflare
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )
        
        # Try different login endpoints
        login_endpoints = [
            f"{PANEL_URL}/api/login",
            f"{PANEL_URL}/login",
            f"{PANEL_URL}/api/auth/login",
            f"{PANEL_URL}/v1/login"
        ]
        
        for endpoint in login_endpoints:
            try:
                print(f"Trying login: {endpoint}")
                response = scraper.post(endpoint, json={
                    "username": PANEL_USER,
                    "password": PANEL_PASS
                }, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") or data.get("token"):
                        panel_scraper = scraper
                        print(f"✅ Panel Login Successful! ({endpoint})")
                        return True
            except:
                continue
        
        print("❌ Panel Login Failed - All endpoints failed")
        return False
    except Exception as e:
        print(f"❌ Panel Error: {e}")
        return False

def generate_key_from_panel(user_id=None):
    try:
        if not panel_scraper:
            panel_login()
        
        if panel_scraper:
            # Try different endpoints
            endpoints = [
                f"{PANEL_URL}/api/generate-key",
                f"{PANEL_URL}/api/key/generate",
                f"{PANEL_URL}/api/v1/generate-key"
            ]
            
            for endpoint in endpoints:
                try:
                    payload = {"user_id": user_id} if user_id else {}
                    response = panel_scraper.post(endpoint, json=payload, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("key"):
                            return data.get("key")
                        if data.get("code"):
                            return data.get("code")
                except:
                    continue
        
        # Fallback: Generate local key
        return generate_local_key()
    except:
        return generate_local_key()

def generate_local_key():
    """Generate local key when panel is unavailable"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

def delete_key_from_panel(key):
    try:
        if not panel_scraper:
            panel_login()
        
        if panel_scraper:
            endpoints = [
                f"{PANEL_URL}/api/delete-key",
                f"{PANEL_URL}/api/key/delete"
            ]
            
            for endpoint in endpoints:
                try:
                    response = panel_scraper.post(endpoint, json={"key": key}, timeout=30)
                    if response.status_code == 200:
                        return True
                except:
                    continue
        return False
    except:
        return False

def get_user_keys_from_panel(user_id):
    try:
        if not panel_scraper:
            panel_login()
        
        if panel_scraper:
            response = panel_scraper.get(f"{PANEL_URL}/api/user-keys/{user_id}", timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data.get("keys", [])
        return []
    except:
        return []

def generate_referral_code(user_id):
    """Generate referral code for reseller"""
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    referrals_collection.insert_one({
        "user_id": user_id,
        "code": code,
        "created_at": time.time(),
        "used_by": [],
        "earnings": 0
    })
    return code

def get_referral_info(user_id):
    return referrals_collection.find_one({"user_id": user_id})

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
│   /blockkey KEY - Block Key
│   /unblockkey KEY - Unblock Key
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
│ 🔗 REFERRAL:
│   /addreseller USER_ID - Add Reseller
│   /removereseller USER_ID - Remove Reseller
│   /myreferral - Your Referral Code
│
│ 📢 BROADCAST:
│   /broadcast (reply to message)
│
│ 🔧 OTHER:
│   /maintenance on/off
│   /stats - Bot Stats
│   /help - Help Menu"""
        bot.reply_to(m, styled_msg("OWNER PANEL", content, "success"))
    
    elif uid in resellers:
        content = f"""│ 💎 Welcome Reseller!
│
│ 📅 {get_current_time()}
│
│ 📝 COMMANDS:
│
│ 🔑 KEYS:
│   /genkey - Generate Key
│   /mykeys - Your Keys
│
│ 🔗 REFERRAL:
│   /myreferral - Your Referral Code
│
│ ℹ️ OTHER:
│   /help - Help Menu"""
        bot.reply_to(m, styled_msg("RESELLER PANEL", content, "success"))
    
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
    elif uid in resellers:
        bot.reply_to(m, styled_msg("STATUS", "│ 💎 Your account is RESELLER!\n│ You can generate keys and get referrals", "success"))
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
    
    if uid not in ADMIN_ID and uid not in resellers and uid not in approved_users:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Your account is not approved!\n│ Contact admin.", "error"))
        return
    
    msg = bot.reply_to(m, "⏳ Generating key... Please wait...")
    
    try:
        # Try to get key from panel, fallback to local
        key = generate_key_from_panel(uid)
        
        if key:
            keys_data[key] = {
                "user_id": uid,
                "generated_by": uid,
                "generated_at": time.time(),
                "used": False,
                "blocked": False
            }
            save_keys(keys_data)
            
            bot.edit_message_text(
                styled_msg("SUCCESS", f"│ 🔑 KEY GENERATED!\n│\n│ Key: `{key}`\n│\n│ ⚠️ Save this key safely!", "success"),
                msg.chat.id, msg.message_id, parse_mode='Markdown'
            )
        else:
            bot.edit_message_text(
                styled_msg("ERROR", "│ ❌ Failed to generate key!\n│ Please try again later.", "error"),
                msg.chat.id, msg.message_id
            )
    except Exception as e:
        bot.edit_message_text(
            styled_msg("ERROR", f"│ ❌ Error: {str(e)[:50]}\n│ Contact admin!", "error"),
            msg.chat.id, msg.message_id
        )

@bot.message_handler(commands=['mykeys'])
def mykeys(m):
    uid = str(m.chat.id)
    
    if uid not in ADMIN_ID and uid not in resellers and uid not in approved_users:
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
        delete_key_from_panel(key)
        del keys_data[key]
        save_keys(keys_data)
        bot.reply_to(m, styled_msg("KEY REMOVED", f"│ ✅ Key `{key}` removed!", "success"), parse_mode='Markdown')
    else:
        bot.reply_to(m, styled_msg("ERROR", "│ ❌ Key not found!", "error"))

@bot.message_handler(commands=['blockkey'])
def blockkey(m):
    uid = str(m.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Owner only!", "error"))
        return
    
    args = m.text.split()
    if len(args) != 2:
        bot.reply_to(m, "⚠️ Usage: /blockkey KEY")
        return
    
    key = args[1]
    
    if key in keys_data:
        keys_data[key]["blocked"] = True
        save_keys(keys_data)
        bot.reply_to(m, styled_msg("KEY BLOCKED", f"│ 🚫 Key `{key}` blocked!", "warning"), parse_mode='Markdown')
    else:
        bot.reply_to(m, styled_msg("ERROR", "│ ❌ Key not found!", "error"))

@bot.message_handler(commands=['unblockkey'])
def unblockkey(m):
    uid = str(m.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Owner only!", "error"))
        return
    
    args = m.text.split()
    if len(args) != 2:
        bot.reply_to(m, "⚠️ Usage: /unblockkey KEY")
        return
    
    key = args[1]
    
    if key in keys_data:
        keys_data[key]["blocked"] = False
        save_keys(keys_data)
        bot.reply_to(m, styled_msg("KEY UNBLOCKED", f"│ ✅ Key `{key}` unblocked!", "success"), parse_mode='Markdown')
    else:
        bot.reply_to(m, styled_msg("ERROR", "│ ❌ Key not found!", "error"))

@bot.message_handler(commands=['addreseller'])
def add_reseller(m):
    uid = str(m.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Owner only!", "error"))
        return
    
    args = m.text.split()
    if len(args) != 2:
        bot.reply_to(m, "⚠️ Usage: /addreseller USER_ID")
        return
    
    target = args[1]
    
    if target not in resellers:
        resellers.append(target)
        save_resellers({"resellers": resellers})
        
        if target in approved_users:
            approved_users.remove(target)
        users_data["approved"] = approved_users
        save_users(users_data)
        
        bot.reply_to(m, styled_msg("RESELLER ADDED", f"│ ✅ User {target} is now a reseller!", "success"))
        
        try:
            bot.send_message(target, styled_msg("RESELLER ACCESS", "│ 💎 You have been promoted to RESELLER!\n│ You can now generate keys and get referrals.", "success"))
        except:
            pass
    else:
        bot.reply_to(m, styled_msg("ERROR", "│ ❌ User is already a reseller!", "error"))

@bot.message_handler(commands=['removereseller'])
def remove_reseller(m):
    uid = str(m.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(m, styled_msg("ACCESS DENIED", "│ ❌ Owner only!", "error"))
        return
    
    args = m.text.split()
    if len(args) != 2:
        bot.reply_to(m, "⚠️ Usage: /removereseller USER_ID")
        return
    
    target = args[1]
    
    if target in resellers:
        resellers.remove(target)
        save_resellers({"resellers": resellers})
        bot.reply_to(m, styled_msg("RESELLER REMOVED", f"│ ✅ User {target} is no longer a reseller!", "success"))
    else:
        bot.reply_to(m, styled_msg("ERROR", "│ ❌ User is not a reseller!", "error"))

@bot.message_handler(commands=['myreferral'])
def myreferral(m):
    uid = str(m.chat.id)
    
    ref_info = get_referral_info(uid)
    
    if not ref_info:
        code = generate_referral_code(uid)
        content = f"""│ 🔗 YOUR REFERRAL CODE
│
│ Code: `{code}`
│
│ Share this code with others.
│ When they use it, you get rewards!"""
        bot.reply_to(m, styled_msg("REFERRAL", content, "success"), parse_mode='Markdown')
    else:
        content = f"""│ 🔗 YOUR REFERRAL CODE
│
│ Code: `{ref_info['code']}`
│
│ Used by: {len(ref_info.get('used_by', []))} users
│ Total Earnings: {ref_info.get('earnings', 0)}"""
        bot.reply_to(m, styled_msg("REFERRAL", content, "info"), parse_mode='Markdown')

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
    elif target in resellers:
        resellers.remove(target)
        if target not in blocked_users:
            blocked_users.append(target)
        save_resellers({"resellers": resellers})
        users_data["blocked"] = blocked_users
        save_users(users_data)
        bot.reply_to(m, styled_msg("RESELLER BLOCKED", f"│ 🚫 Reseller {target} blocked!", "warning"))
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
    
    total_keys = len(keys_data)
    active_keys = len([k for k, v in keys_data.items() if not v.get("blocked")])
    
    content = f"""│ 📊 BOT STATISTICS
│
│ 👑 Owner: {len(ADMIN_ID)}
│ 💎 Resellers: {len(resellers)}
│ ✅ Approved: {len(approved_users)}
│ ⏳ Pending: {len(pending_users)}
│ 🚫 Blocked: {len(blocked_users)}
│ 🔑 Total Keys: {total_keys}
│ 🔓 Active Keys: {active_keys}
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
│   /blockkey KEY - Block Key
│   /unblockkey KEY - Unblock Key
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
│ 🔗 REFERRAL:
│   /addreseller USER_ID - Add Reseller
│   /removereseller USER_ID - Remove Reseller
│   /myreferral - Your Referral Code
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
    
    elif uid in resellers:
        content = f"""│ 💎 RESELLER HELP
│
│ 🔑 KEYS:
│   /genkey - Generate Key
│   /mykeys - Your Keys
│
│ 🔗 REFERRAL:
│   /myreferral - Your Referral Code
│
│ ℹ️ OTHER:
│   /status - Check Status
│   /help - This Menu
│
│ 📅 {get_current_time()}"""
        bot.reply_to(m, styled_msg("RESELLER HELP", content))
    
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
print(f"💎 Resellers: {len(resellers)}")
print(f"✅ Approved: {len(approved_users)}")
print(f"⏳ Pending: {len(pending_users)}")
print(f"📅 {get_current_time()}")
print("=" * 50)

bot.infinity_polling()
