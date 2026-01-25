from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI

# Initialize Database Connection
client = AsyncIOMotorClient(MONGO_URI)
db = client['gmail_otp_bot']

# --- Collections ---
users = db['users']
seen_msgs = db['seen_messages']
oauth_states = db['oauth_states']
server_lock = db['server_lock']

# --- RAM CACHE (Enabled for Speed) ---
# We use this to make button clicks instant, while services.py 
# bypasses it for critical login detection.
USER_CACHE = {}

async def get_user(uid: str):
    """
    Retrieves user data.
    Priority: RAM (Fast) -> Database (Slow)
    """
    # 1. Check RAM first (Instant response)
    if uid in USER_CACHE:
        return USER_CACHE[uid]
    
    # 2. If not in RAM, fetch from Database
    user = await users.find_one({"uid": uid})
    
    # 3. Save to RAM for next time
    if user:
        USER_CACHE[uid] = user
        
    return user

async def update_user(uid: str, data: dict):
    """
    Updates both Database and RAM immediately.
    """
    # 1. Update Database (Persistent Storage)
    await users.update_one({"uid": uid}, {"$set": data}, upsert=True)
    
    # 2. Update RAM (So the UI updates instantly without re-fetching)
    if uid in USER_CACHE:
        USER_CACHE[uid].update(data)
    else:
        # If the user wasn't in cache, fetch the full object to be safe
        user = await users.find_one({"uid": uid})
        if user:
            USER_CACHE[uid] = user

async def delete_user_data(uid: str):
    """
    Deletes user from both Database and RAM.
    """
    # 1. Delete from Database
    await users.delete_one({"uid": uid})
    
    # 2. Delete from RAM
    if uid in USER_CACHE:
        del USER_CACHE[uid]
