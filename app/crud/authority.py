from datetime import datetime
from typing import Optional, Dict, Any
from bson import ObjectId
from app.database import authorities_collection
from app.models import AuthorityCreate, Authority
from app.security import get_password_hash, verify_password

async def create_authority(authority: AuthorityCreate) -> Authority:
    """Create a new authority"""
    authority_dict = authority.dict()
    authority_dict["password"] = get_password_hash(authority_dict["password"])
    authority_dict["created_at"] = datetime.utcnow()
    authority_dict["updated_at"] = datetime.utcnow()
    
    result = await authorities_collection.insert_one(authority_dict)
    authority_dict["id"] = str(result.inserted_id)
    
    return Authority(**authority_dict)

async def get_authority_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get authority by username"""
    return await authorities_collection.find_one({"username": username})

async def get_authority_by_id(authority_id: str) -> Optional[Dict[str, Any]]:
    """Get authority by ID"""
    return await authorities_collection.find_one({"_id": ObjectId(authority_id)})

async def update_authority(authority_id: str, authority_data: dict) -> Optional[Dict[str, Any]]:
    """Update authority data"""
    authority_data["updated_at"] = datetime.utcnow()
    
    if "password" in authority_data:
        authority_data["password"] = get_password_hash(authority_data["password"])
    
    result = await authorities_collection.update_one(
        {"_id": ObjectId(authority_id)},
        {"$set": authority_data}
    )
    
    if result.modified_count:
        return await get_authority_by_id(authority_id)
    return None

async def delete_authority(authority_id: str) -> bool:
    """Delete authority"""
    result = await authorities_collection.delete_one({"_id": ObjectId(authority_id)})
    return result.deleted_count > 0

async def authenticate_authority(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate authority"""
    authority = await get_authority_by_username(username)
    if not authority or not verify_password(password, authority["password"]):
        return None
    return authority 