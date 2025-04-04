from fastapi import APIRouter, HTTPException, Path
from typing import Optional, Dict, Any
from ..crud import user as user_crud
from ..crud import badge as badge_crud
from bson.errors import InvalidId
from bson import ObjectId

router = APIRouter()

@router.get("/users/{user_id}/profile")
async def get_user_profile(
    user_id: str = Path(..., description="The ID of the user")
):
    """
    Get profile information about a user by ID including badge status
    """
    try:
        user = await user_crud.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        # Get all user badges
        user_badges = await badge_crud.get_user_badges(user_id)
        
        # Get user badge stats
        user_badge_stats = await badge_crud.get_user_badge_stats(user_id)
        total_reports = user_badge_stats.get("total_reports", 0) if user_badge_stats else 0
        
        # Determine highest badge level
        badge_level_order = {"diamond": 5, "platinum": 4, "gold": 3, "silver": 2, "bronze": 1, None: 0}
        highest_badge = None
        highest_level = 0
        
        for badge in user_badges:
            level_value = badge_level_order.get(badge.get("badge_level"), 0)
            if level_value > highest_level:
                highest_level = level_value
                highest_badge = badge.get("badge_level")
        
        # Format badge information
        badge_info = {
            "total_reports": total_reports,
            "badges": user_badges,
            "current_badge_level": highest_badge,
            "badge_updated_at": user_badge_stats.get("updated_at") if user_badge_stats else None
        }
        
        # Calculate reports needed for next badge level
        reports = total_reports
        if reports < 10:
            badge_info["next_badge"] = "bronze"
            badge_info["reports_needed"] = 10 - reports
        elif reports < 25:
            badge_info["next_badge"] = "silver"
            badge_info["reports_needed"] = 25 - reports
        elif reports < 50:
            badge_info["next_badge"] = "gold"
            badge_info["reports_needed"] = 50 - reports
        elif reports < 100:
            badge_info["next_badge"] = "platinum"
            badge_info["reports_needed"] = 100 - reports
        elif reports < 250:
            badge_info["next_badge"] = "diamond"
            badge_info["reports_needed"] = 250 - reports
        else:
            badge_info["next_badge"] = None
            badge_info["reports_needed"] = 0
        
        # Format user information
        user_info = {
            "id": str(user.get("_id")),
            "name": user.get("name"),
            "email": user.get("email"),
            "picture": user.get("picture"),
            "badge": badge_info
        }
        
        return user_info
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving user profile information: {str(e)}"
        )

@router.get("/users/{user_id}/badge")
async def get_user_badge_info(
    user_id: str = Path(..., description="The ID of the user")
):
    """
    Get badge information for a specific user
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
        
        # Determine highest badge level
        badge_level_order = {"diamond": 5, "platinum": 4, "gold": 3, "silver": 2, "bronze": 1, None: 0}
        highest_badge = None
        highest_level = 0
        
        for badge in user_badges:
            level_value = badge_level_order.get(badge.get("badge_level"), 0)
            if level_value > highest_level:
                highest_level = level_value
                highest_badge = badge.get("badge_level")
        
        # Format badge information
        badge_info = {
            "user_id": user_id,
            "name": user.get("name", "Unknown"),
            "total_reports": total_reports,
            "badges": user_badges,
            "current_badge_level": highest_badge,
            "badge_updated_at": user_badge_stats.get("updated_at") if user_badge_stats else None
        }
        
        # Calculate reports needed for next badge level
        reports = total_reports
        if reports < 10:
            badge_info["next_badge"] = "bronze"
            badge_info["reports_needed"] = 10 - reports
        elif reports < 25:
            badge_info["next_badge"] = "silver"
            badge_info["reports_needed"] = 25 - reports
        elif reports < 50:
            badge_info["next_badge"] = "gold"
            badge_info["reports_needed"] = 50 - reports
        elif reports < 100:
            badge_info["next_badge"] = "platinum"
            badge_info["reports_needed"] = 100 - reports
        elif reports < 250:
            badge_info["next_badge"] = "diamond"
            badge_info["reports_needed"] = 250 - reports
        else:
            badge_info["next_badge"] = None
            badge_info["reports_needed"] = 0
            
        return badge_info
        
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user ID format: {user_id}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving user badge information: {str(e)}"
        ) 