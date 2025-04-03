from datetime import datetime
from typing import Optional, Dict, Any
from bson import ObjectId
from app.database import users_collection
from app.models import GoogleUser

async def create_user(user_data: dict) -> Dict[str, Any]:
    """Create a new user"""
    user_dict = {
        **user_data,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await users_collection.insert_one(user_dict)
    user_dict["id"] = str(result.inserted_id)
    
    return user_dict

async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email"""
    return await users_collection.find_one({"email": email})

async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user by ID"""
    return await users_collection.find_one({"_id": ObjectId(user_id)})

async def update_user(user_id: str, user_data: dict) -> Optional[Dict[str, Any]]:
    """Update user data"""
    user_data["updated_at"] = datetime.utcnow()
    
    result = await users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": user_data}
    )
    
    if result.modified_count:
        return await get_user_by_id(user_id)
    return None

async def delete_user(user_id: str) -> bool:
    """Delete user"""
    result = await users_collection.delete_one({"_id": ObjectId(user_id)})
    return result.deleted_count > 0

async def get_or_create_google_user(user_info: dict) -> Dict[str, Any]:
    """Get existing user or create new one from Google info"""
    existing_user = await get_user_by_email(user_info["email"])
    if existing_user:
        return existing_user
    
    user_dict = {
        "email": user_info["email"],
        "name": user_info["name"],
        "picture": user_info.get("picture"),
        "google_id": user_info["sub"]
    }
    
    return await create_user(user_dict) 