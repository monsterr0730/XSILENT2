from pymongo import MongoClient
from datetime import datetime
import config

class Database:
    def __init__(self):
        self.client = MongoClient(config.MONGODB_URI)
        self.db = self.client[config.DATABASE_NAME]
        
        # Collections
        self.users = self.db.users
        self.keys = self.db.keys
        self.requests = self.db.requests
        self.broadcasts = self.db.broadcasts
        self.referrals = self.db.referrals
        
        # Create indexes
        self.users.create_index("user_id", unique=True)
        self.keys.create_index("key_code", unique=True)
    
    # User functions
    def add_user(self, user_id, username, first_name, referred_by=None):
        try:
            user = self.users.find_one({"user_id": user_id})
            if not user:
                self.users.insert_one({
                    "user_id": user_id,
                    "username": username,
                    "first_name": first_name,
                    "is_approved": False,
                    "is_admin": user_id in config.ADMIN_IDS or user_id == config.OWNER_ID,
                    "join_date": datetime.now().isoformat(),
                    "total_keys": 0,
                    "balance": 0,
                    "referred_by": referred_by
                })
                return True
            return False
        except Exception as e:
            print(f"Error adding user: {e}")
            return False
    
    def get_user(self, user_id):
        return self.users.find_one({"user_id": user_id})
    
    def approve_user(self, user_id):
        self.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_approved": True}}
        )
    
    def disapprove_user(self, user_id):
        self.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_approved": False}}
        )
    
    def is_approved(self, user_id):
        user = self.get_user(user_id)
        return user["is_approved"] if user else False
    
    def is_admin(self, user_id):
        user = self.get_user(user_id)
        return user["is_admin"] if user else (user_id in config.ADMIN_IDS or user_id == config.OWNER_ID)
    
    def make_admin(self, user_id):
        self.users.update_one(
            {"user_id": user_id},
            {"$set": {"is_admin": True}}
        )
    
    def get_all_users(self):
        return list(self.users.find({}, {"user_id": 1, "username": 1, "first_name": 1, "is_approved": 1}))
    
    def get_approved_users(self):
        return [user["user_id"] for user in self.users.find({"is_approved": True}, {"user_id": 1})]
    
    def get_pending_users(self):
        return list(self.users.find({"is_approved": False}, {"user_id": 1, "username": 1, "first_name": 1}))
    
    def get_user_count(self):
        return self.users.count_documents({})
    
    def get_approved_count(self):
        return self.users.count_documents({"is_approved": True})
    
    # Key functions
    def save_key(self, key_code, duration, generated_by, generated_for):
        try:
            self.keys.insert_one({
                "key_code": key_code,
                "duration": duration,
                "generated_by": generated_by,
                "generated_for": generated_for,
                "generated_date": datetime.now().isoformat(),
                "status": "active"
            })
            
            self.users.update_one(
                {"user_id": generated_for},
                {"$inc": {"total_keys": 1}}
            )
            return True
        except Exception as e:
            print(f"Error saving key: {e}")
            return False
    
    def get_user_keys(self, user_id, limit=10):
        return list(self.keys.find(
            {"generated_for": user_id},
            {"key_code": 1, "duration": 1, "status": 1, "generated_date": 1}
        ).sort("generated_date", -1).limit(limit))
    
    def get_key(self, key_code):
        return self.keys.find_one({"key_code": key_code})
    
    def block_key(self, key_code):
        self.keys.update_one(
            {"key_code": key_code},
            {"$set": {"status": "blocked"}}
        )
    
    def delete_key(self, key_code):
        self.keys.delete_one({"key_code": key_code})
    
    def get_all_keys(self):
        return list(self.keys.find({}, {"key_code": 1, "duration": 1, "status": 1, "generated_for": 1}))
    
    # Request functions
    def add_request(self, user_id, duration):
        request = {
            "user_id": user_id,
            "duration": duration,
            "request_date": datetime.now().isoformat(),
            "status": "pending"
        }
        result = self.requests.insert_one(request)
        return result.inserted_id
    
    def get_pending_requests(self):
        return list(self.requests.aggregate([
            {"$match": {"status": "pending"}},
            {"$lookup": {
                "from": "users",
                "localField": "user_id",
                "foreignField": "user_id",
                "as": "user"
            }},
            {"$unwind": "$user"},
            {"$sort": {"request_date": -1}}
        ]))
    
    def update_request_status(self, request_id, status):
        self.requests.update_one(
            {"_id": request_id},
            {"$set": {"status": status}}
        )
    
    # Broadcast functions
    def save_broadcast(self, message, sent_by, total_received):
        self.broadcasts.insert_one({
            "message": message,
            "sent_by": sent_by,
            "sent_date": datetime.now().isoformat(),
            "total_received": total_received
        })
    
    # Referral functions
    def add_referral(self, referrer_id, referred_id):
        # Check if already referred
        existing = self.referrals.find_one({"referred_id": referred_id})
        if existing:
            return False
        
        self.referrals.insert_one({
            "referrer_id": referrer_id,
            "referred_id": referred_id,
            "reward_given": 0,
            "date": datetime.now().isoformat()
        })
        
        # Add balance to referrer
        self.users.update_one(
            {"user_id": referrer_id},
            {"$inc": {"balance": 5}}
        )
        return True
    
    def get_referral_count(self, user_id):
        return self.referrals.count_documents({"referrer_id": user_id})
    
    def get_referrals(self, user_id):
        return list(self.referrals.find({"referrer_id": user_id}))
    
    # Stats
    def get_stats(self):
        return {
            "total_users": self.get_user_count(),
            "approved_users": self.get_approved_count(),
            "total_keys": self.keys.count_documents({}),
            "active_keys": self.keys.count_documents({"status": "active"}),
            "total_requests": self.requests.count_documents({}),
            "pending_requests": self.requests.count_documents({"status": "pending"})
        }
