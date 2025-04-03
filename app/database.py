from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings

settings = get_settings()

client = AsyncIOMotorClient(settings.MONGO_URI)
database = client[settings.DATABASE_NAME]

# Collections
authorities_collection = database.authorities
users_collection = database.users

async def get_database():
    """
    Get the database instance.
    """
    return database

# Indexes
async def create_indexes():
    # Authority indexes
    await authorities_collection.create_index("username", unique=True)
    await authorities_collection.create_index("email", unique=True)
    
    # User indexes
    await users_collection.create_index("email", unique=True)
    await users_collection.create_index("google_id", unique=True) 