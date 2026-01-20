from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI

# Initialize Client
client = AsyncIOMotorClient(MONGO_URI)

# Database Name
db = client['gmail_otp_bot']

# Collections
users = db['users']
seen_msgs = db['seen_messages']
oauth_states = db['oauth_states'] # Stores the secret "state" tokens for login
server_lock = db['server_lock']   # Stores the Highlander ID to prevent conflicts

# --- RAM CACHE ---
USER_CACHE = {}

async def get_user(uid: str):
    # 1. Try RAM (Fast)
    if uid in USER_CACHE:
        return USER_CACHE[uid]
    
    # 2. Try DB (Slow)
    user = await users.find_one({"uid": uid})
    
    # 3. Update RAM
    if user:
        USER_CACHE[uid] = user
        
    return user

async def update_user(uid: str, data: dict):
    # 1. Update DB
    await users.update_one({"uid": uid}, {"$set": data}, upsert=True)
    
    # 2. Update RAM
    if uid in USER_CACHE:
        USER_CACHE[uid].update(data)
    else:
        # Fetch fresh to ensure we have specific fields if needed later
        pass

async def delete_user_data(uid: str):
    # 1. Delete DB
    await users.delete_one({"uid": uid})
    
    # 2. Clear RAM
    if uid in USER_CACHE:
        del USER_CACHE[uid]
