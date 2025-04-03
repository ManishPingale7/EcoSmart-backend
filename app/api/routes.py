from fastapi import APIRouter, Depends
from ..auth.router import get_current_authority

router = APIRouter(prefix="/api", tags=["API"])

@router.get("/protected")
async def protected_route(current_authority: dict = Depends(get_current_authority)):
    """Example of a protected route"""
    return {
        "message": "This is a protected route",
        "user": current_authority
    }

@router.get("/public")
async def public_route():
    """Example of a public route"""
    return {"message": "This is a public route"} 