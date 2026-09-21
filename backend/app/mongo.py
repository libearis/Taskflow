from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings

_client = AsyncIOMotorClient(settings.mongo_url)
mongo_db = _client[settings.mongo_db]

project_boards = mongo_db["project_boards"]
user_workload = mongo_db["user_workload"]
