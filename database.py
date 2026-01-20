from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI

# Initialize the Asynchronous MongoDB Client
client = AsyncIOMotorClient(MONGO_URI)

# Select the Database
# You can change 'gmail_otp_bot' to any name you prefer
db = client['gmail_otp_bot']

# --- EXPORTED COLLECTIONS ---
# We assign these variables so other files can import them easily
users = db['users']
seen_msgs = db['seen_messages']
oauth_states = db['oauth_states'] # Stores the secret login tokens
server_lock = db['server_lock']   # Stores the 'Killer Protocol' lock

# --- RAM CACHE ---
# A simple memory cache to speed up the bot and reduce database hits
USER_CACHE = {}

async def get_user(uid: str):
    # 1. Try to get from RAM first (Super Fast)
    if uid in USER_CACHE:
        return USER_CACHE[uid]
    
    # 2. If not in RAM, get from Database (Slower)
    user = await users.find_one({"uid": uid})
    
    # 3. Save to RAM for next time
    if user:
        USER_CACHE[uid] = user
        
    return user

async def update_user(uid: str, data: dict):
    # 1. Save to Database (Safe)
    await users.update_one({"uid": uid}, {"$set": data}, upsert=True)
    
    # 2. Update RAM (Fast)
    if uid in USER_CACHE:
        USER_CACHE[uid].update(data)
    else:
        # If not in cache, we just leave it empty. 
        # The next 'get_user' will fetch the full updated profile from DB.
        pass

async def delete_user_data(uid: str):
    # 1. Delete from Database
    await users.delete_one({"uid": uid})
    
    # 2. Delete from RAM
    if uid in USER_CACHE:
        del USER_CACHE[uid]
