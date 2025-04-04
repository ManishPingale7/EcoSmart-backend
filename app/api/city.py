from fastapi import APIRouter, HTTPException, Depends, Path, Query, Body
from typing import Dict, Any, List
from datetime import datetime
from ..models import CityStats, CityLeaderboard, UpdateCityRequest
from ..crud import city as city_crud
from ..crud import user as user_crud
from bson.errors import InvalidId

router = APIRouter(
    tags=["City Leaderboard"],
    responses={404: {"description": "Not found"}},
)

@router.put("/users/{user_id}/city", 
    summary="Update user city",
    description="Update the city information for a user"
)
async def update_user_city(
    user_id: str = Path(..., description="The ID of the user"),
    city_request: UpdateCityRequest = Body(..., description="City information")
):
    """
    Update the city information for a user
    """
    try:
        # Get user
        user = await user_crud.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {user_id} not found"
            )
            
        # Check if city is changing
        old_city = user.get("city")
        new_city = city_request.city
        
        # Update user with city information
        user_data = {
            "city": city_request.city,
            "state": city_request.state,
            "country": city_request.country
        }
        
        updated_user = await user_crud.update_user(user_id, user_data)
        
        # Update city stats - decrement old city if exists
        if old_city and old_city != new_city:
            await city_crud.increment_city_users(old_city, -1)
            
        # Increment new city user count
        await city_crud.increment_city_users(new_city)
        
        return {
            "message": f"City updated to {new_city}",
            "user_id": user_id,
            "city": new_city,
            "state": city_request.state,
            "country": city_request.country
        }
        
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
            detail=f"Error updating user city: {str(e)}"
        )

@router.get("/stats/{city_name}", 
    response_model=CityStats,
    summary="Get city stats",
    description="Get statistics for a specific city"
)
async def get_city_stats(
    city_name: str = Path(..., description="The name of the city")
):
    """
    Get statistics for a specific city
    """
    try:
        city_stats = await city_crud.get_city_stats(city_name)
        if not city_stats:
            raise HTTPException(
                status_code=404,
                detail=f"No statistics found for city: {city_name}"
            )
        return city_stats
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving city stats: {str(e)}"
        )

@router.get("/leaderboard", 
    response_model=CityLeaderboard,
    summary="Get city leaderboard",
    description="Get leaderboard of cities ranked by their performance based on active municipal authorities and responsible citizens"
)
async def get_city_leaderboard(
    limit: int = Query(10, description="Number of cities to include in leaderboard", ge=1, le=100)
):
    """
    Get leaderboard of cities ranked by their performance metrics.
    Cities are ranked based on:
    1. Municipal authority activity (responsiveness and resolution rate)
    2. Citizen responsibility (engagement and reporting)
    """
    try:
        # Get all ranked cities
        ranked_cities = await city_crud.get_city_leaderboard()
        
        # Limit to requested number of cities
        limited_cities = ranked_cities[:limit]
        
        # Add explanatory information about the scoring
        response = {
            "cities": limited_cities,
            "last_updated": datetime.utcnow(),
            "scoring_explanation": {
                "authority_score": "50% of total - Measures municipal responsiveness and resolution efficiency",
                "citizen_score": "50% of total - Measures citizen engagement and responsible reporting",
                "total_score": "Combined score determining overall ranking"
            }
        }
        
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving city leaderboard: {str(e)}"
        )

@router.get("/stats", 
    response_model=List[CityStats],
    summary="Get all city stats",
    description="Get statistics for all cities"
)
async def get_all_city_stats():
    """
    Get statistics for all cities
    """
    try:
        city_stats = await city_crud.get_all_city_stats()
        return city_stats
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving city stats: {str(e)}"
        ) 