from typing import Dict, Any, List, Optional
from datetime import datetime
from bson import ObjectId
from ..database import get_database
from ..models import CityStats

# Initialize database and collections
db = None
city_stats_collection = None

async def init_collections():
    global db, city_stats_collection
    db = await get_database()
    city_stats_collection = db.city_stats

async def upsert_city_stats(city_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update or insert city statistics
    """
    global city_stats_collection
    if city_stats_collection is None:
        await init_collections()
        
    city_name = city_data.get("city_name")
    if not city_name:
        raise ValueError("City name is required")
    
    # Normalize city name (lowercase for case-insensitive matching)
    normalized_city = city_name.lower()
    
    # Set last updated timestamp
    city_data["last_updated"] = datetime.utcnow()
    
    # Find existing city or create new one
    existing_city = await city_stats_collection.find_one({"city_name_lower": normalized_city})
    
    if existing_city:
        # Update existing city
        await city_stats_collection.update_one(
            {"city_name_lower": normalized_city},
            {"$set": {**city_data, "city_name_lower": normalized_city}}
        )
        # Get updated city
        updated_city = await city_stats_collection.find_one({"city_name_lower": normalized_city})
        if updated_city:
            updated_city["id"] = str(updated_city["_id"])
            del updated_city["_id"]
        return updated_city
    else:
        # Create new city
        city_data["city_name_lower"] = normalized_city
        result = await city_stats_collection.insert_one(city_data)
        city_data["id"] = str(result.inserted_id)
        
        return city_data

async def get_city_stats(city_name: str) -> Optional[Dict[str, Any]]:
    """
    Get statistics for a specific city
    """
    global city_stats_collection
    if city_stats_collection is None:
        await init_collections()
        
    # Normalize city name
    normalized_city = city_name.lower()
    
    # Find city
    city = await city_stats_collection.find_one({"city_name_lower": normalized_city})
    
    if city:
        city["id"] = str(city["_id"])
        del city["_id"]
        return city
    
    return None

async def get_all_city_stats() -> List[Dict[str, Any]]:
    """
    Get statistics for all cities
    """
    global city_stats_collection
    if city_stats_collection is None:
        await init_collections()
        
    # Find all cities
    cities = await city_stats_collection.find().to_list(length=None)
    
    # Format the results
    for city in cities:
        city["id"] = str(city["_id"])
        del city["_id"]
        
    return cities

async def get_city_leaderboard() -> List[Dict[str, Any]]:
    """
    Get city leaderboard sorted by total score
    """
    global city_stats_collection
    if city_stats_collection is None:
        await init_collections()
        
    # Find all cities and sort by total_score in descending order
    cities = await city_stats_collection.find().sort("total_score", -1).to_list(length=None)
    
    # Format the results and calculate ranks
    ranked_cities = []
    for rank, city in enumerate(cities, start=1):
        city["id"] = str(city["_id"])
        del city["_id"]
        city["rank"] = rank
        ranked_cities.append(city)
        
    return ranked_cities

async def increment_city_report_count(city_name: str, resolved: bool = False) -> Optional[Dict[str, Any]]:
    """
    Increment report count for a city
    """
    global city_stats_collection
    if city_stats_collection is None:
        await init_collections()
        
    # Normalize city name
    normalized_city = city_name.lower()
    
    # Prepare update data
    update_data = {
        "$inc": {
            "total_reports": 1
        },
        "$set": {
            "last_updated": datetime.utcnow()
        }
    }
    
    # Increment resolved or pending reports based on status
    if resolved:
        update_data["$inc"]["resolved_reports"] = 1
    else:
        update_data["$inc"]["pending_reports"] = 1
    
    # Update city stats
    result = await city_stats_collection.update_one(
        {"city_name_lower": normalized_city},
        update_data,
        upsert=True
    )
    
    # If city was created (upsert), set the city_name
    if result.upserted_id:
        await city_stats_collection.update_one(
            {"_id": result.upserted_id},
            {"$set": {"city_name": city_name, "city_name_lower": normalized_city}}
        )
    
    # Get updated city
    updated_city = await city_stats_collection.find_one({"city_name_lower": normalized_city})
    if updated_city:
        updated_city["id"] = str(updated_city["_id"])
        del updated_city["_id"]
        
    return updated_city

async def update_city_engagement(city_name: str, engagement_delta: float) -> Optional[Dict[str, Any]]:
    """
    Update engagement score for a city
    """
    global city_stats_collection
    if city_stats_collection is None:
        await init_collections()
        
    # Normalize city name
    normalized_city = city_name.lower()
    
    # Get current city data
    city = await city_stats_collection.find_one({"city_name_lower": normalized_city})
    
    if not city:
        # Create city if it doesn't exist
        await upsert_city_stats({
            "city_name": city_name,
            "engagement_score": engagement_delta
        })
    else:
        # Update engagement score
        current_engagement = city.get("engagement_score", 0) or 0
        new_engagement = current_engagement + engagement_delta
        
        await city_stats_collection.update_one(
            {"city_name_lower": normalized_city},
            {"$set": {
                "engagement_score": new_engagement,
                "last_updated": datetime.utcnow()
            }}
        )
    
    # Calculate total score
    await calculate_city_score(city_name)
    
    # Get updated city
    updated_city = await city_stats_collection.find_one({"city_name_lower": normalized_city})
    if updated_city:
        updated_city["id"] = str(updated_city["_id"])
        del updated_city["_id"]
        
    return updated_city

async def increment_city_users(city_name: str, delta: int = 1) -> Optional[Dict[str, Any]]:
    """
    Increment user count for a city
    """
    global city_stats_collection
    if city_stats_collection is None:
        await init_collections()
        
    # Normalize city name
    normalized_city = city_name.lower()
    
    # Update city stats
    result = await city_stats_collection.update_one(
        {"city_name_lower": normalized_city},
        {
            "$inc": {"total_users": delta},
            "$set": {"last_updated": datetime.utcnow()}
        },
        upsert=True
    )
    
    # If city was created (upsert), set the city_name
    if result.upserted_id:
        await city_stats_collection.update_one(
            {"_id": result.upserted_id},
            {"$set": {"city_name": city_name, "city_name_lower": normalized_city}}
        )
    
    # Get updated city
    updated_city = await city_stats_collection.find_one({"city_name_lower": normalized_city})
    if updated_city:
        updated_city["id"] = str(updated_city["_id"])
        del updated_city["_id"]
        
    return updated_city

async def calculate_city_score(city_name: str) -> Optional[Dict[str, Any]]:
    """
    Calculate overall score for a city based on various metrics
    """
    global city_stats_collection
    if city_stats_collection is None:
        await init_collections()
        
    # Normalize city name
    normalized_city = city_name.lower()
    
    # Get city data
    city = await city_stats_collection.find_one({"city_name_lower": normalized_city})
    
    if not city:
        return None
    
    # Get all metrics
    total_reports = city.get("total_reports", 0) or 0
    resolved_reports = city.get("resolved_reports", 0) or 0
    pending_reports = city.get("pending_reports", 0) or 0
    engagement_score = city.get("engagement_score", 0) or 0
    response_rate = city.get("response_rate", 0) or 0
    avg_response_time = city.get("avg_response_time", 0) or 0
    
    # Calculate resolution rate (percentage of resolved reports)
    resolution_rate = 0
    if total_reports > 0:
        resolution_rate = (resolved_reports / total_reports) * 100
    
    # Calculate responsiveness score (inverse of response time)
    # Lower response time is better
    responsiveness_score = 0
    if avg_response_time > 0:
        responsiveness_score = 100 / (1 + avg_response_time)  # Normalize to 0-100 scale
    else:
        # If no response time data, use response rate as a proxy
        responsiveness_score = response_rate
    
    # Authority activity score (combined measure of responsiveness and resolution)
    authority_score = (responsiveness_score * 0.6) + (resolution_rate * 0.4)
    
    # Citizen responsibility score (based on engagement and reports)
    citizen_score = engagement_score
    if total_reports > 0:
        # Adjust citizen score based on the ratio of pending reports
        # Lower pending ratio is better
        pending_ratio = pending_reports / total_reports
        pending_factor = 1 - (pending_ratio * 0.5)  # Penalize for high pending ratio
        citizen_score = citizen_score * pending_factor
    
    # Calculate total score (prioritize authority activity and citizen responsibility)
    # New weights: Authority activity (50%), Citizen responsibility (50%)
    total_score = (
        (authority_score * 0.5) +           # 50% weight to authority activity
        (citizen_score * 0.5)               # 50% weight to citizen responsibility
    )
    
    # Update total score and component scores
    await city_stats_collection.update_one(
        {"city_name_lower": normalized_city},
        {"$set": {
            "total_score": total_score,
            "authority_score": authority_score,
            "citizen_score": citizen_score,
            "last_updated": datetime.utcnow()
        }}
    )
    
    # Get updated city
    updated_city = await city_stats_collection.find_one({"city_name_lower": normalized_city})
    if updated_city:
        updated_city["id"] = str(updated_city["_id"])
        del updated_city["_id"]
        
    return updated_city 