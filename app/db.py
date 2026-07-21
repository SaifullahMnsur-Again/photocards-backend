from motor.motor_asyncio import AsyncIOMotorClient
from app.config import MONGO_URI

client = AsyncIOMotorClient(MONGO_URI)
db = client["photocards_db"]

# 1. Live incoming capture logs
collection = db["posts"]

# 2. Archived historical logs
history_collection = db["posts_history"]

# 3. Dataset Project Definitions (Metadata & Custom Classes)
projects_collection = db["projects"]

# 4. Multi-Project Working Items (Metadata and Central Image Links)
dataset_collection = db["dataset_copies"]