from motor.motor_asyncio import AsyncIOMotorClient
from app.config import MONGO_URI

client = AsyncIOMotorClient(MONGO_URI)
db = client["photocards_db"]

# 1. Live incoming capture logs
collection = db["posts"]

# 2. Archived historical logs
history_collection = db["posts_history"]

# 3. Isolated working dataset copies
dataset_collection = db["dataset_copies"]