from fastapi import APIRouter, HTTPException, Path
from typing import Optional, Dict, Any
from ..crud import user as user_crud
from ..crud import badge as badge_crud
from ..crud import city as city_crud
from ..crud import digital_wallet as wallet_crud
from bson.errors import InvalidId
from bson import ObjectId

router = APIRouter()

@router.get("/users/{user_id}/profile")
async def get_user_profile(
    user_id: str = Path(..., description="The ID of the user")
):
    """
    Get profile information about a user by ID including badge status, city information, and more
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
        
        # Get city statistics if user has city information
        city_info = None
        if user.get("city"):
            try:
                city_stats = await city_crud.get_city_stats(user.get("city"))
                if city_stats:
                    # Get city rank
                    leaderboard = await city_crud.get_city_leaderboard()
                    city_rank = None
                    for ranked_city in leaderboard:
                        if ranked_city.get("city_name_lower") == user.get("city").lower():
                            city_rank = ranked_city.get("rank")
                            break
                    
                    city_info = {
                        "name": user.get("city"),
                        "state": user.get("state"),
                        "country": user.get("country", "India"),
                        "rank": city_rank,
                        "total_reports": city_stats.get("total_reports", 0),
                        "resolved_reports": city_stats.get("resolved_reports", 0),
                        "total_users": city_stats.get("total_users", 0),
                        "authority_score": city_stats.get("authority_score", 0),
                        "citizen_score": city_stats.get("citizen_score", 0),
                        "total_score": city_stats.get("total_score", 0)
                    }
            except Exception:
                # If city stats retrieval fails, just provide basic city info
                city_info = {
                    "name": user.get("city"),
                    "state": user.get("state"),
                    "country": user.get("country", "India")
                }
        
        # Get digital wallet information if available
        wallet_info = None
        try:
            wallet = await wallet_crud.get_wallet_by_user_id(user_id)
            if wallet:
                wallet_info = {
                    "balance": wallet.get("balance", 0),
                    "total_earned": wallet.get("total_earned", 0),
                    "total_spent": wallet.get("total_spent", 0),
                    "updated_at": wallet.get("updated_at")
                }
        except Exception:
            # If wallet retrieval fails, continue without wallet info
            pass
        
        # Format user information with all available data
        user_info = {
            "id": str(user.get("_id")) if "_id" in user else user.get("id"),
            "name": user.get("name"),
            "email": user.get("email"),
            "picture": user.get("picture"),
            "google_id": user.get("google_id"),
            "city": city_info,
            "created_at": user.get("created_at"),
            "updated_at": user.get("updated_at"),
            "badge": badge_info,
            "wallet": wallet_info
        }
        
        # Add any other fields that might be in the user object
        for key, value in user.items():
            if key not in ["_id", "id", "name", "email", "picture", "google_id", "city", "state", "country", "created_at", "updated_at"]:
                user_info[key] = value
        
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
            
        # Get city information for context
        if user.get("city"):
            badge_info["city"] = user.get("city")
            badge_info["state"] = user.get("state")
            badge_info["country"] = user.get("country", "India")
            
            # Try to get city rank
            try:
                leaderboard = await city_crud.get_city_leaderboard()
                for ranked_city in leaderboard:
                    if ranked_city.get("city_name_lower") == user.get("city").lower():
                        badge_info["city_rank"] = ranked_city.get("rank")
                        break
            except Exception:
                pass
            
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