from fastapi import APIRouter
from ..auth.router import router as auth_router
from .user import router as user_router
from .waste_validation import router as waste_validation_router
from .badges import router as badges_router

router = APIRouter()

# Include all routers
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(user_router, prefix="/users", tags=["users"])
router.include_router(waste_validation_router, prefix="/waste-validation", tags=["waste-validation"])
router.include_router(badges_router, prefix="/badges", tags=["badges"])
# Digital wallet router is included in routes.py

__all__ = ["router"] 