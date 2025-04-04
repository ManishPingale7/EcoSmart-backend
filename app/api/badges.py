from fastapi import APIRouter, HTTPException, Path, Body
from typing import Dict, Any
from ..models import BadgeLevel, BadgeAddRequest
from ..crud import user as user_crud
from ..crud import badge as badge_crud
from bson.errors import InvalidId
from bson import ObjectId
from datetime import datetime

router = APIRouter()

# Get badge by user ID
@router.get("/{user_id}")
async def get_badge_by_id(
    user_id: str = Path(..., description="The ID of the user")
):
    """
    Get badge information for a user by ID
    """
    try:
        user = await user_crud.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {user_id} not found"
            )
        
        # Get all user badges
        user_badges = await badge_crud.get_user_badges(user_id)
        
        # Get user badge stats
        user_badge_stats = await badge_crud.get_user_badge_stats(user_id)
        total_reports = user_badge_stats.get("total_reports", 0) if user_badge_stats else 0
        
        # Calculate eco-score based on reports
        eco_score = min(100, max(0, total_reports * 2))
        
        # Format badge information
        badge_info = {
            "user_id": user_id,
            "name": user.get("name", "Unknown"),
            "total_reports": total_reports,
            "badges": user_badges,
            "eco_score": eco_score,
            "badge_updated_at": user_badge_stats.get("updated_at") if user_badge_stats else None
        }
        
        # Add rewards info for each badge level
        for badge in user_badges:
            badge_level = badge.get("badge_level")
            if badge_level == BadgeLevel.BRONZE:
                badge["rewards"] = [
                    "0.25% interest rate reduction on green loans",
                    "50 EcoPoints redeemable at partner businesses",
                    "Certificate of Environmental Contribution"
                ]
            elif badge_level == BadgeLevel.SILVER:
                badge["rewards"] = [
                    "0.5% interest rate reduction on green loans",
                    "150 EcoPoints redeemable at partner businesses",
                    "Priority processing for municipal services"
                ]
            elif badge_level == BadgeLevel.GOLD:
                badge["rewards"] = [
                    "1% interest rate reduction on green loans",
                    "300 EcoPoints redeemable at partner businesses",
                    "Annual free waste collection service",
                    "Official recognition in city environmental program"
                ]
            else:
                badge["rewards"] = []
            
        return badge_info
        
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user ID format: {user_id}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving badge information: {str(e)}"
        )

# Manually add a badge to a user
@router.post("/add")
async def add_badge(
    request: BadgeAddRequest
):
    """
    Manually add a badge to a user
    """
    try:
        user_id = request.user_id
        badge_level = request.badge_level
            
        # Get the user
        user = await user_crud.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {user_id} not found"
            )
        
        # Get badge by level
        all_badges = await badge_crud.get_badges()
        badge_to_assign = next((b for b in all_badges if b.get("level") == badge_level), None)
        
        if not badge_to_assign:
            raise HTTPException(
                status_code=404,
                detail=f"Badge with level {badge_level} not found"
            )
        
        # Assign the badge to the user
        user_badge = await badge_crud.assign_user_badge(
            user_id=user_id,
            badge_id=badge_to_assign["id"],
            badge_name=badge_to_assign["name"],
            badge_level=badge_level
        )
        
        # Make sure user has appropriate report count for this badge level in badge_stats
        user_badge_stats = await badge_crud.get_user_badge_stats(user_id)
        report_count_update = {}
        
        if user_badge_stats:
            current_reports = user_badge_stats.get("total_reports", 0)
            required_reports = 0
            
            if badge_level == BadgeLevel.GOLD and current_reports < 50:
                required_reports = 50
            elif badge_level == BadgeLevel.SILVER and current_reports < 25:
                required_reports = 25
            elif badge_level == BadgeLevel.BRONZE and current_reports < 10:
                required_reports = 10
                
            if required_reports > 0 and current_reports < required_reports:
                # Update report count in user_badge_stats
                await badge_crud.user_badge_stats_collection.update_one(
                    {"user_id": user_id},
                    {"$set": {
                        "total_reports": required_reports,
                        "updated_at": datetime.utcnow()
                    }}
                )
        else:
            # Create user badge stats if it doesn't exist
            required_reports = 0
            if badge_level == BadgeLevel.GOLD:
                required_reports = 50
            elif badge_level == BadgeLevel.SILVER:
                required_reports = 25
            elif badge_level == BadgeLevel.BRONZE:
                required_reports = 10
                
            await badge_crud.user_badge_stats_collection.insert_one({
                "user_id": user_id,
                "total_reports": required_reports,
                "badges_earned": [badge_to_assign["id"]],
                "updated_at": datetime.utcnow()
            })
            
        return {
            "message": f"Badge {badge_level} added to user {user_id}",
            "user_id": user_id,
            "badge_level": badge_level,
            "badge_id": user_badge.get("id")
        }
            
    except HTTPException:
        raise
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user ID format"
        ) 
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error adding badge: {str(e)}"
        )
        
# For reference: Badge levels and benefits overview        
@router.get("/info")
async def get_badge_info():
    """
    Get badge system information including levels and rewards
    """
    return {
        "badge_levels": [
            {
                "level": "bronze",
                "required_reports": 10,
                "rewards": [
                    "0.25% interest rate reduction on green loans",
                    "50 EcoPoints redeemable at partner businesses",
                    "Certificate of Environmental Contribution"
                ]
            },
            {
                "level": "silver",
                "required_reports": 25,
                "rewards": [
                    "0.5% interest rate reduction on green loans",
                    "150 EcoPoints redeemable at partner businesses",
                    "Priority processing for municipal services"
                ]
            },
            {
                "level": "gold",
                "required_reports": 50,
                "rewards": [
                    "1% interest rate reduction on green loans",
                    "300 EcoPoints redeemable at partner businesses",
                    "Annual free waste collection service",
                    "Official recognition in city environmental program"
                ]
            }
        ]
    } 