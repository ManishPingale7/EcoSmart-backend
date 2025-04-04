from datetime import datetime
from typing import Dict, Any, List, Optional
from bson import ObjectId
from app.database import database
from app.models import Badge, BadgeLevel, UserBadge, UserBadgeStats

# Collections
badges_collection = database["badges"]
user_badges_collection = database["user_badges"]
user_badge_stats_collection = database["user_badge_stats"]

def serialize_mongo_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize MongoDB document by converting ObjectIds to strings
    and ensuring _id is available as id
    """
    if not doc:
        return {}
        
    result = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, list) and value and all(isinstance(item, ObjectId) for item in value):
            result[key] = [str(item) for item in value]
        else:
            result[key] = value
    
    # Ensure _id is converted to id
    if "_id" in result:
        result["id"] = result["_id"]
    
    return result

# Badge CRUD operations
async def create_badge(badge_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new badge"""
    badge_data["created_at"] = datetime.utcnow()
    badge_data["updated_at"] = datetime.utcnow()
    
    result = await badges_collection.insert_one(badge_data)
    badge_data["id"] = str(result.inserted_id)
    
    return badge_data

async def get_badge(badge_id: str) -> Optional[Dict[str, Any]]:
    """Get badge by ID"""
    badge = await badges_collection.find_one({"_id": ObjectId(badge_id)})
    return serialize_mongo_doc(badge)

async def get_badge_by_required_reports(required_reports: int) -> Optional[Dict[str, Any]]:
    """Get badge by required reports count"""
    badge = await badges_collection.find_one({"required_reports": required_reports})
    return serialize_mongo_doc(badge)

async def get_badges() -> List[Dict[str, Any]]:
    """Get all badges sorted by required_reports"""
    cursor = badges_collection.find().sort("required_reports", 1)
    badges = []
    async for badge in cursor:
        badges.append(serialize_mongo_doc(badge))
    return badges

async def update_badge(badge_id: str, badge_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update badge data"""
    badge_data["updated_at"] = datetime.utcnow()
    
    result = await badges_collection.update_one(
        {"_id": ObjectId(badge_id)},
        {"$set": badge_data}
    )
    
    if result.modified_count:
        return await get_badge(badge_id)
    return None

async def delete_badge(badge_id: str) -> bool:
    """Delete a badge"""
    result = await badges_collection.delete_one({"_id": ObjectId(badge_id)})
    return result.deleted_count > 0

# User Badge CRUD operations
async def assign_user_badge(user_id: str, badge_id: str, badge_name: str, badge_level: str) -> Dict[str, Any]:
    """Assign a badge to a user"""
    user_badge = {
        "user_id": user_id,
        "badge_id": badge_id,
        "badge_name": badge_name,
        "badge_level": badge_level,
        "earned_at": datetime.utcnow(),
        "claimed": False,
        "claimed_at": None
    }
    
    result = await user_badges_collection.insert_one(user_badge)
    user_badge["id"] = str(result.inserted_id)
    
    # Update user badge stats
    await user_badge_stats_collection.update_one(
        {"user_id": user_id},
        {"$addToSet": {"badges_earned": badge_id}, 
         "$set": {"updated_at": datetime.utcnow()}},
        upsert=True
    )
    
    return user_badge

async def get_user_badges(user_id: str) -> List[Dict[str, Any]]:
    """Get all badges earned by a user"""
    cursor = user_badges_collection.find({"user_id": user_id}).sort("earned_at", -1)
    badges = []
    async for badge in cursor:
        badges.append(serialize_mongo_doc(badge))
    return badges

async def claim_badge(user_badge_id: str) -> Optional[Dict[str, Any]]:
    """Mark a badge as claimed"""
    result = await user_badges_collection.update_one(
        {"_id": ObjectId(user_badge_id)},
        {"$set": {"claimed": True, "claimed_at": datetime.utcnow()}}
    )
    
    if result.modified_count:
        badge = await user_badges_collection.find_one({"_id": ObjectId(user_badge_id)})
        return serialize_mongo_doc(badge)
    return None

# User Badge Stats CRUD operations
async def get_user_badge_stats(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user badge stats"""
    stats = await user_badge_stats_collection.find_one({"user_id": user_id})
    return serialize_mongo_doc(stats)

async def increment_user_report_count(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Increment a user's report count in user_badge_stats collection and check badge eligibility
    
    Args:
        user_id: The ID of the user who submitted the report
        
    Returns:
        Updated user badge stats document or None if not found
    """
    # First, get or create user badge stats
    stats = await user_badge_stats_collection.find_one({"user_id": user_id})
    
    if stats:
        # Increment report count
        result = await user_badge_stats_collection.update_one(
            {"user_id": user_id},
            {"$inc": {"total_reports": 1},
             "$set": {"updated_at": datetime.utcnow()}}
        )
    else:
        # Create new badge stats document
        result = await user_badge_stats_collection.insert_one({
            "user_id": user_id,
            "total_reports": 1,
            "badges_earned": [],
            "updated_at": datetime.utcnow()
        })
    
    # Get updated stats
    updated_stats = await user_badge_stats_collection.find_one({"user_id": user_id})
    if not updated_stats:
        return None
    
    # Check badge eligibility
    total_reports = updated_stats.get("total_reports", 0)
    
    # Get all badges and sort by required reports
    all_badges = await get_badges()
    eligible_badges = [b for b in all_badges if total_reports >= b.get("required_reports", 0)]
    
    # Get current user badges
    user_badges = await get_user_badges(user_id)
    earned_badge_ids = [b.get("badge_id") for b in user_badges]
    
    # Assign any new eligible badges
    for badge in eligible_badges:
        if badge.get("id") not in earned_badge_ids:
            await assign_user_badge(
                user_id=user_id,
                badge_id=badge.get("id"),
                badge_name=badge.get("name"),
                badge_level=badge.get("level")
            )
    
    # Return updated stats
    return serialize_mongo_doc(updated_stats)

# Initialize default badges if none exist
async def initialize_default_badges():
    """Initialize default badges if none exist"""
    count = await badges_collection.count_documents({})
    if count == 0:
        default_badges = [
            {
                "name": "Waste Warrior Bronze",
                "description": "Submitted 10 waste reports",
                "level": "bronze",
                "required_reports": 10,
                "image_url": "/assets/badges/bronze.png",
                "rewards": [
                    {"type": "discount", "value": "5% off on EcoSmart products"}
                ]
            },
            {
                "name": "Waste Warrior Silver",
                "description": "Submitted 25 waste reports",
                "level": "silver",
                "required_reports": 25,
                "image_url": "/assets/badges/silver.png",
                "rewards": [
                    {"type": "discount", "value": "10% off on EcoSmart products"},
                    {"type": "reward", "value": "Free composting starter kit"}
                ]
            },
            {
                "name": "Waste Warrior Gold",
                "description": "Submitted 50 waste reports",
                "level": "gold",
                "required_reports": 50,
                "image_url": "/assets/badges/gold.png",
                "rewards": [
                    {"type": "discount", "value": "15% off on EcoSmart products"},
                    {"type": "reward", "value": "Free reusable shopping bag set"},
                    {"type": "certificate", "value": "Official Environmental Champion Certificate"}
                ]
            },
            {
                "name": "Waste Warrior Platinum",
                "description": "Submitted 100 waste reports",
                "level": "platinum",
                "required_reports": 100,
                "image_url": "/assets/badges/platinum.png",
                "rewards": [
                    {"type": "discount", "value": "20% off on EcoSmart products"},
                    {"type": "reward", "value": "Premium eco-friendly gift set"},
                    {"type": "access", "value": "Priority reporting and handling"}
                ]
            },
            {
                "name": "Waste Warrior Diamond",
                "description": "Submitted 250 waste reports",
                "level": "diamond",
                "required_reports": 250,
                "image_url": "/assets/badges/diamond.png",
                "rewards": [
                    {"type": "discount", "value": "25% off on EcoSmart products"},
                    {"type": "reward", "value": "Exclusive sustainable living kit"},
                    {"type": "recognition", "value": "Feature in the EcoSmart community newsletter"},
                    {"type": "access", "value": "Invitation to annual environmental leadership conference"}
                ]
            }
        ]
        
        for badge_data in default_badges:
            await create_badge(badge_data) 