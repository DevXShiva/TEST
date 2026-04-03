import os
import motor.motor_asyncio
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv("MONGO_URL"))
        self.db = self.client["m3u8_bot_db"]
        self.users = self.db["users"]

    async def add_user(self, user_id, username):
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": {"username": username}},
            upsert=True
        )

db = Database()
