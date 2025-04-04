from typing import Dict, Any, List, Optional
from datetime import datetime
from bson import ObjectId
from ..database import get_database
from ..models import PickupRequest

# Initialize database and collections
db = None
pickup_collection = None

async def init_collections():
    global db, pickup_collection
    db = await get_database()
    pickup_collection = db.pickup_requests

async def schedule_pickup(pickup_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Schedule a new pickup request
    """
    global pickup_collection
    if pickup_collection is None:
        await init_collections()
        
    # Ensure created_at and updated_at are set
    if not pickup_data.get("created_at"):
        pickup_data["created_at"] = datetime.utcnow()
    pickup_data["updated_at"] = datetime.utcnow()
    
    # Insert the pickup request
    result = await pickup_collection.insert_one(pickup_data)
    pickup_data["id"] = str(result.inserted_id)
    
    # Remove MongoDB _id field
    if "_id" in pickup_data:
        del pickup_data["_id"]
        
    return pickup_data

async def get_all_pickups() -> List[Dict[str, Any]]:
    """
    Get all pickup requests
    """
    global pickup_collection
    if pickup_collection is None:
        await init_collections()
        
    # Fetch all pickup requests, sorted by pickup date
    pickups = await pickup_collection.find().sort("pickup_date", 1).to_list(length=None)
    
    # Format the results
    for pickup in pickups:
        pickup["id"] = str(pickup["_id"])
        del pickup["_id"]
        
    return pickups

async def get_user_pickups(user_id: str) -> List[Dict[str, Any]]:
    """
    Get pickup requests for a specific user
    """
    global pickup_collection
    if pickup_collection is None:
        await init_collections()
        
    # Fetch pickups for the user, sorted by pickup date
    pickups = await pickup_collection.find({"user_id": user_id}).sort("pickup_date", 1).to_list(length=None)
    
    # Format the results
    for pickup in pickups:
        pickup["id"] = str(pickup["_id"])
        del pickup["_id"]
        
    return pickups

async def get_pickup_by_id(pickup_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a pickup request by ID
    """
    global pickup_collection
    if pickup_collection is None:
        await init_collections()
        
    try:
        # Convert string ID to ObjectId
        object_id = ObjectId(pickup_id)
        
        # Fetch the pickup
        pickup = await pickup_collection.find_one({"_id": object_id})
        
        if pickup:
            pickup["id"] = str(pickup["_id"])
            del pickup["_id"]
            
        return pickup
    except Exception:
        return None

async def update_pickup_status(pickup_id: str, status: str) -> Optional[Dict[str, Any]]:
    """
    Update the status of a pickup request
    """
    global pickup_collection
    if pickup_collection is None:
        await init_collections()
        
    try:
        # Convert string ID to ObjectId
        object_id = ObjectId(pickup_id)
        
        # Update the pickup status
        await pickup_collection.update_one(
            {"_id": object_id},
            {"$set": {
                "status": status,
                "updated_at": datetime.utcnow()
            }}
        )
        
        # Return the updated pickup
        return await get_pickup_by_id(pickup_id)
    except Exception:
        return None 