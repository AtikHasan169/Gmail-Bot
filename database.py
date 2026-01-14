from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI

client = AsyncIOMotorClient(MONGO_URI)
db = client['gmail_otp_bot']

users = db['users']
seen_msgs = db['seen_messages']

async def get_user(uid: str):
    return await users.find_one({"uid": uid})

async def update_user(uid: str, data: dict):
    await users.update_one({"uid": uid}, {"$set": data}, upsert=True)
