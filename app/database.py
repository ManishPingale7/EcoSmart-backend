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
    await users_collection.create_index("total_reports")  # For efficient badge level calculations
    
    # Waste report indexes
    await database["waste_reports"].create_index([("created_at", -1)])  # Sort newest first
    await database["waste_reports"].create_index("severity")  # Filter by severity
    await database["waste_reports"].create_index("status")  # Filter by status
    await database["waste_reports"].create_index([("submitted_by.user_id", 1)])  # Find reports by user 