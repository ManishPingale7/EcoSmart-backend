from fastapi import APIRouter, HTTPException, Depends, Path, Body
from typing import Dict, Any, List
from datetime import datetime
from ..models import PickupRequest
from ..crud import pickup as pickup_crud
from bson.errors import InvalidId

router = APIRouter(
    tags=["Pickup"],
    responses={404: {"description": "Not found"}},
)

@router.post("/schedule", 
    response_model=PickupRequest,
    summary="Schedule a pickup",
    description="Schedule a waste pickup request providing description, location, and pickup date"
)
async def schedule_pickup(
    pickup_request: PickupRequest = Body(..., description="Pickup request details")
):
    """
    Schedule a waste pickup request
    """
    try:
        # Prepare pickup data
        pickup_data = pickup_request.dict(exclude_unset=True)
        
        # Schedule the pickup
        scheduled_pickup = await pickup_crud.schedule_pickup(pickup_data)
        
        return scheduled_pickup
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error scheduling pickup: {str(e)}"
        )

@router.get("/all", 
    response_model=List[PickupRequest],
    summary="Get all pickups",
    description="Get a list of all scheduled pickup requests"
)
async def get_all_pickups():
    """
    Get all scheduled pickups
    """
    try:
        pickups = await pickup_crud.get_all_pickups()
        return pickups
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving pickups: {str(e)}"
        )

@router.get("/user/{user_id}", 
    response_model=List[PickupRequest],
    summary="Get user pickups",
    description="Get all pickup requests for a specific user"
)
async def get_user_pickups(
    user_id: str = Path(..., description="The ID of the user")
):
    """
    Get pickup requests for a specific user
    """
    try:
        pickups = await pickup_crud.get_user_pickups(user_id)
        return pickups
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user ID format: {user_id}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving pickups: {str(e)}"
        )

@router.get("/{pickup_id}", 
    response_model=PickupRequest,
    summary="Get pickup by ID",
    description="Get details of a specific pickup request by ID"
)
async def get_pickup_by_id(
    pickup_id: str = Path(..., description="The ID of the pickup request")
):
    """
    Get a pickup request by ID
    """
    try:
        pickup = await pickup_crud.get_pickup_by_id(pickup_id)
        if not pickup:
            raise HTTPException(
                status_code=404,
                detail=f"Pickup request with ID {pickup_id} not found"
            )
        return pickup
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pickup ID format: {pickup_id}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving pickup: {str(e)}"
        )

@router.put("/{pickup_id}/status/{status}", 
    response_model=PickupRequest,
    summary="Update pickup status",
    description="Update the status of a pickup request (pending, confirmed, completed, cancelled)"
)
async def update_pickup_status(
    pickup_id: str = Path(..., description="The ID of the pickup request"),
    status: str = Path(..., description="The new status (pending, confirmed, completed, cancelled)")
):
    """
    Update the status of a pickup request
    """
    try:
        # Validate status
        valid_statuses = ["pending", "confirmed", "completed", "cancelled"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
            
        # Update the pickup status
        updated_pickup = await pickup_crud.update_pickup_status(pickup_id, status)
        
        if not updated_pickup:
            raise HTTPException(
                status_code=404,
                detail=f"Pickup request with ID {pickup_id} not found"
            )
            
        return updated_pickup
    except InvalidId:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pickup ID format: {pickup_id}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating pickup status: {str(e)}"
        ) 